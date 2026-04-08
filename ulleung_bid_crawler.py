# -*- coding: utf-8 -*-
"""
울릉군청 입찰정보 크롤러
https://www.ulleung.go.kr/ko/page.do?mnu_uid=1450&boardType=notice&board_code=02
GET 기반, tbl_board 테이블, 10건/페이지, pageNo 파라미터
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.ulleung.go.kr"
LIST_URL = f"{BASE_URL}/ko/page.do"
MNU_UID = "1450"
PAGE_SIZE = 10
ORGANIZATION_NAME = "울릉군청"


class UlleungBidCrawler:
    """울릉군청 입찰정보 크롤러"""

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
            "mnu_uid": MNU_UID,
            "boardType": "notice",
            "board_code": "02",
            "pageNo": str(page),
        }
        if keyword:
            params["srchColumn"] = "title"
            params["srchKwd"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []

        table = soup.select_one("table.tbl_board") or soup.select_one("table.board_list")
        if not table:
            for t in soup.find_all("table"):
                if t.find("th", class_="subject"):
                    table = t
                    break
        if not table:
            return items, total_count

        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

        for row in rows:
            tds = row.find_all("td")
            if len(tds) < 4:
                continue

            num_td = row.select_one("td.num")
            number = num_td.get_text(strip=True) if num_td else tds[0].get_text(strip=True)

            if total_count == 0 and page == 1:
                num_text = number.replace(",", "")
                if num_text.isdigit():
                    total_count = int(num_text)

            subject_td = row.select_one("td.subject") or row.select_one("td.taL")
            if not subject_td:
                subject_td = tds[1]
            link = subject_td.find("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")
            if href.startswith("?"):
                detail_url = f"{LIST_URL}{href}"
            elif href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href if href.startswith("http") else ""

            date_td = row.select_one("td.date")
            date = date_td.get_text(strip=True) if date_td else ""

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": ORGANIZATION_NAME,
            })

        if total_count == 0:
            paging = soup.select_one("div.pageInfo") or soup.select_one("div.paging")
            if paging:
                max_page = 1
                for a in paging.find_all("a"):
                    href_p = a.get("href", "")
                    m = re.search(r'pageNo=(\d+)', href_p)
                    if m:
                        pn = int(m.group(1))
                        if pn > max_page:
                            max_page = pn
                total_count = max_page * PAGE_SIZE

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
        print(f"[{ORGANIZATION_NAME} 입찰정보] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = UlleungBidCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
