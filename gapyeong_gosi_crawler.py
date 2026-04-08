# -*- coding: utf-8 -*-
"""
가평군청 고시공고 크롤러
http://www.gp.go.kr/portal/selectGosiList.do?key=2148&not_ancmt_se_code=01
GET 기반, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "http://www.gp.go.kr"
LIST_URL = f"{BASE_URL}/portal/selectGosiList.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "가평군청"


class GapyeongGosiCrawler:
    """가평군청 고시공고 크롤러"""

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
            "key": "2148",
            "not_ancmt_se_code": "01",
            "pageIndex": str(page),
        }
        if keyword:
            params["searchCnd"] = "SJ"
            params["searchKrwd"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # Parse total count from "총 게시물 <em>774</em>"
        total_count = 0
        board_top = soup.find("div", class_="board_top")
        if board_top:
            em = board_top.find("em")
            if em:
                try:
                    total_count = int(re.sub(r"[^\d]", "", em.get_text(strip=True)))
                except ValueError:
                    pass

        items = []
        table = soup.find("table", class_="bbs_default_list")
        if table:
            tbody = table.find("tbody")
            if tbody:
                for tr in tbody.find_all("tr"):
                    tds = tr.find_all("td")
                    if len(tds) < 6:
                        continue
                    # 번호, 공고번호, 등록일, 제목, 담당부서, 게재기간
                    number = tds[0].get_text(strip=True)
                    raw_date = tds[2].get_text(strip=True)
                    # Convert 20260319 -> 2026-03-19
                    if len(raw_date) == 8 and raw_date.isdigit():
                        date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
                    else:
                        date = raw_date

                    title_td = tds[3]
                    title_tag = title_td.find("a")
                    if not title_tag:
                        continue
                    title = title_tag.get_text(strip=True)
                    href = title_tag.get("href", "")
                    detail_url = f"{BASE_URL}/portal/{href.lstrip('./')}" if href.startswith("./") else (BASE_URL + href if href.startswith("/") else href)

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
    crawler = GapyeongGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
