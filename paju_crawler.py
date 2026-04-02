# -*- coding: utf-8 -*-
"""
파주시청 고시공고 크롤러
https://www.paju.go.kr/user/board/BD_board.list.do?bbsCd=1022&q_ctgCd=4063
GET 기반, OpenWorks BBS, 10건/페이지
컬럼: 번호, 제목, 부서명, 등록일, 게재기간, 첨부, 조회수
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.paju.go.kr"
LIST_URL = f"{BASE_URL}/user/board/BD_board.list.do"
VIEW_URL = f"{BASE_URL}/user/board/BD_board.view.do"
PAGE_SIZE = 100


class PajuCrawler:
    """파주시청 고시공고 크롤러"""

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
            "bbsCd": "1022",
            "q_ctgCd": "4063",
            "q_currPage": page,
            "q_rowPerPage": PAGE_SIZE,
        }
        if keyword:
            params["q_searchKey"] = "sj"
            params["q_searchVal"] = keyword
        if start_date:
            params["q_startDt"] = start_date
        if end_date:
            params["q_endDt"] = end_date

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 총 건수: 첫 번째 행 번호 (= 전체 게시물 수)
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
            if len(cells) < 4:
                continue

            # 번호(cell-no), 제목(cell-subject), 부서명, 등록일(cell-tit), ...
            number = cells[0].get_text(strip=True)

            # 총 건수 fallback: 첫 행 번호
            if total_count == 0 and number.isdigit():
                total_count = int(number)

            # 제목 + 링크
            title_cell = cells[1]
            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            # 'N' 마커 제거
            title = re.sub(r'N$', '', title).strip()

            # jsView('1022', '20260319161106871', 'N', 'Y')
            onclick = link.get("onclick", "")
            m_view = re.search(r"jsView\('(\d+)',\s*'([^']+)'", onclick)
            if m_view:
                bbs_cd = m_view.group(1)
                bbs_sn = m_view.group(2)
                detail_url = f"{VIEW_URL}?bbsCd={bbs_cd}&q_bbsSn={bbs_sn}&q_ctgCd=4063"
            else:
                detail_url = f"{LIST_URL}?bbsCd=1022&q_ctgCd=4063"

            # 등록일: "등록일 :2026/03/19" 패턴
            date = ""
            for c in cells[2:]:
                txt = c.get_text(strip=True)
                m_date = re.search(r'(\d{4})[/.-](\d{2})[/.-](\d{2})', txt)
                if m_date:
                    date = f"{m_date.group(1)}-{m_date.group(2)}-{m_date.group(3)}"
                    break

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "파주시청",
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

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[파주시청 고시공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = PajuCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
