# -*- coding: utf-8 -*-
"""
경상북도청 고시공고 크롤러
https://www.gb.go.kr/Main/page.do?mnu_uid=6789&LARGE_CODE=720&MEDIUM_CODE=50&SMALL_CODE=10&SMALL_CODE2=30
GET 기반, 10건/페이지, Start 오프셋 방식
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.gb.go.kr"
LIST_URL = f"{BASE_URL}/Main/page.do"
PAGE_SIZE = 10


class GBGosiCrawler:
    """경상북도청 고시공고 크롤러"""

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

    def _fetch_page(self, keyword, page, start_date=None, end_date=None):
        start = (page - 1) * PAGE_SIZE
        params = {
            "mnu_uid": "6789",
            "BD_CODE": "gosi_notice",
            "cmd": "1",
            "Start": start,
        }
        if keyword:
            params["key"] = "2"       # 제목 검색
            params["word"] = keyword
        if start_date and end_date:
            params["period"] = "1"
            params["B_START"] = start_date
            params["B_END"] = end_date
            params["bdName"] = "알림마당"
            params["p1"] = "0"
            params["p2"] = "0"
            params["dept_name"] = ""
            params["dept_code"] = ""
            params["CSRF_TOKEN"] = ""

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        html = resp.text
        soup = BeautifulSoup(html, "lxml")

        # 총 건수: "총 게시물 16776건" (HTML 주석 내부에 있음)
        total_count = 0
        m = re.search(r'총\s*게시물\s*<em>(\d[\d,]*)</em>', html)
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        table = soup.select_one("table.bbsList")
        if not table:
            return items, total_count

        rows = table.select("tbody tr") or table.select("tr")[1:]
        for row in rows:
            num_cell = row.select_one("td.b_number")
            subj_cell = row.select_one("td.b_subject")
            author_cell = row.select_one("td.b_author")
            date_cell = row.select_one("td.b_date")

            if not subj_cell:
                continue

            number = num_cell.get_text(strip=True) if num_cell else ""
            date = date_cell.get_text(strip=True) if date_cell else ""
            author = author_cell.get_text(strip=True) if author_cell else "경상북도청"

            link = subj_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")
            if href.startswith("./"):
                detail_url = f"{BASE_URL}/Main/{href[2:]}"
            elif href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "경상북도청",
            })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
        first_items, total_count = self._fetch_page(keyword, 1, start_date, end_date)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 {total_count}건)")

        if actual_pages <= 1:
            all_items = first_items
        else:
            page_results = {1: first_items}
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_page, keyword, p, start_date, end_date): p
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

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[경상북도청 고시공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = GBGosiCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
