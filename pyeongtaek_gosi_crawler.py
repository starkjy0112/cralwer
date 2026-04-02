# -*- coding: utf-8 -*-
"""
평택시청 고시공고 크롤러
https://www.pyeongtaek.go.kr/pyeongtaek/saeol/gosi/list.do?mid=0401020100
GET 기반, 10건/페이지
컬럼: 번호, 고시공고번호, 제목, 담당부서, 등록일
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.pyeongtaek.go.kr"
LIST_URL = f"{BASE_URL}/pyeongtaek/saeol/gosi/list.do"
PAGE_SIZE = 10


class PyeongtaekGosiCrawler:
    """평택시청 고시공고 크롤러"""

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
            "mid": "0401020100",
            "seCode": "01",
            "pageIndex": page,
        }
        if keyword:
            params["searchType"] = "NOT_ANCMT_SJ"
            params["searchTxt"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        html = resp.text
        soup = BeautifulSoup(html, "lxml")

        # 총 건수: goPage() 최대값에서 추출
        total_count = 0
        pages = re.findall(r'goPage\((\d+)\)', html)
        if pages:
            max_page = max(int(p) for p in pages)
            total_count = max_page * PAGE_SIZE

        items = []
        table = soup.select_one("table.tableSt_list") or soup.select_one("table.tbl_gosi") or soup.select_one("table")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        if not rows:
            rows = table.select("tr")[1:]

        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            # 번호, 고시공고번호, 제목, 담당부서, 등록일
            number = cells[0].get_text(strip=True)
            title_cell = cells[2]
            dept = cells[3].get_text(strip=True)
            date = cells[4].get_text(strip=True)

            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)

            # req.post(this) - uses form submission, link is just #
            # Detail URL constructed from the row number
            detail_url = f"{LIST_URL}?mid=0401020100&seCode=01"

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "평택시청",
            })

        return items, total_count

    WORKERS = 50

    def search(self, keyword="", max_pages=10):
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

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[평택시청 고시공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = PyeongtaekGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
