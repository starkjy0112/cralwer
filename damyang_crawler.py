# -*- coding: utf-8 -*-
"""
담양군청 고시/공고 크롤러
https://www.damyang.go.kr/eminwon/searchList?domainId=DOM_0000001&contentsSid=2&menuCd=DOM_000000190001002001&boardType=special&listType=01
AJAX JSON API 기반 (/eminwon/getSearchList), 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
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

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
        # 날짜 기본값 (최근 30일)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 {total_count}건)")

        all_items = []
        stop = False

        # 첫 페이지 날짜 필터
        for item in first_items:
            d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
            if not d:
                continue
            if d < start_date:
                stop = True
                continue
            if d <= end_date:
                all_items.append(item)

        # 나머지 페이지 순차 수집 + early stop
        if not stop and actual_pages > 1:
            page = 2
            while page <= actual_pages and not stop:
                # 배치 단위로 병렬 수집
                batch_end = min(page + self.WORKERS, actual_pages + 1)
                with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                    futures = {
                        executor.submit(self._fetch_page, keyword, p): p
                        for p in range(page, batch_end)
                    }
                    batch_results = {}
                    for future in as_completed(futures):
                        p = futures[future]
                        try:
                            items, _ = future.result()
                            if items:
                                batch_results[p] = items
                        except Exception:
                            pass

                # 페이지 순서대로 날짜 체크
                for p in sorted(batch_results.keys()):
                    for item in batch_results[p]:
                        d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
                        if not d:
                            continue
                        if d < start_date:
                            stop = True
                            break
                        if d <= end_date:
                            all_items.append(item)
                    if stop:
                        break

                page = batch_end

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
