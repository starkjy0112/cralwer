# -*- coding: utf-8 -*-
"""
전북특별자치도청 전북공고 크롤러
https://www.jeonbuk.go.kr/board/list.jeonbuk?menuCd=DOM_000000102002005000&boardId=BBS_0000129
GET 기반, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.jeonbuk.go.kr"
LIST_URL = f"{BASE_URL}/board/list.jeonbuk"
PAGE_SIZE = 100


class JeonbukCrawler:
    """전북특별자치도청 전북공고 크롤러"""

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
            "boardId": "BBS_0000129",
            "menuCd": "DOM_000000102002005000",
            "listCel": "1",
            "listRow": PAGE_SIZE,
            "searchType": "DATA_TITLE",
            "paging": "ok",
            "startPage": page,
        }
        if keyword:
            params["keyword"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 총 건수: "총 13070건(1/1307 페이지)"
        total_count = 0
        total_el = soup.select_one("p.bbs_total")
        if total_el:
            m = re.search(r'총\s*(\d[\d,]*)\s*건', total_el.get_text())
            if m:
                total_count = int(m.group(1).replace(",", ""))

        items = []
        table = soup.select_one("table.bbs_table")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 6:
                continue

            number = cells[0].get_text(strip=True)
            # 구분(공고/고시), 고시/공고 번호, 제목, 부서명, 작성일, 조회
            title_cell = cells[3]
            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")
            if href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href

            date = cells[5].get_text(strip=True)

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "전북특별자치도청",
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
        print(f"[전북특별자치도청 전북공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = JeonbukCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
