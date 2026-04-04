# -*- coding: utf-8 -*-
"""
해남군청 고시공고 크롤러
https://www.haenam.go.kr/index.9is?contentUid=18e3368f7913117f017915ea3b971122
GET 기반, table 5열 (번호/제목/고시번호/부서/일자), nowPageNum 파라미터
detail: goDetialView(id) -> index.9is?contentUid=...&recordCountPerPage=10
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.haenam.go.kr"
CONTENT_UID = "18e3368f7913117f017915ea3b971122"
DETAIL_CONTENT_UID = "18e3368f7913117f01791bdc63505ada"
LIST_URL = f"{BASE_URL}/index.9is"
PAGE_SIZE = 10
ORGANIZATION_NAME = "해남군청"


class HaenamGosiCrawler:
    """해남군청 고시공고 크롤러"""

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
            "contentUid": CONTENT_UID,
            "nowPageNum": str(page),
            "recordCountPerPage": "10",
        }
        if keyword:
            params["searchType"] = "title"
            params["keyword"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        max_page = 1
        for a in soup.select('a[href*="nowPageNum="]'):
            m = re.search(r'nowPageNum=(\d+)', a.get("href", ""))
            if m:
                max_page = max(max_page, int(m.group(1)))
        total_count = max_page * PAGE_SIZE

        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_count
        rows = table.select("tbody tr") or table.select("tr")[1:]
        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue
            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            gosi_no = cells[2].get_text(strip=True)
            dept = cells[3].get_text(strip=True)
            date = cells[4].get_text(strip=True)

            link = title_cell.select_one("a")
            title = link.get_text(strip=True) if link else title_cell.get_text(strip=True)
            title = re.sub(r'파일$', '', title).strip()
            title = re.sub(r'NEW$', '', title).strip()

            # Extract ID from onclick: goDetialView('55901','1','','')
            detail_id = ""
            if link:
                onclick = link.get("onclick", "")
                m_id = re.search(r"goDetialView\('(\d+)'", onclick)
                if m_id:
                    detail_id = m_id.group(1)

            detail_url = f"{LIST_URL}?contentUid={DETAIL_CONTENT_UID}&recordCountPerPage=10" if detail_id else LIST_URL

            display_title = f"[{gosi_no}] {title}" if gosi_no else title
            items.append({"number": number, "title": display_title, "date": date, "url": detail_url, "organization": dept or ORGANIZATION_NAME})
        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10):
        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 약 {total_count}건)")
        if actual_pages <= 1:
            all_items = first_items
        else:
            page_results = {1: first_items}
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {executor.submit(self._fetch_page, keyword, p): p for p in range(2, actual_pages + 1)}
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
        print(f"[{ORGANIZATION_NAME} 고시공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = HaenamGosiCrawler()
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
