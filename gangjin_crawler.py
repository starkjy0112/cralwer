# -*- coding: utf-8 -*-
"""
강진군청 고시/공고 크롤러
https://www.gangjin.go.kr/www/government/notice/gosi
GET 기반, 15건/페이지, page 파라미터
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.gangjin.go.kr"
LIST_PATH = "/www/government/notice/gosi"
LIST_URL = f"{BASE_URL}{LIST_PATH}"
PAGE_SIZE = 15
ORGANIZATION_NAME = "강진군청"


class GangjinCrawler:
    """강진군청 고시/공고 크롤러"""

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
        params = {"page": str(page)}
        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        page_links = soup.select('a[href*="page="]')
        max_page = 1
        for a in page_links:
            href = a.get("href", "")
            m = re.search(r'page=(\d+)', href)
            if m:
                p = int(m.group(1))
                if p > max_page:
                    max_page = p
        total_count = max_page * PAGE_SIZE

        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        if not rows:
            rows = table.select("tr")[1:]

        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            dept = cells[2].get_text(strip=True) if len(cells) >= 3 else ORGANIZATION_NAME
            date = cells[3].get_text(strip=True) if len(cells) >= 4 else ""

            link = title_cell.select_one("a")
            if link:
                title = link.get_text(strip=True)
                href = link.get("href", "")
            else:
                title = title_cell.get_text(strip=True)
                href = ""

            title = re.sub(r'새로운글$', '', title).strip()

            if href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            elif href.startswith("http"):
                detail_url = href
            else:
                detail_url = LIST_URL

            if keyword and keyword not in title:
                continue

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": dept if dept else ORGANIZATION_NAME,
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
        print(f"[{ORGANIZATION_NAME}] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = GangjinCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
