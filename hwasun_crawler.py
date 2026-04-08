# -*- coding: utf-8 -*-
"""
화순군청 공지사항 크롤러
https://www.hwasun.go.kr/board.do?S=S01&M=020102000000&b_code=0000000002&b_list=10
GET 기반, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.hwasun.go.kr"
LIST_URL = f"{BASE_URL}/board.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "화순군청"


class HwasunCrawler:
    """화순군청 공지사항 크롤러"""

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
            "S": "S01",
            "M": "020102000000",
            "b_code": "0000000002",
            "b_list": "10",
            "nPage": str(page),
        }
        if keyword:
            params["keyWord"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 총 건수: 첫 번째 행의 번호 (역순)
        total_count = 0

        # 페이지 수 추정: pageForm 영역
        paging = soup.find("div", class_="pageForm")
        if paging:
            max_page = 1
            for a in paging.find_all("a"):
                href = a.get("href", "")
                m = re.search(r"nPage=(\d+)", href)
                if m:
                    p_num = int(m.group(1))
                    if p_num > max_page:
                        max_page = p_num
            total_count = max_page * PAGE_SIZE

        items = []
        table = None
        for t in soup.find_all("table"):
            rows = t.find_all("tr")
            if len(rows) > 3:
                table = t
                break

        if table:
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
            for tr in rows:
                tds = tr.find_all("td")
                if len(tds) < 4:
                    continue
                number = tds[0].get_text(strip=True)
                if not total_count and number.isdigit():
                    total_count = int(number)

                title_td = tds[1]
                title_tag = title_td.find("a")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                href = title_tag.get("href", "")
                detail_url = BASE_URL + href if href and not href.startswith("http") else href

                date = tds[3].get_text(strip=True)

                items.append({
                    "number": number,
                    "title": title,
                    "date": date,
                    "url": detail_url,
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
    crawler = HwasunCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
