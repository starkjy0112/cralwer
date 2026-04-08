# -*- coding: utf-8 -*-
"""
서울특별시청 건설알림이 공지사항 크롤러
https://cis.seoul.go.kr/TotalAlimi_new/Notice.action
GET 기반, 10건/페이지, Struts .action 엔드포인트
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://cis.seoul.go.kr"
LIST_URL = f"{BASE_URL}/TotalAlimi_new/Notice.action"
PAGE_SIZE = 10


class SeoulCISCrawler:
    """서울특별시청 건설알림이 공지사항 크롤러"""

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

    def _fetch_page(self, keyword, page, start_date=None, end_date=None):
        params = {
            "pageNo": page,
            "start_ymd": start_date if start_date else "",
            "end_ymd": end_date if end_date else "",
            "pic_div": "1",
        }
        if keyword:
            params["pic_text"] = keyword
        else:
            params["pic_text"] = ""

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 총 건수: 첫 번째 row의 번호가 전체 건수 (내림차순 번호)
        total_count = 0

        items = []
        table = soup.select_one("table.tbStyle1")
        if not table:
            return items, total_count

        rows = table.select("tbody tr") or table.select("tr")[1:]
        for row in rows:
            cells = row.select("td")
            if len(cells) < 6:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            # cells[2] is 정보보기 (skip)
            dept = cells[3].get_text(strip=True)
            # cells[4] is 조회수 (skip)
            date = cells[5].get_text(strip=True)

            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")
            if href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href

            if not items and number.isdigit():
                total_count = int(number)

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "서울특별시청",
            })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
        first_items, total_count = self._fetch_page(keyword, 1, start_date, end_date)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 {total_count}건)")

        if actual_pages <= 1:
            all_items = first_items
        else:
            page_results = {1: first_items}
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_page, keyword, p, start_date, end_date): p
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
        print(f"[서울특별시청 건설알림이] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = SeoulCISCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공사' 검색 ===")
    results2 = crawler.search("공사", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
