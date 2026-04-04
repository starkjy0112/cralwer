# -*- coding: utf-8 -*-
"""
함평군청 공지사항 크롤러
https://www.hampyeong.go.kr/boardList.do?boardId=NOTICE&pageId=www272
GET 기반, div.board_list 기반, boardView.do 상세링크, movePage 파라미터
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.hampyeong.go.kr"
LIST_URL = f"{BASE_URL}/boardList.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "함평군청"


class HampyeongNoticeCrawler:
    """함평군청 공지사항 크롤러"""

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
            "boardId": "NOTICE",
            "pageId": "www272",
            "movePage": str(page),
            "recordCnt": "10",
        }
        if keyword:
            params["searchQuery"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []

        # Board list with boardView links
        board = soup.select_one("div.board_list_body") or soup.select_one("div.board_list")
        if not board:
            return items, total_count

        links = board.select("a[href*='boardView']")
        if not total_count:
            max_page = 1
            for a in soup.select("a[href*='movePage=']"):
                m = re.search(r'movePage=(\d+)', a.get("href", ""))
                if m:
                    max_page = max(max_page, int(m.group(1)))
            total_count = max_page * PAGE_SIZE

        for link in links:
            href = link.get("href", "")
            title = link.get_text(strip=True)
            if not title:
                continue

            # Remove file/attachment text markers
            title = re.sub(r'파일$', '', title).strip()
            title = re.sub(r'NEW$', '', title).strip()

            seq_match = re.search(r'seq=(\d+)', href)
            seq = seq_match.group(1) if seq_match else ""

            detail_url = f"{BASE_URL}{href}" if href.startswith("/") else href

            items.append({
                "number": seq,
                "title": title,
                "date": "",
                "url": detail_url,
                "organization": ORGANIZATION_NAME,
            })

        # Extract dates
        date_pattern = re.compile(r'(\d{4}-\d{2}-\d{2})')
        if board:
            dates = date_pattern.findall(board.get_text())
            for i, item in enumerate(items):
                if i < len(dates):
                    item["date"] = dates[i]

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10):
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
        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[{ORGANIZATION_NAME} 공지사항] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = HampyeongNoticeCrawler()
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
