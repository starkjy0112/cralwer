# -*- coding: utf-8 -*-
"""
공주시청 입찰공고 크롤러
https://www.gongju.go.kr/prog/saeolGosi/GOSI_02/sub04_03_02/list.do
POST 기반, pageIndex/searchKeyword 검색, 10건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.gongju.go.kr"
LIST_URL = f"{BASE_URL}/prog/saeolGosi/GOSI_02/sub04_03_02/list.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "공주시청"


class GongjuBidCrawler:
    """공주시청 입찰공고 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
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
        self._csrf = None

    def _get_csrf(self):
        """CSRF 토큰 획득"""
        if self._csrf:
            return self._csrf
        resp = self.session.get(LIST_URL, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")
        meta = soup.find("meta", attrs={"name": "_csrf"})
        if meta:
            self._csrf = meta.get("content", "")
        return self._csrf or ""

    def _fetch_page(self, keyword, page):
        data = {
            "pageIndex": str(page),
            "searchCondition": "notAncmtSj",
            "searchKeyword": keyword or "",
        }

        resp = self.session.post(LIST_URL, data=data, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []
        table = soup.find("table")
        if table:
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 5:
                    continue
                number = tds[0].get_text(strip=True)
                if not total_count and number.isdigit():
                    total_count = int(number)
                gosi_no = tds[1].get_text(strip=True)
                title_td = tds[2]
                title_tag = title_td.find("a")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                href = title_tag.get("href", "")
                if href and href.startswith("/"):
                    detail_url = BASE_URL + href
                elif href == "#":
                    detail_url = ""
                else:
                    detail_url = href
                dept = tds[3].get_text(strip=True)
                date = tds[4].get_text(strip=True)
                period = tds[5].get_text(strip=True) if len(tds) > 5 else ""

                items.append({
                    "number": number,
                    "title": f"[{gosi_no}] {title}" if gosi_no else title,
                    "date": date,
                    "url": detail_url,
                    "organization": ORGANIZATION_NAME,
                })

        return items, total_count

    WORKERS = 20

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
        print(f"[{ORGANIZATION_NAME}] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = GongjuBidCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
