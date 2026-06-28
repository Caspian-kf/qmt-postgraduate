import json
import random
import re
import subprocess
import time
import warnings
from collections import Counter
from datetime import datetime
from io import StringIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


warnings.simplefilter("ignore", InsecureRequestWarning)

SCHOOL = "南京邮电大学"
COLLEGE = "材料科学与工程学院"
MAJOR = "材料科学与工程"

TIMEOUT = 15
REQUEST_INTERVAL = (2, 5)
MAX_ARTICLES = 100
MAX_LIST_PAGES = 12

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"

MATERIALS_JSON = DATA_DIR / "kaoyan_materials.json"
SCORE_JSON = DATA_DIR / "score_lines.json"
ADMISSION_JSON = DATA_DIR / "admission_stats.json"
EXAM_JSON = DATA_DIR / "exam_info.json"

MATERIALS_COLUMNS = [
    "school",
    "college",
    "major",
    "category",
    "title",
    "content",
    "publish_time",
    "url",
    "source",
    "crawl_time",
]

SCORE_COLUMNS = [
    "year",
    "school",
    "college",
    "major_code",
    "major_name",
    "degree_type",
    "study_type",
    "score_line",
    "politics",
    "foreign_language",
    "business_course_1",
    "business_course_2",
    "source_title",
    "source_url",
    "crawl_time",
]

ADMISSION_COLUMNS = [
    "year",
    "school",
    "college",
    "major_code",
    "major_name",
    "degree_type",
    "study_type",
    "planned_enrollment",
    "reexam_count",
    "admitted_count",
    "adjustment_count",
    "lowest_score",
    "highest_score",
    "average_score",
    "source_title",
    "source_url",
    "crawl_time",
    "note",
]

EXAM_COLUMNS = [
    "year",
    "school",
    "college",
    "major_code",
    "major_name",
    "exam_type",
    "subject_code",
    "subject_name",
    "reference_books",
    "outline_title",
    "source_url",
    "crawl_time",
]

PUBLIC_SEED_URLS = [
    "https://iam.njupt.edu.cn/10962/listm.htm",
    "https://iam.njupt.edu.cn/10962/list.htm",
    "https://iam.njupt.edu.cn/",
    "https://yzb.njupt.edu.cn/",
    "https://yzb.njupt.edu.cn/7795/list.htm",
    "https://yzb.njupt.edu.cn/7797/list.htm",
    "https://yzb.njupt.edu.cn/7798/list.htm",
    "https://yzb.njupt.edu.cn/7799/list.htm",
    "https://yzb.njupt.edu.cn/7813/list.htm",
]

ARTICLE_KEYWORDS = [
    "复试分数线",
    "分数线",
    "招生简章",
    "专业目录",
    "考试大纲",
    "大纲",
    "复试",
    "拟录取",
    "综合成绩",
    "调剂",
    "参考书",
    "材料",
    "硕士",
    "研究生",
]

KAOYAN_TITLE_KEYWORDS = [
    "复试分数线",
    "分数线",
    "招生简章",
    "专业目录",
    "考试大纲",
    "大纲",
    "复试",
    "拟录取",
    "综合成绩",
    "调剂",
    "参考书",
    "硕士研究生",
    "硕士生",
    "推免生",
]

MATERIAL_TERMS = [
    "材料科学与工程学院",
    "信息材料与纳米技术研究院",
    "材料科学与工程",
    "材料",
    "080500",
    "080300",
    "0809Z1",
    "0809Z2",
    "085400",
    "电子信息",
    "有机电子学",
    "生物电子学",
    "光学工程",
]

TARGET_MAJORS = {
    "080300": "光学工程",
    "080500": "材料科学与工程",
    "0809Z1": "有机电子学",
    "0809Z2": "生物电子学",
    "085400": "电子信息",
}

CAPTCHA_TERMS = ["验证码", "安全验证", "访问过于频繁", "人机验证", "captcha"]
ATTACHMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx")

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
)


def main():
    start = time.time()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("启动真实公开数据采集：南京邮电大学材料考研")
    print("合规边界：只采集公开网页和公开附件，不保存考生个人明细。")

    materials = load_json(MATERIALS_JSON, MATERIALS_COLUMNS)
    score_lines = load_json(SCORE_JSON, SCORE_COLUMNS)
    admission_stats = load_json(ADMISSION_JSON, ADMISSION_COLUMNS)
    exam_info = load_json(EXAM_JSON, EXAM_COLUMNS)

    material_keys = {dedupe_key(item) for item in materials}
    score_keys = {structured_key(item, ["year", "major_code", "major_name", "source_url"]) for item in score_lines}
    admission_keys = {structured_key(item, ["year", "major_code", "major_name", "source_url"]) for item in admission_stats}
    exam_keys = {structured_key(item, ["year", "major_code", "subject_code", "outline_title", "source_url"]) for item in exam_info}

    urls = discover_article_urls(PUBLIC_SEED_URLS)
    print(f"\n候选详情页数量：{len(urls)}")

    added = Counter()
    for index, url in enumerate(urls[:MAX_ARTICLES], start=1):
        print(f"\n[{index}/{min(len(urls), MAX_ARTICLES)}] 当前采集来源：{source_name(url)}")
        print(f"当前 URL：{url}")

        try:
            html = fetch_text(url)
            if not html:
                print("失败原因：页面无法读取或按合规要求跳过")
                continue

            soup = BeautifulSoup(html, "lxml")
            title = extract_title(soup) or url
            content = extract_content(soup)
            publish_time = extract_publish_time(soup, content, title)
            category = classify_category(title)
            attachments = extract_attachments(soup, url)

            if not is_relevant_article(title, content, url):
                print(f"当前标题：{title}")
                print("失败原因：不是材料考研相关公开信息")
                continue

            article = normalize_record(
                {
                    "school": SCHOOL,
                    "college": COLLEGE,
                    "major": MAJOR,
                    "category": category,
                    "title": title,
                    "content": summarize(with_attachment_note(content, attachments)),
                    "publish_time": publish_time,
                    "url": url,
                    "source": source_name(url),
                    "crawl_time": now(),
                },
                MATERIALS_COLUMNS,
            )

            key = dedupe_key(article)
            if key not in material_keys:
                materials.append(article)
                material_keys.add(key)
                added["materials"] += 1

            for item in parse_score_lines(title, url, html, content):
                key = structured_key(item, ["year", "major_code", "major_name", "source_url"])
                if key not in score_keys:
                    score_lines.append(item)
                    score_keys.add(key)
                    added["score_lines"] += 1

            for item in parse_exam_info(title, url, content, attachments):
                key = structured_key(item, ["year", "major_code", "subject_code", "outline_title", "source_url"])
                if key not in exam_keys:
                    exam_info.append(item)
                    exam_keys.add(key)
                    added["exam_info"] += 1

            for item in parse_admission_stats(title, url, html, content, attachments):
                key = structured_key(item, ["year", "major_code", "major_name", "source_url"])
                if key not in admission_keys:
                    admission_stats.append(item)
                    admission_keys.add(key)
                    added["admission_stats"] += 1

            print(f"当前标题：{title}")
            print(f"当前累计数量：原始 {len(materials)} / 分数线 {len(score_lines)} / 录取统计 {len(admission_stats)} / 考试信息 {len(exam_info)}")

            if sum(added.values()) and sum(added.values()) % 20 == 0:
                save_all(materials, score_lines, admission_stats, exam_info)
                print("阶段性保存完成。")
        except Exception as exc:
            print(f"失败原因：单页解析异常 {exc}")

    save_all(materials, score_lines, admission_stats, exam_info)
    elapsed = time.time() - start

    print("\n采集结束")
    print(f"本次新增原始信息：{added['materials']}")
    print(f"本次新增分数线记录：{added['score_lines']}")
    print(f"本次新增录取统计记录：{added['admission_stats']}")
    print(f"本次新增考试信息记录：{added['exam_info']}")
    print(f"总数据量：原始 {len(materials)} / 分数线 {len(score_lines)} / 录取统计 {len(admission_stats)} / 考试信息 {len(exam_info)}")
    print("原始信息 category 数量：")
    for category, count in Counter(item.get("category", "其他") for item in materials).most_common():
        print(f"- {category}: {count}")
    print(f"JSON 保存路径：{DATA_DIR}")
    print(f"CSV 保存路径：{DATA_DIR}")
    print(f"总耗时：{elapsed:.2f} 秒")


def discover_article_urls(seed_urls):
    visited = set()
    queue = list(dict.fromkeys(seed_urls))
    articles = []

    while queue and len(visited) < MAX_LIST_PAGES:
        url = queue.pop(0)
        if url in visited or not is_allowed_domain(url):
            continue
        visited.add(url)

        print(f"\n扫描列表页：{url}")
        html = fetch_text(url)
        if not html:
            print("列表页跳过：无法读取")
            continue

        soup = BeautifulSoup(html, "lxml")
        links = extract_links(soup, url)
        for link_url, link_text in links:
            if not is_allowed_domain(link_url):
                continue
            if is_list_page(link_url) and link_url not in visited and link_url not in queue:
                queue.append(link_url)
            if is_candidate_article(link_text, link_url) and link_url not in articles:
                articles.append(link_url)
        print(f"候选详情页累计：{len(articles)}")

    return articles


def fetch_text(url):
    sleep_random()
    for verify in (True, False):
        try:
            response = SESSION.get(url, timeout=TIMEOUT, verify=verify)
            break
        except requests.exceptions.SSLError as exc:
            if verify:
                print(f"SSL 读取失败，尝试兼容模式：{exc}")
                continue
            print(f"失败原因：SSL 异常 {exc}")
            return fetch_text_with_curl(url)
        except requests.RequestException as exc:
            print(f"失败原因：请求异常 {exc}")
            return fetch_text_with_curl(url)
    else:
        return ""

    if response.status_code in {403, 429}:
        print(f"失败原因：HTTP {response.status_code}，按合规要求跳过")
        return ""
    if response.status_code >= 400:
        print(f"失败原因：HTTP {response.status_code}")
        return ""

    response.encoding = response.apparent_encoding or response.encoding
    text = response.text
    lowered = text.lower()
    if any(term.lower() in lowered for term in CAPTCHA_TERMS):
        print("失败原因：疑似验证码或访问限制页面，按合规要求跳过")
        return ""
    return text


def fetch_text_with_curl(url):
    print("尝试使用 curl 读取公开页面")
    try:
        result = subprocess.run(
            ["curl.exe", "-L", "--compressed", "--max-time", str(TIMEOUT), "-sS", url],
            capture_output=True,
            check=False,
        )
    except Exception as exc:
        print(f"curl 读取失败：{exc}")
        return ""

    if result.returncode != 0 or not result.stdout:
        stderr = result.stderr.decode("utf-8", errors="ignore")
        print(f"curl 读取失败：{stderr or result.returncode}")
        return ""

    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            text = result.stdout.decode(encoding)
            break
        except UnicodeDecodeError:
            text = ""
    lowered = text.lower()
    if any(term.lower() in lowered for term in CAPTCHA_TERMS):
        print("失败原因：疑似验证码或访问限制页面，按合规要求跳过")
        return ""
    return text


def load_json(path, columns):
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, list):
            records = [normalize_record(item, columns) for item in data if isinstance(item, dict)]
            if path == MATERIALS_JSON:
                records = [
                    item for item in records
                    if is_valid_saved_material(item)
                ]
            if path in {SCORE_JSON, ADMISSION_JSON, EXAM_JSON}:
                records = [
                    item for item in records
                    if "博士" not in f"{item.get('source_title', '')} {item.get('outline_title', '')} {item.get('major_name', '')}"
                ]
            return records
    except Exception as exc:
        print(f"读取 {path.name} 失败，将使用空数据：{exc}")
    return []


def save_all(materials, score_lines, admission_stats, exam_info):
    save_dataset(MATERIALS_JSON, DATA_DIR / "kaoyan_materials.csv", materials, MATERIALS_COLUMNS)
    save_dataset(SCORE_JSON, DATA_DIR / "score_lines.csv", score_lines, SCORE_COLUMNS)
    save_dataset(ADMISSION_JSON, DATA_DIR / "admission_stats.csv", admission_stats, ADMISSION_COLUMNS)
    save_dataset(EXAM_JSON, DATA_DIR / "exam_info.csv", exam_info, EXAM_COLUMNS)


def save_dataset(json_path, csv_path, records, columns):
    cleaned = [normalize_record(item, columns) for item in records]
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(cleaned, file, ensure_ascii=False, indent=2)
    pd.DataFrame(cleaned, columns=columns).to_csv(csv_path, index=False, encoding="utf-8-sig")


def extract_links(soup, base_url):
    links = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        text = normalize_text(anchor.get_text(" ", strip=True))
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        clean = parsed._replace(fragment="").geturl()
        if clean.startswith("http"):
            links.append((clean, text))
    return links


def extract_attachments(soup, base_url):
    attachments = []
    for link_url, text in extract_links(soup, base_url):
        lowered = link_url.lower()
        if any(lowered.split("?")[0].endswith(ext) for ext in ATTACHMENT_EXTENSIONS):
            attachments.append({"title": text or Path(urlparse(link_url).path).name, "url": link_url})
    return attachments


def extract_title(soup):
    selectors = ["h1", ".arti_title", ".article-title", ".news_title", ".title", "title"]
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            title = normalize_text(node.get_text(" ", strip=True))
            title = re.sub(r"[-_]?南京邮电大学.*$", "", title).strip()
            if title:
                return title
    return ""


def extract_content(soup):
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    preferred = soup.select_one(".wp_articlecontent, .article, .article-content, .content, .main, #content")
    text = preferred.get_text(" ", strip=True) if preferred else soup.get_text(" ", strip=True)
    return normalize_text(text)


def extract_publish_time(soup, content, title=""):
    text = " ".join([title, soup.get_text(" ", strip=True)[:1200], content[:1200]])
    match = re.search(r"(20\d{2})[-/.年]\s*(\d{1,2})[-/.月]\s*(\d{1,2})", text)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    year = extract_year(text)
    return year


def classify_category(title):
    if "复试分数线" in title or "分数线" in title:
        return "复试分数线"
    if "招生简章" in title:
        return "招生简章"
    if "专业目录" in title:
        return "专业目录"
    if "大纲" in title:
        return "考试大纲"
    if "拟录取" in title or "综合成绩" in title:
        return "拟录取名单"
    if "调剂" in title:
        return "调剂信息"
    if "复试" in title:
        return "复试细则"
    return "其他"


def is_candidate_article(text, url):
    combined = normalize_text(f"{text} {url}")
    if is_attachment(url) or is_list_page(url):
        return False
    return any(keyword in combined for keyword in KAOYAN_TITLE_KEYWORDS)


def is_relevant_article(title, content, url):
    combined = normalize_text(f"{title} {content} {url}")
    if "博士" in title and "硕士" not in title:
        return False
    if "yzb.njupt.edu.cn" in urlparse(url).netloc.lower():
        return any(keyword in title for keyword in KAOYAN_TITLE_KEYWORDS)
    return any(keyword in title for keyword in KAOYAN_TITLE_KEYWORDS) and any(term in combined for term in MATERIAL_TERMS)


def is_valid_saved_material(item):
    combined = f"{item.get('title', '')} {item.get('content', '')} {item.get('url', '')}"
    if "模拟" in combined:
        return False
    if "博士" in item.get("title", "") and "硕士" not in item.get("title", ""):
        return False
    if not any(keyword in combined for keyword in KAOYAN_TITLE_KEYWORDS):
        return False
    return True


def parse_score_lines(title, url, html, content):
    if "分数线" not in title and "复试线" not in title and "复试分数" not in content:
        return []

    year = extract_year(title) or extract_year(content)
    source = source_name(url)
    rows = []

    for table in read_html_tables(html):
        for _, row in table.iterrows():
            text = normalize_text(" ".join(str(value) for value in row.tolist() if str(value) != "nan"))
            if not row_matches_material(text):
                continue
            rows.extend(score_records_from_text(text, year, title, url))

    if not rows:
        for line in split_text_lines(content):
            if row_matches_material(line):
                rows.extend(score_records_from_text(line, year, title, url))

    if not rows and row_matches_material(content):
        rows.append(
            score_record(
                year=year,
                major_code=extract_major_code(content),
                major_name=extract_major_name(content),
                score_line="",
                degree_type=extract_degree_type(content),
                study_type=extract_study_type(content),
                source_title=title,
                source_url=url,
            )
        )

    return [normalize_record(item, SCORE_COLUMNS) for item in rows]


def score_records_from_text(text, year, title, url):
    code = extract_major_code(text)
    majors = []
    if code:
        majors.append((code, TARGET_MAJORS.get(code, extract_major_name(text))))
    else:
        name = extract_major_name(text)
        if name:
            majors.append(("", name))

    if not majors:
        return []

    score = extract_score_line(text)
    return [
        score_record(
            year=year,
            major_code=major_code,
            major_name=major_name,
            score_line=score,
            degree_type=extract_degree_type(text),
            study_type=extract_study_type(text),
            source_title=title,
            source_url=url,
        )
        for major_code, major_name in majors
    ]


def score_record(year, major_code, major_name, score_line, degree_type, study_type, source_title, source_url):
    return {
        "year": year,
        "school": SCHOOL,
        "college": COLLEGE,
        "major_code": major_code,
        "major_name": major_name,
        "degree_type": degree_type,
        "study_type": study_type,
        "score_line": score_line,
        "politics": "",
        "foreign_language": "",
        "business_course_1": "",
        "business_course_2": "",
        "source_title": source_title,
        "source_url": source_url,
        "crawl_time": now(),
    }


def parse_exam_info(title, url, content, attachments):
    if not any(keyword in f"{title} {content}" for keyword in ["专业目录", "招生简章", "考试大纲", "大纲", "参考书", "复试科目", "初试"]):
        return []

    year = extract_year(title) or extract_year(content)
    records = []
    source_text = normalize_text(f"{title} {content}")
    related = [item for item in TARGET_MAJORS.items() if item[0] in source_text or item[1] in source_text]
    if not related:
        related = [("", MAJOR)]

    subject_matches = re.findall(r"([0-9A-Z]{3,6})[）)\s、:：-]*([^，。；;\n]{2,30})", source_text)
    subject_text = "；".join(f"{code} {name}" for code, name in subject_matches[:8])
    attachment_text = "；".join(f"{item['title']} {item['url']}" for item in attachments)

    for major_code, major_name in related:
        records.append(
            normalize_record(
                {
                    "year": year,
                    "school": SCHOOL,
                    "college": COLLEGE,
                    "major_code": major_code,
                    "major_name": major_name,
                    "exam_type": "复试" if "复试" in source_text else "初试",
                    "subject_code": "",
                    "subject_name": subject_text,
                    "reference_books": extract_reference_books(source_text) or attachment_text,
                    "outline_title": title,
                    "source_url": url,
                    "crawl_time": now(),
                },
                EXAM_COLUMNS,
            )
        )
    return records


def parse_admission_stats(title, url, html, content, attachments):
    if not any(keyword in f"{title} {content}" for keyword in ["拟录取", "录取名单", "复试成绩", "综合成绩", "调剂"]):
        return []

    year = extract_year(title) or extract_year(content)
    note = "需人工核验"
    admitted_count = ""
    lowest_score = ""
    highest_score = ""
    average_score = ""
    attachment_urls = []

    table_stats = aggregate_tables_for_admission(html)
    if table_stats:
        admitted_count = table_stats.get("count", "")
        lowest_score = table_stats.get("min", "")
        highest_score = table_stats.get("max", "")
        average_score = table_stats.get("avg", "")
        note = "由网页表格聚合统计，未保存个人明细"

    for attachment in attachments:
        attachment_urls.append(attachment["url"])
        stats = parse_attachment_for_admission(attachment["url"])
        if stats and not admitted_count:
            admitted_count = stats.get("count", "")
            lowest_score = stats.get("min", "")
            highest_score = stats.get("max", "")
            average_score = stats.get("avg", "")
            note = stats.get("note", "由附件聚合统计，未保存个人明细")

    source_url = "；".join(attachment_urls) if attachment_urls else url
    if attachment_urls and not admitted_count:
        note = "附件未解析，需人工核验"

    return [
        normalize_record(
            {
                "year": year,
                "school": SCHOOL,
                "college": COLLEGE,
                "major_code": extract_major_code(content),
                "major_name": extract_major_name(content) or MAJOR,
                "degree_type": extract_degree_type(content),
                "study_type": extract_study_type(content),
                "planned_enrollment": extract_count_near(content, ["计划", "招生"]),
                "reexam_count": extract_count_near(content, ["复试"]),
                "admitted_count": admitted_count,
                "adjustment_count": extract_count_near(content, ["调剂"]),
                "lowest_score": lowest_score,
                "highest_score": highest_score,
                "average_score": average_score,
                "source_title": title,
                "source_url": source_url,
                "crawl_time": now(),
                "note": note,
            },
            ADMISSION_COLUMNS,
        )
    ]


def aggregate_tables_for_admission(html):
    rows = []
    scores = []
    for table in read_html_tables(html):
        text_table = table.astype(str)
        for _, row in text_table.iterrows():
            text = normalize_text(" ".join(str(value) for value in row.tolist() if str(value) and str(value) != "nan"))
            if not text or re.search(r"姓名|身份证|准考证", text):
                pass
            if "拟录取" in text or "录取" in text:
                rows.append(text)
            scores.extend(extract_score_candidates(text))
    if not rows:
        return {}
    valid_scores = [score for score in scores if 100 <= score <= 500]
    return build_score_stats(len(rows), valid_scores)


def parse_attachment_for_admission(url):
    lowered = url.lower().split("?")[0]
    path = download_attachment(url)
    if not path:
        return {}

    if lowered.endswith((".xls", ".xlsx")):
        try:
            sheets = pd.read_excel(path, sheet_name=None)
            rows = []
            scores = []
            for table in sheets.values():
                for _, row in table.astype(str).iterrows():
                    text = normalize_text(" ".join(value for value in row.tolist() if value and value != "nan"))
                    if "拟录取" in text or "录取" in text:
                        rows.append(text)
                    scores.extend(extract_score_candidates(text))
            return {**build_score_stats(len(rows), scores), "note": "由 Excel 附件聚合统计，未保存个人明细"}
        except Exception as exc:
            print(f"Excel 附件解析失败：{exc}")
            return {"note": "附件未解析"}

    if lowered.endswith(".pdf"):
        if not pdfplumber:
            print("PDF 解析依赖未安装")
            return {"note": "PDF 解析依赖未安装，附件未解析"}
        try:
            text_parts = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    text_parts.append(page.extract_text() or "")
            text = "\n".join(text_parts)
            rows = [line for line in split_text_lines(text) if "拟录取" in line or "录取" in line]
            scores = extract_score_candidates(text)
            return {**build_score_stats(len(rows), scores), "note": "由 PDF 附件聚合统计，未保存个人明细"}
        except Exception as exc:
            print(f"PDF 附件解析失败：{exc}")
            return {"note": "附件未解析"}

    return {"note": "附件未解析"}


def download_attachment(url):
    try:
        sleep_random()
        response = SESSION.get(url, timeout=TIMEOUT, verify=False)
        if response.status_code >= 400:
            print(f"附件下载失败：HTTP {response.status_code} {url}")
            return None
        suffix = Path(urlparse(url).path).suffix or ".bin"
        filename = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(urlparse(url).path).stem)[-80:] or "attachment"
        path = RAW_DIR / f"{filename}{suffix}"
        path.write_bytes(response.content)
        return path
    except Exception as exc:
        print(f"附件下载失败：{exc}")
        return None


def read_html_tables(html):
    try:
        return pd.read_html(StringIO(html))
    except Exception:
        return []


def build_score_stats(count, scores):
    valid = [float(score) for score in scores if 100 <= float(score) <= 500]
    if not valid:
        return {"count": str(count) if count else "", "min": "", "max": "", "avg": ""}
    return {
        "count": str(count) if count else "",
        "min": f"{min(valid):.0f}",
        "max": f"{max(valid):.0f}",
        "avg": f"{sum(valid) / len(valid):.1f}",
    }


def extract_reference_books(text):
    match = re.search(r"(参考书目|参考书|指定教材)[：:\s]*(.{0,160})", text)
    return normalize_text(match.group(0)) if match else ""


def extract_count_near(text, keywords):
    compact = normalize_text(text)
    for keyword in keywords:
        match = re.search(rf"{keyword}[^0-9]{{0,12}}(\d{{1,4}})\s*人", compact)
        if match:
            return match.group(1)
    return ""


def extract_score_line(text):
    numbers = extract_score_candidates(text)
    numbers = [num for num in numbers if 150 <= num <= 450]
    return str(int(max(numbers))) if numbers else ""


def extract_score_candidates(text):
    values = []
    for match in re.finditer(r"(?<!\d)([1-4]\d{2}(?:\.\d+)?)(?!\d)", text):
        values.append(float(match.group(1)))
    return values


def extract_major_code(text):
    for code in TARGET_MAJORS:
        if code in text:
            return code
    match = re.search(r"(?<!\d)(0[78]\d{4}|08\d{2}Z\d|0854\d{2}|085400)(?!\d)", text)
    return match.group(1) if match else ""


def extract_major_name(text):
    for name in TARGET_MAJORS.values():
        if name in text:
            return name
    if "材料" in text:
        return MAJOR
    return ""


def extract_degree_type(text):
    if "专业学位" in text or "专硕" in text:
        return "专业学位"
    if "学术学位" in text or "学硕" in text:
        return "学术学位"
    return ""


def extract_study_type(text):
    if "非全日制" in text:
        return "非全日制"
    if "全日制" in text:
        return "全日制"
    return ""


def extract_year(text):
    match = re.search(r"(20\d{2})", str(text or ""))
    return match.group(1) if match else ""


def row_matches_material(text):
    return any(term in text for term in MATERIAL_TERMS)


def split_text_lines(text):
    return [normalize_text(line) for line in re.split(r"[\r\n]+|(?<=。)", text) if normalize_text(line)]


def with_attachment_note(content, attachments):
    if not attachments:
        return content
    notes = " ".join(f"附件：{item['title']} {item['url']}" for item in attachments)
    return f"{content} {notes}"


def is_allowed_domain(url):
    domain = urlparse(url).netloc.lower()
    return any(domain == item or domain.endswith(f".{item}") for item in ["iam.njupt.edu.cn", "yzb.njupt.edu.cn", "www.njupt.edu.cn"])


def is_list_page(url):
    lowered = url.lower().split("?")[0]
    return ("list" in lowered or lowered.endswith("/")) and not is_attachment(url)


def is_attachment(url):
    lowered = url.lower().split("?")[0]
    return any(lowered.endswith(ext) for ext in ATTACHMENT_EXTENSIONS)


def source_name(url):
    domain = urlparse(url).netloc.lower()
    if "iam.njupt.edu.cn" in domain:
        return "南京邮电大学材料科学与工程学院"
    if "yzb.njupt.edu.cn" in domain:
        return "南京邮电大学研究生招生信息网"
    if "njupt.edu.cn" in domain:
        return "南京邮电大学官网"
    return domain or "公开网页"


def dedupe_key(item):
    url = normalize_text(item.get("url", ""))
    if url:
        return f"url::{url}"
    return f"text::{item.get('title', '')}::{item.get('content', '')[:120]}"


def structured_key(item, fields):
    return "||".join(normalize_text(item.get(field, "")) for field in fields)


def normalize_record(item, columns):
    return {column: normalize_text(item.get(column, "")) for column in columns}


def normalize_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def summarize(text, limit=320):
    text = normalize_text(text)
    return text if len(text) <= limit else f"{text[:limit]}..."


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sleep_random():
    time.sleep(random.uniform(*REQUEST_INTERVAL))


if __name__ == "__main__":
    main()
