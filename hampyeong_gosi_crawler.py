# -*- coding: utf-8 -*-
"""
함평군청 고시공고 크롤러
https://www.hampyeong.go.kr/pg/GosiList.do?pageId=www273
GET 기반, div.board_list 기반, GosiDetail.do 상세링크, pageIndex 파라미터
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.hampyeong.go.kr"
LIST_URL = f"{BASE_URL}/pg/GosiList.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "함평군청"


class HampyeongGosiCrawler:
    """함평군청 고시공고 크롤러"""

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
            "pageId": "www273",
            "pageIndex": str(page),
            "notAncmtSeCode": "01,02,03,04",
        }
        if keyword:
            params["searchText"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []

        # Board list is div-based with GosiDetail links
        board = soup.select_one("div.board_list_body")
        if not board:
            board = soup.select_one("div.board_list")
        if not board:
            return items, total_count

        links = board.select("a[href*='GosiDetail']")

        # Estimate total from the div.board_list_head text or pagination
        head = soup.select_one("div.board_list_head, div.board_list")
        if head:
            # Try to get first item number as total
            text = head.get_text()
            numbers = re.findall(r'^\d+', text.strip())
            if numbers:
                try:
                    total_count = int(numbers[0])
                except ValueError:
                    pass

        if not total_count:
            total_count = page * PAGE_SIZE if links else 0

        # Parse links - each link is a GosiDetail entry
        # The board_list_body contains rows with: number, gosi_no, title(link), dept, date, views
        all_text = board.get_text()
        # Parse structured data from the div
        # Each row has: seq number, gosi number, title, dept, date, views
        # Links contain the title text
        for link in links:
            href = link.get("href", "")
            title = link.get_text(strip=True)

            # Extract SEQ from href
            seq_match = re.search(r'SEQ=(\d+)', href)
            seq = seq_match.group(1) if seq_match else ""

            detail_url = f"{BASE_URL}{href}" if href.startswith("/") else href

            items.append({
                "number": seq,
                "title": title,
                "date": "",
                "url": detail_url,
                "organization": ORGANIZATION_NAME,
            })

        # Try to extract dates from the full board text
        # The text is structured as: number gosi_no title dept date views
        date_pattern = re.compile(r'(\d{4}-\d{2}-\d{2})')
        dates = date_pattern.findall(board.get_text())
        for i, item in enumerate(items):
            if i < len(dates):
                item["date"] = dates[i]

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 약 {total_count}건)")
        if actual_pages <= 1:
            all_items = first_items
        else:
            page_results = {1: first_items}
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {executor.submit(self._fetch_page, keyword, p): p for p in range(2, actual_pages + 1)}
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
        print(f"[{ORGANIZATION_NAME} 고시공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = HampyeongGosiCrawler()
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
