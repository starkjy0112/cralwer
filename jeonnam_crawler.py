# -*- coding: utf-8 -*-
"""
전라남도청 고시/공고 크롤러
https://www.jeonnam.go.kr/J0203/boardList.do?menuId=jeonnam0203000000
GET 기반, 10건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.jeonnam.go.kr"
LIST_URL = f"{BASE_URL}/J0203/boardList.do"
PAGE_SIZE = 10


class JeonnamNotCrawler:
    """전라남도청 고시/공고 크롤러"""

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
            "menuId": "jeonnam0203000000",
            "boardId": "J0203",
            "pageIndex": page,
        }
        if keyword:
            params["searchType"] = "0"  # 제목
            params["searchText"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 총 건수: 페이지네이션에서 마지막 페이지 번호로 추정
        total_count = 0
        # 마지막 페이지 링크에서 총 페이지 수 추출
        page_links = soup.select("a[href*='pageIndex=']")
        max_page = 1
        for link in page_links:
            href = link.get("href", "")
            m = re.search(r'pageIndex=(\d+)', href)
            if m:
                p = int(m.group(1))
                if p > max_page:
                    max_page = p
        total_count = max_page * PAGE_SIZE  # 근사치

        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        if not rows:
            rows = table.select("tr")[1:]

        for row in rows:
            cells = row.select("td")
            if len(cells) < 4:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            author = cells[2].get_text(strip=True) if len(cells) >= 3 else "전라남도청"
            date = cells[3].get_text(strip=True) if len(cells) >= 4 else ""

            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            # 제목에서 NEW, 날짜 등 불필요한 텍스트 제거
            title = re.sub(r'NEW\d{4}-\d{2}-\d{2}$', '', title).strip()
            title = re.sub(r'NEW$', '', title).strip()

            href = link.get("href", "")
            if href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": author if author else "전라남도청",
            })

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
        print(f"[전라남도청] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = JeonnamNotCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
