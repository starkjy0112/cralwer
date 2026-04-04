# -*- coding: utf-8 -*-
"""
양산시청 입찰공고 크롤러
https://www.yangsan.go.kr/portal/saeol/gosi/list.do?seCode=02&mid=0102020000
POST 기반, table.bod_list, 10건/페이지, page 파라미터
서버사이드 키워드 검색 미지원 → 클라이언트 필터링
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.yangsan.go.kr"
LIST_URL = f"{BASE_URL}/portal/saeol/gosi/list.do"
MID = "0102020000"
SE_CODE = "02"
PAGE_SIZE = 10
ORGANIZATION_NAME = "양산시청"


class YangsanBidCrawler:
    """양산시청 입찰공고 크롤러"""

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

    def _fetch_page(self, page):
        data = {
            "page": str(page),
            "pageSize": str(PAGE_SIZE),
            "seCode": SE_CODE,
        }
        resp = self.session.post(
            f"{LIST_URL}?seCode={SE_CODE}&mid={MID}",
            data=data, timeout=15, verify=False,
        )
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []

        table = soup.select_one("table.bod_list")
        if not table:
            return items, total_count

        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else []
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue

            number = tds[0].get_text(strip=True)
            if not total_count and number.isdigit():
                total_count = int(number)

            gosi_no = tds[1].get_text(strip=True)
            a_tag = tds[2].find("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)

            data_action = a_tag.get("data-action", "")
            if data_action:
                detail_url = f"{BASE_URL}{data_action}"
            else:
                detail_url = f"{LIST_URL}?seCode={SE_CODE}&mid={MID}"

            dept = tds[3].get_text(strip=True)
            date_str = tds[4].get_text(strip=True).replace(".", "-")

            items.append({
                "number": number,
                "title": f"[{gosi_no}] {title}" if gosi_no else title,
                "date": date_str,
                "url": detail_url,
                "organization": ORGANIZATION_NAME,
            })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10):
        first_items, total_count = self._fetch_page(1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 {total_count}건)")

        if actual_pages <= 1:
            all_items = first_items
        else:
            page_results = {1: first_items}
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_page, p): p
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

        if keyword:
            all_items = [item for item in all_items if keyword in item["title"]]

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[{ORGANIZATION_NAME} 입찰공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = YangsanBidCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n=== '용역' 검색 ===")
    results2 = crawler.search("용역", max_pages=1)
    for r in results2[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n공고: {len(results)}건, 용역: {len(results2)}건")
