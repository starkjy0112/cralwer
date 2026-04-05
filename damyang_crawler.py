# -*- coding: utf-8 -*-
"""
담양군청 고시/공고 크롤러
https://www.damyang.go.kr/eminwon/searchList?domainId=DOM_0000001&contentsSid=2&menuCd=DOM_000000190001002001&boardType=special&listType=01
AJAX JSON API 기반 (/eminwon/getSearchList), 10건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.damyang.go.kr"
API_URL = f"{BASE_URL}/eminwon/getSearchList"
DETAIL_URL = f"{BASE_URL}/eminwon/searchDetail?notAncmtMgtNo="
PAGE_SIZE = 10
ORGANIZATION_NAME = "담양군청"


class DamyangCrawler:
    """담양군청 고시/공고 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
        })
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.verify = False

    def _fetch_page(self, keyword, page):
        params = {
            "domainId": "DOM_0000001",
            "contentsSid": "2",
            "listType": "01,02,03,04",
            "listGubun": "",
            "currentPageNo": str(page),
            "pageCnt": str(PAGE_SIZE),
        }
        if keyword:
            params["searchKey"] = "sch_sco1"
            params["searchVal"] = keyword

        resp = self.session.get(API_URL, params=params, timeout=15)
        data = resp.json()

        total_count = 0
        items = []

        rslt = data.get("RSLT_DATA", {})
        sl = rslt.get("searchList", {})
        if not sl:
            return items, total_count

        total_count = int(sl.get("PG_TOT_CNT", 0) or 0)
        item_list = sl.get("dataMap", [])

        for item in item_list:
            mgt_no = str(item.get("col0", "")).strip()
            number = str(item.get("col1", "")).strip()
            gosi_no = str(item.get("col2", "")).strip()
            title = str(item.get("col3", "")).strip()
            dept = str(item.get("col4", "")).strip()
            date = str(item.get("col5", "")).strip()

            # 서버 검색이 미지원이므로 클라이언트 필터링
            if keyword and keyword not in title:
                continue

            detail_link = f"{DETAIL_URL}{mgt_no}" if mgt_no else BASE_URL

            display_title = f"[{gosi_no}] {title}" if gosi_no else title

            items.append({
                "number": number,
                "title": display_title,
                "date": date,
                "url": detail_link,
                "organization": dept if dept else ORGANIZATION_NAME,
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

    crawler = DamyangCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
