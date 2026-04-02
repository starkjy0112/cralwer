# -*- coding: utf-8 -*-
"""
충주시청 공고/고시/입찰 크롤러
https://www.chungju.go.kr/www/selectEminwonList.do?key=510&ancmt_se_code=01,02,04,05
GET 기반, 10건/페이지 (session 필요 - contents.do 먼저 방문)
"""
import math
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.chungju.go.kr"
CONTENTS_URL = f"{BASE_URL}/www/contents.do?key=510"
LIST_URL = f"{BASE_URL}/www/selectEminwonList.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "충주시청"


class ChungjuCrawler:
    """충주시청 공고/고시/입찰 크롤러"""

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
        self._initialized = False

    def _ensure_session(self):
        if not self._initialized:
            self.session.get(CONTENTS_URL, timeout=30)
            self._initialized = True

    def _fetch_page(self, keyword, page):
        self._ensure_session()
        params = {
            "key": "510",
            "ofr_pageSize": "10",
            "ancmt_se_code": "01,02,04,05",
            "pageIndex": str(page),
            "searchCnd": "all",
        }
        if keyword:
            params["searchKrwd"] = keyword
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
            number = tds[0].get_text(strip=True).replace(",", "")
            if not total_count and page == 1 and number.isdigit():
                total_count = int(number)

            gosi_no = tds[1].get_text(strip=True)
            a_tag = tds[2].find("a")
            if not a_tag:
                continue
            title_text = a_tag.get_text(strip=True)
            title = f"[{gosi_no}] {title_text}" if gosi_no else title_text

            href = a_tag.get("href", "")
            if href.startswith("./"):
                href = f"{BASE_URL}/www/{href[2:]}"
            elif href.startswith("/"):
                href = f"{BASE_URL}{href}"

            dept = tds[3].get_text(strip=True)
            date = tds[4].get_text(strip=True).replace(".", "-") if len(tds) > 4 else ""

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": href,
                "organization": f"{ORGANIZATION_NAME} ({dept})" if dept else ORGANIZATION_NAME,
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
        print(f"[{ORGANIZATION_NAME} 공고/고시/입찰] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = ChungjuCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n=== '용역' 검색 ===")
    results2 = crawler.search("용역", max_pages=1)
    for r in results2[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n공고: {len(results)}건, 용역: {len(results2)}건")
