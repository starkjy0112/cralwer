# -*- coding: utf-8 -*-
"""
화성특례시청 입찰공고 크롤러
https://www.hscity.go.kr/www/gosi/BD_bidding.do?q_notAncmtSeCode=02
GET 기반, OpenWorks, 10건/페이지
컬럼: 고시공고번호, 제목, 담당부서, 게재(공고)일자, 게재기간
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.hscity.go.kr"
LIST_URL = f"{BASE_URL}/www/gosi/BD_bidding.do"
DETAIL_URL = f"{BASE_URL}/www/gosi/BD_selectBiddingDetail.do"
PAGE_SIZE = 100


class HwaseongBidCrawler:
    """화성특례시청 입찰공고 크롤러"""

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
            "q_notAncmtSeCode": "02",
            "q_rowPerPage": str(PAGE_SIZE),
            "q_currPage": str(page),
            "q_cp": str(page),
        }
        if keyword:
            params["q_sv"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        text = soup.get_text()
        m = re.search(r'총\s*(\d[\d,]*)\s*건', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        if not rows:
            rows = table.select("tr")[1:]

        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            notice_no = cells[0].get_text(strip=True)
            title_cell = cells[1]
            dept = cells[2].get_text(strip=True)
            date = cells[3].get_text(strip=True)

            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")

            m_view = re.search(r"opGosiView\('([^']+)'\)", href)
            if m_view:
                detail_url = f"{DETAIL_URL}?q_notAncmtSeCode=02&q_notAncmtMgtNo={m_view.group(1)}"
            else:
                detail_url = f"{LIST_URL}?q_notAncmtSeCode=02"

            items.append({
                "number": notice_no,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "화성특례시청",
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
        print(f"[화성특례시청 입찰공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = HwaseongBidCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
