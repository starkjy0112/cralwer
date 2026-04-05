# -*- coding: utf-8 -*-
"""
영광군청 고시공고 크롤러
https://www.yeonggwang.go.kr/bbs/?b_id=gosigonggo&site=headquarter_new&mn=9059&type=lists
GET 기반, table 7열 (번호/고시번호/제목/부서/기간/등록일/조회), 페이지 파라미터
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.yeonggwang.go.kr"
LIST_URL = f"{BASE_URL}/bbs/"
PAGE_SIZE = 10
ORGANIZATION_NAME = "영광군청"


class YeonggwangCrawler:
    """영광군청 고시공고 크롤러"""

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
            "b_id": "gosigonggo",
            "site": "headquarter_new",
            "mn": "9059",
            "type": "lists",
            "page": str(page),
        }
        if keyword:
            params["sc_key"] = "subject"
            params["sc_word"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        # First row number indicates total
        table = soup.select_one("table")
        if not table:
            return [], total_count

        rows = table.select("tbody tr") or table.select("tr")[1:]
        if rows:
            first_num = rows[0].select_one("td")
            if first_num:
                try:
                    total_count = int(first_num.get_text(strip=True))
                except ValueError:
                    pass

        items = []
        for row in rows:
            cells = row.select("td")
            if len(cells) < 6:
                continue
            number = cells[0].get_text(strip=True)
            gosi_no = cells[1].get_text(strip=True)
            title_cell = cells[2]
            dept = cells[3].get_text(strip=True)
            period = cells[4].get_text(strip=True)
            date = cells[5].get_text(strip=True)

            link = title_cell.select_one("a")
            title = link.get_text(strip=True) if link else title_cell.get_text(strip=True)
            href = link.get("href", "") if link else ""

            if href.startswith("?"):
                detail_url = f"{LIST_URL}{href}"
            elif href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            elif href.startswith("http"):
                detail_url = href
            else:
                detail_url = LIST_URL

            display_title = f"[{gosi_no}] {title}" if gosi_no else title

            items.append({"number": number, "title": display_title, "date": date, "url": detail_url, "organization": dept or ORGANIZATION_NAME})
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
        print(f"[{ORGANIZATION_NAME}] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = YeonggwangCrawler()
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
