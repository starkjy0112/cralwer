# -*- coding: utf-8 -*-
"""
속초시청 공지사항 크롤러
https://www.sokcho.go.kr/sc/portal/sokchonews/notice
POST 기반 (mForm), recordCountPerPage=100 지원
table.skinTb
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.sokcho.go.kr"
LIST_URL = f"{BASE_URL}/sc/portal/sokchonews/notice"
PAGE_SIZE = 100
ORGANIZATION_NAME = "속초시청"


class SokchoNoticeCrawler:
    """속초시청 공지사항 크롤러"""

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
            "pageIndex": str(page),
            "recordCountPerPage": str(PAGE_SIZE),
            "searchCondition": "TITLE",
            "searchKeyword": keyword if keyword else "",
            "boardCode": "BDAAFF03",
        }

        resp = self.session.post(LIST_URL, data=data, timeout=15, verify=False)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        text = soup.get_text()
        m = re.search(r'총\s*(\d[\d,]*)\s*건', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        table = soup.select_one("table.skinTb")
        if not table:
            return items, total_count

        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 6:
                continue
            # 번호(or 공지), 제목, 작성부서, 작성일, 첨부, 조회수
            number = tds[0].get_text(strip=True)
            if not total_count and number.isdigit():
                total_count = int(number)
            a_tag = tds[1].find("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            dept = tds[2].get_text(strip=True)
            date_str = tds[3].get_text(strip=True)

            items.append({
                "number": number,
                "title": title,
                "date": date_str,
                "url": LIST_URL,
                "organization": ORGANIZATION_NAME,
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
        print(f"[{ORGANIZATION_NAME}] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = SokchoNoticeCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n=== '용역' 검색 ===")
    results2 = crawler.search("용역", max_pages=1)
    for r in results2[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n공고: {len(results)}건, 용역: {len(results2)}건")
