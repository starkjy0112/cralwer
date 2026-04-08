# -*- coding: utf-8 -*-
"""
해남군청 고시공고 크롤러
https://www.haenam.go.kr/index.9is?contentUid=18e3368f7913117f017915ea3b971122
GET 기반, table 5열 (번호/제목/고시번호/부서/일자), nowPageNum 파라미터
detail: goDetialView(id) -> index.9is?contentUid=...&recordCountPerPage=10
"""
import math
import re
from datetime import datetime, timedelta
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
        print(f"[{ORGANIZATION_NAME} 고시공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = HaenamGosiCrawler()
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
