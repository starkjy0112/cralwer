# -*- coding: utf-8 -*-
"""
광주광역시도시공사 통합검색 크롤러
https://www.gmcc.co.kr/findeepSearch.es?mid=a10603000000
GET 기반, 5건/페이지, allKeyWord 검색
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.gmcc.co.kr"
LIST_URL = f"{BASE_URL}/findeepSearch.es"
PAGE_SIZE = 5
ORGANIZATION_NAME = "광주광역시도시공사"


class GMCCCrawler:
    """광주광역시도시공사 통합검색 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _fetch_page(self, keyword, page):
        params = {
            "mid": "a10603000000",
            "allKeyWord": keyword if keyword else "",
            "nPage": str(page),
        }

        resp = self.session.get(LIST_URL, params=params, timeout=60)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        counts = re.findall(r'총\s*([\d,]+)', resp.text)
        for c_str in counts:
            total_count += int(c_str.replace(",", ""))

        items = []
        lists = soup.select("ul.list")
        if len(lists) > 1:
            result_list = lists[1]
            for li in result_list.select("li"):
                a = li.find("a")
                if not a:
                    continue

                title = a.get_text(strip=True)
                href = a.get("href", "")
                if href and not href.startswith("http"):
                    href = f"{BASE_URL}{href}"

                date = ""
                dm = re.search(r'(\d{4}-\d{2}-\d{2})', li.get_text())
                if dm:
                    date = dm.group(1)

                items.append({
                    "number": "",
                    "title": title,
                    "date": date,
                    "url": href,
                    "organization": ORGANIZATION_NAME,
                })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 {total_count}건)")

        if actual_pages <= 1:
            all_items = first_items
        else:
            page_results = {1: first_items}
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_page, keyword, p): p
                    for p in range(2, actual_pages + 1)
                }
                for future in as_completed(futures):
                    p = futures[future]
                    try:
                        items, _ = future.result()
                        if items:
                            page_results[p] = items
                    except Exception:
                        pass

            all_items = []
            for p in sorted(page_results.keys()):
                all_items.extend(page_results[p])

        # 날짜 필터 (기본: 최근 30일)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        filtered = []
        for item in all_items:
            d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
            if not d:
                continue
            if start_date <= d <= end_date:
                filtered.append(item)
        all_items = filtered

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[{ORGANIZATION_NAME}] 완료: 총 {len(all_items)}건")
        return all_items
