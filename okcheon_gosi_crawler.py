# -*- coding: utf-8 -*-
"""
옥천군청 고시/공고 크롤러
https://www.oc.go.kr/www/selectBbsNttList.do?bbsNo=40&key=236
GET 기반, 10건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.oc.go.kr"
LIST_URL = f"{BASE_URL}/www/selectBbsNttList.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "옥천군청"


class OkcheonGosiCrawler:
    """옥천군청 고시/공고 크롤러"""

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
        params = {
            "key": "236",
            "bbsNo": "40",
            "pageIndex": str(page),
            "searchCnd": "SJ",
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
            # Columns: 고시공고번호, 제목, 담당부서, 등록일, 조회수, 첨부
            gosi_no = tds[0].get_text(strip=True)
            a_tag = tds[1].find("a")
            if not a_tag:
                continue
            title_text = a_tag.get_text(strip=True)
            title = f"[{gosi_no}] {title_text}" if gosi_no else title_text

            href = a_tag.get("href", "")
            if href.startswith("./"):
                href = f"{BASE_URL}/www/{href[2:]}"
            elif href.startswith("/"):
                href = f"{BASE_URL}{href}"

            dept = tds[2].get_text(strip=True)
            date = tds[3].get_text(strip=True).replace(".", "-")

            # Extract number from gosi_no or use order
            number = ""
            if gosi_no:
                m = re.search(r"(\d+)호", gosi_no)
                if m:
                    number = m.group(1)

            items.append({
                "number": number or gosi_no,
                "title": title,
                "date": date,
                "url": href,
                "organization": f"{ORGANIZATION_NAME} ({dept})" if dept else ORGANIZATION_NAME,
            })

        if not total_count and items:
            # Estimate from pagination
            paging = soup.select(".pagination a, .paging a")
            max_page = 1
            for a in paging:
                href = a.get("href", "")
                m = re.search(r"pageIndex=(\d+)", href)
                if m:
                    p = int(m.group(1))
                    if p > max_page:
                        max_page = p
            total_count = max_page * PAGE_SIZE

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
        print(f"[{ORGANIZATION_NAME} 고시/공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = OkcheonGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n=== '용역' 검색 ===")
    results2 = crawler.search("용역", max_pages=1)
    for r in results2[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n공고: {len(results)}건, 용역: {len(results2)}건")
