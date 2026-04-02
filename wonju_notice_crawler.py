# -*- coding: utf-8 -*-
"""
원주시청 새소식 크롤러
https://www.wonju.go.kr/www/selectBbsNttList.do?bbsNo=1&key=211
GET 기반, 10건/페이지, table.p-table.simple
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.wonju.go.kr"
LIST_URL = f"{BASE_URL}/www/selectBbsNttList.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "원주시청"


class WonjuNoticeCrawler:
    """원주시청 새소식 크롤러"""

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
            "key": "211",
            "bbsNo": "1",
            "searchCnd": "SJ",
            "pageIndex": str(page),
        }
        if keyword:
            params["searchKrwd"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15, verify=False)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        em = soup.select_one(".em_black")
        if em:
            try:
                total_count = int(em.get_text(strip=True).replace(",", ""))
            except ValueError:
                pass

        items = []
        table = soup.select_one("table.p-table")
        if not table:
            return items, total_count

        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 6:
                continue
            # 번호, 제목, 작성자, 파일, 조회수, 작성일
            number = tds[0].get_text(strip=True)
            if not total_count and number.isdigit():
                total_count = int(number)
            a_tag = tds[1].find("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            href = a_tag.get("href", "")
            if href.startswith("./"):
                detail_url = f"{BASE_URL}/www/{href[2:]}"
            elif href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href
            dept = tds[2].get_text(strip=True)
            date_str = tds[5].get_text(strip=True).replace(".", "-")

            items.append({
                "number": number,
                "title": title,
                "date": date_str,
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
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = WonjuNoticeCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n=== '용역' 검색 ===")
    results2 = crawler.search("용역", max_pages=1)
    for r in results2[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n공고: {len(results)}건, 용역: {len(results2)}건")
