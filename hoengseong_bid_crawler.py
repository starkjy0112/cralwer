# -*- coding: utf-8 -*-
"""
횡성군청 입찰공고 크롤러
https://gyeyak.hsg.go.kr/bid
계약정보공개시스템 (hanayo iframe)
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://gyeyak.hsg.go.kr"
LIST_URL = f"{BASE_URL}/bid"
PAGE_SIZE = 10
ORGANIZATION_NAME = "횡성군청"


class HoengseongBidCrawler:
    """횡성군청 입찰공고 크롤러 (계약정보공개시스템)"""

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

    def _fetch_page(self, keyword, page):
        params = {"page": str(page)}
        if keyword:
            params["search"] = keyword
        resp = self.session.get(LIST_URL, params=params, timeout=30)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_count
        tbody = table.select_one("tbody")
        if not tbody:
            return items, total_count
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            number = tds[0].get_text(strip=True)
            if not total_count and page == 1 and number.isdigit():
                total_count = int(number)

            a_tag = tr.find("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            href = a_tag.get("href", "")
            if href and not href.startswith("http"):
                href = f"{BASE_URL}{href}" if href.startswith("/") else f"{BASE_URL}/{href}"

            date = ""
            for td in tds:
                text = td.get_text(strip=True)
                if re.match(r"\d{4}[-./]\d{2}[-./]\d{2}", text):
                    date = text.replace(".", "-")
                    break

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": href or LIST_URL,
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
        print(f"[{ORGANIZATION_NAME} 입찰공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = HoengseongBidCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n=== '용역' 검색 ===")
    results2 = crawler.search("용역", max_pages=1)
    for r in results2[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n공고: {len(results)}건, 용역: {len(results2)}건")
