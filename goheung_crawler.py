# -*- coding: utf-8 -*-
"""
고흥군청 고시/공고 크롤러
https://www.goheung.go.kr/contentsView.do?pageId=www99
POST /getEminwon.do AJAX 기반, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.goheung.go.kr"
API_URL = f"{BASE_URL}/getEminwon.do"
DETAIL_URL = f"{BASE_URL}/contentsView.do?pageId=www99&action=V&seq="
PAGE_SIZE = 10
ORGANIZATION_NAME = "고흥군청"


class GoheungCrawler:
    """고흥군청 고시/공고 크롤러"""

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
        data = {
            "action": "L",
            "notAncmtSeCode": "01,04,05",
            "listGubun": "A",
            "recordCnt": str(PAGE_SIZE),
            "movePage": str(page),
            "prevAction": "L",
            "prevMovePage": str(page),
        }
        if keyword:
            data["eminwonQuery"] = keyword

        resp = self.session.post(API_URL, data=data, timeout=15)
        result = resp.json()

        total_count = 0
        items = []

        if result.get("errChk") != "N":
            return items, total_count

        arr = result.get("dataArr", {})
        total_count = int(arr.get("totalCnt", 0))
        item_list = arr.get("list", [])

        for item in item_list:
            seq = str(item.get("seq", "")).strip()
            number = str(item.get("idx", "")).strip()
            title = str(item.get("sj", "")).strip()
            date = str(item.get("regDe", "")).strip()
            dept = str(item.get("deptNm", "")).strip()
            gosi_no = str(item.get("gosiNo", "")).strip()

            detail_link = f"{DETAIL_URL}{seq}" if seq else BASE_URL

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
    crawler = GoheungCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
