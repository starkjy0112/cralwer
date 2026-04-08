# -*- coding: utf-8 -*-
"""
경기도청 고시공고 크롤러
https://www.gg.go.kr/bbs/board.do?bsIdx=469&menuId=1547
AJAX POST 기반 (/ajax/board/getList.do), 10건/페이지, offset 방식
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.gg.go.kr"
AJAX_URL = f"{BASE_URL}/ajax/board/getList.do"
PAGE_SIZE = 10


class GGCrawler:
    """경기도청 고시공고 크롤러"""

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

    def _fetch_page(self, keyword, page):
        offset = (page - 1) * PAGE_SIZE
        post_data = {
            "bsIdx": "469",
            "bcIdx": "0",
            "menuId": "1547",
            "offset": str(offset),
        }
        if keyword:
            post_data["keyword"] = keyword
            post_data["keyfield"] = "SUBJECTANDREMARK"

        resp = self.session.post(AJAX_URL, data=post_data, timeout=15)
        resp.encoding = "utf-8"
        data = resp.json()

        total_count = int(data.get("total", 0))

        items = []
        for item in data.get("items", []):
            b_idx = item.get("B_IDX", "")
            subject = item.get("SUBJECT", "")
            writer = item.get("WRITER", "")
            date = item.get("WRITE_DATE2", "")

            detail_url = f"{BASE_URL}/bbs/boardView.do?bIdx={b_idx}&bsIdx=469&menuId=1547"

            items.append({
                "number": str(b_idx),
                "title": subject,
                "date": date,
                "url": detail_url,
                "organization": writer if writer else "경기도청",
            })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
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

        # 날짜 필터 (기본: 최근 30일)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        filtered = []
        for item in all_items:
            d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
            if not d:
                continue
            if start_date <= d <= end_date:
                filtered.append(item)
        all_items = filtered

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[경기도청] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = GGCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
