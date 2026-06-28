import csv
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"
EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "config" / "config.example.json"
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"

OUTPUT_JSON = DATA_DIR / "results.json"
OUTPUT_CSV = DATA_DIR / "results.csv"
LOG_FILE = LOG_DIR / "crawler.log"

FIELDS = ["source", "title", "content", "url", "publish_time", "crawl_time"]


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def load_config():
    config_path = CONFIG_PATH if CONFIG_PATH.exists() else EXAMPLE_CONFIG_PATH
    with config_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def robots_allowed(session, url, user_agent):
    parser = RobotFileParser()
    robots_url = url.rstrip("/") + "/robots.txt"

    try:
        response = session.get(robots_url, timeout=10)
        if response.status_code != 200:
            logging.warning("robots.txt unavailable: %s (%s)", robots_url, response.status_code)
            return True

        parser.parse(response.text.splitlines())
        return parser.can_fetch(user_agent, url)
    except requests.RequestException as error:
        logging.warning("robots.txt check failed: %s", error)
        return True


def fetch_html(session, url, headers, timeout):
    response = session.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return response.text


def parse_items(html, source_name, page_url):
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else ""

    if not title:
        return []

    return [
        {
            "source": source_name,
            "title": title,
            "content": title,
            "url": page_url,
            "publish_time": "",
            "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    ]


def save_results(results):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_JSON.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(results)

    logging.info("saved %s records", len(results))
    logging.info("json: %s", OUTPUT_JSON)
    logging.info("csv: %s", OUTPUT_CSV)


def main():
    setup_logging()
    config = load_config()
    interval = config.get("request_interval_seconds", 2)
    timeout = config.get("timeout_seconds", 10)
    user_agent = config.get("user_agent", "Mozilla/5.0")
    headers = {"User-Agent": user_agent}
    results = []

    with requests.Session() as session:
        for target in config.get("targets", []):
            if not target.get("enabled", False):
                logging.info("skip disabled target: %s", target.get("name", "unnamed"))
                continue

            name = target.get("name", "unnamed")
            url = target.get("url", "")

            if not url:
                logging.warning("skip target with empty url: %s", name)
                continue

            if not robots_allowed(session, url, user_agent):
                logging.warning("robots.txt disallows crawling: %s", url)
                continue

            try:
                logging.info("fetching: %s", url)
                html = fetch_html(session, url, headers, timeout)
                results.extend(parse_items(html, name, url))
            except requests.RequestException as error:
                logging.error("request failed: %s", error)

            time.sleep(interval)

    save_results(results)


if __name__ == "__main__":
    main()
