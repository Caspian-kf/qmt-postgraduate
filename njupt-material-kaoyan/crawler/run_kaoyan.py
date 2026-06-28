import json
import random
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


SCHOOL = "南京邮电大学"
COLLEGE = "材料科学与工程学院"
MAJOR = "材料科学与工程"

TIMEOUT = 10
MIN_INTERVAL = 2
MAX_INTERVAL = 5
MAX_TOTAL_ITEMS = 200
MIN_TARGET_ITEMS = 50
MAX_CANDIDATE_PAGES = 160

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
JSON_PATH = DATA_DIR / "kaoyan_materials.json"
CSV_PATH = DATA_DIR / "kaoyan_materials.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

PUBLIC_SEED_URLS = [
    "https://iam.njupt.edu.cn/",
    "https://iam.njupt.edu.cn/10962/list.htm",
    "https://iam.njupt.edu.cn/10962/listm.htm",
    "https://yzb.njupt.edu.cn/",
    "https://yzb.njupt.edu.cn/7795/list.htm",
    "https://yzb.njupt.edu.cn/7797/list.htm",
    "https://yzb.njupt.edu.cn/7798/list.htm",
    "https://yzb.njupt.edu.cn/7799/list.htm",
]

SEARCH_KEYWORDS = [
    "南京邮电大学 材料 考研",
    "南京邮电大学 材料科学与工程 硕士研究生",
    "南京邮电大学 材料科学与工程学院 复试",
    "南京邮电大学 材料科学与工程学院 考试大纲",
    "南京邮电大学 材料 拟录取",
    "南京邮电大学 材料 调剂",
    "南京邮电大学 材料 专业目录",
    "南京邮电大学 材料 参考书目",
]

RELATED_TERMS = [
    "南京邮电大学",
    "南邮",
    "材料",
    "材料科学与工程",
    "硕士",
    "研究生",
    "招生",
    "考研",
    "复试",
    "拟录取",
    "综合成绩",
    "调剂",
    "专业目录",
    "大纲",
    "参考书目",
]

CAPTCHA_TERMS = ["验证码", "安全验证", "访问过于频繁", "人机验证", "captcha"]

COLUMNS = [
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


def main():
    start_time = time.time()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("启动南京邮电大学材料考研公开信息采集")
    print("合规说明：只采集公开网页，遇到登录、验证码、403、429 将跳过。")
    print("关键词：")
    for keyword in SEARCH_KEYWORDS:
        print(f"- {keyword}")

    records = load_existing_records()
    existing_keys = {build_dedupe_key(item) for item in records}
    initial_total = len(records)
    newly_added = 0

    candidate_urls = discover_candidate_urls(PUBLIC_SEED_URLS)
    print(f"候选 URL 数量：{len(candidate_urls)}")

    for url in candidate_urls:
        if len(records) >= MAX_TOTAL_ITEMS:
            print(f"已达到本版本采集上限 {MAX_TOTAL_ITEMS} 条，停止采集。")
            break

        print(f"\n当前采集来源：{get_source_name(url)}")
        print(f"当前 URL：{url}")

        try:
            item = crawl_article(url)
            if not item:
                print("失败原因：页面为空、无关或不符合采集边界")
                continue

            key = build_dedupe_key(item)
            if key in existing_keys:
                print(f"当前标题：{item['title']}")
                print("失败原因：重复数据，已跳过")
                continue

            records.append(item)
            existing_keys.add(key)
            newly_added += 1

            print(f"当前标题：{item['title']}")
            print(f"当前累计数量：{len(records)}")

            if newly_added % 20 == 0:
                save_records(records)
                print("已新增 20 条，执行阶段性保存。")
        except Exception as exc:
            print(f"失败原因：{exc}")

    save_records(records)
    elapsed = time.time() - start_time
    category_counts = Counter(item.get("category", "其他") for item in records)

    print("\n采集结束")
    print(f"本次新增数量：{newly_added}")
    print(f"总数据量：{len(records)}")
    print("各 category 数量：")
    for category, count in category_counts.most_common():
        print(f"- {category}: {count}")
    print(f"JSON 保存路径：{JSON_PATH}")
    print(f"CSV 保存路径：{CSV_PATH}")
    print(f"总耗时：{elapsed:.2f} 秒")

    if len(records) < MIN_TARGET_ITEMS:
        print(f"提示：当前总量少于 {MIN_TARGET_ITEMS} 条，可补充更多公开列表页到 PUBLIC_SEED_URLS 后继续采集。")


def load_existing_records():
    if not JSON_PATH.exists():
        return []

    try:
        with JSON_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, list):
            return [normalize_record(item) for item in data if isinstance(item, dict)]
    except Exception as exc:
        print(f"读取已有 JSON 失败，将从空数据开始：{exc}")
    return []


def save_records(records):
    cleaned = [normalize_record(item) for item in records]

    with JSON_PATH.open("w", encoding="utf-8") as file:
        json.dump(cleaned, file, ensure_ascii=False, indent=2)

    df = pd.DataFrame(cleaned, columns=COLUMNS)
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")


def discover_candidate_urls(seed_urls):
    visited = set()
    queued = list(dict.fromkeys(seed_urls))
    candidates = []

    while queued and len(visited) < MAX_CANDIDATE_PAGES and len(candidates) < MAX_TOTAL_ITEMS * 2:
        url = queued.pop(0)
        if url in visited or not is_allowed_domain(url):
            continue

        visited.add(url)
        print(f"\n当前采集来源：{get_source_name(url)}")
        print(f"当前 URL：{url}")
        print("当前标题：列表页/入口页")

        html = fetch_html(url)
        if not html:
            print("失败原因：入口页读取失败或被跳过")
            continue

        soup = BeautifulSoup(html, "lxml")
        for link_url, link_title in extract_links(soup, url):
            if not is_allowed_domain(link_url) or link_url in visited:
                continue

            if is_list_page(link_url) and link_url not in queued:
                queued.append(link_url)

            if is_related_text(f"{link_title} {link_url}") and link_url not in candidates:
                candidates.append(link_url)

        print(f"当前累计数量：候选 {len(candidates)}")

    return candidates[: MAX_TOTAL_ITEMS * 2]


def crawl_article(url):
    html = fetch_html(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")
    title = extract_title(soup)
    content = extract_content(soup)
    combined = f"{title} {content}"

    if not title or not is_related_text(combined):
        return None

    return normalize_record(
        {
            "school": SCHOOL,
            "college": COLLEGE,
            "major": MAJOR,
            "category": classify_category(title),
            "title": title,
            "content": summarize(content),
            "publish_time": extract_publish_time(soup, content),
            "url": url,
            "source": get_source_name(url),
            "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


def fetch_html(url):
    sleep_random()
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as exc:
        print(f"失败原因：请求异常 {exc}")
        return None

    if response.status_code in {403, 429}:
        print(f"失败原因：HTTP {response.status_code}，按合规要求跳过")
        return None

    if response.status_code >= 400:
        print(f"失败原因：HTTP {response.status_code}")
        return None

    response.encoding = response.apparent_encoding or response.encoding
    text = response.text
    lowered = text.lower()
    if any(term.lower() in lowered for term in CAPTCHA_TERMS):
        print("失败原因：疑似验证码或访问限制页面，按合规要求跳过")
        return None

    return text


def extract_links(soup, base_url):
    links = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        text = normalize_text(anchor.get_text(" ", strip=True))
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue

        absolute_url = urljoin(base_url, href)
        parsed = urlparse(absolute_url)
        clean_url = parsed._replace(fragment="").geturl()
        if clean_url.startswith("http"):
            links.append((clean_url, text))
    return links


def extract_title(soup):
    for selector in ["h1", ".arti_title", ".article-title", ".title", "title"]:
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

    preferred = soup.select_one(".wp_articlecontent, .article, .content, .main, #content")
    if preferred:
        text = preferred.get_text(" ", strip=True)
    else:
        text = soup.get_text(" ", strip=True)
    return normalize_text(text)


def extract_publish_time(soup, content):
    text = " ".join(
        [
            soup.get_text(" ", strip=True)[:1200],
            content[:1200],
        ]
    )
    patterns = [
        r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})",
        r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            year, month, day = match.groups()
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return ""


def classify_category(title):
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
    if "经验" in title or "经验贴" in title:
        return "经验贴"
    return "其他"


def is_related_text(text):
    normalized = normalize_text(text)
    has_school = "南京邮电大学" in normalized or "南邮" in normalized or "njupt" in normalized.lower()
    has_material = "材料" in normalized or "材料科学与工程" in normalized
    has_admission = any(term in normalized for term in RELATED_TERMS)

    if has_material and has_admission:
        return True
    if has_school and has_material:
        return True
    return False


def is_allowed_domain(url):
    domain = urlparse(url).netloc.lower()
    allowed_domains = [
        "iam.njupt.edu.cn",
        "yzb.njupt.edu.cn",
        "www.njupt.edu.cn",
    ]
    return any(domain == item or domain.endswith(f".{item}") for item in allowed_domains)


def is_list_page(url):
    lowered = url.lower()
    return any(flag in lowered for flag in ["list", "index", "page"]) and not lowered.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx"))


def get_source_name(url):
    domain = urlparse(url).netloc.lower()
    if "iam.njupt.edu.cn" in domain:
        return "南京邮电大学材料科学与工程学院"
    if "yzb.njupt.edu.cn" in domain:
        return "南京邮电大学研究生招生信息网"
    if "njupt.edu.cn" in domain:
        return "南京邮电大学官网"
    return domain or "公开网页"


def build_dedupe_key(item):
    url = normalize_text(item.get("url", ""))
    if url:
        return f"url::{url}"
    title = normalize_text(item.get("title", ""))
    content = normalize_text(item.get("content", ""))
    return f"text::{title}::{content[:160]}"


def normalize_record(item):
    return {column: normalize_text(item.get(column, "")) for column in COLUMNS}


def normalize_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def summarize(text, limit=280):
    text = normalize_text(text)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def sleep_random():
    time.sleep(random.uniform(MIN_INTERVAL, MAX_INTERVAL))


if __name__ == "__main__":
    main()
