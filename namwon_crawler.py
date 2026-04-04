# -*- coding: utf-8 -*-
"""
남원시청 고시공고 크롤러
https://www.namwon.go.kr/board/post/list.do?boardUid=ff8080818ea1fec5018ea24137680031&menuUid=ff8080818e3beff0018e4077131b007a&sort=registerDt,desc
GET 기반, table.bbs_table, 10건/페이지, page 파라미터
컬럼: 번호, 공고번호, 제목(link), 담당부서, 첨부파일, 등록일, 조회
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.namwon.go.kr"
LIST_URL = f"{BASE_URL}/board/post/list.do"
BOARD_UID = "ff8080818ea1fec5018ea24137680031"
MENU_UID = "ff8080818e3beff0018e4077131b007a"
PAGE_SIZE = 10
ORGANIZATION_NAME = "남원시청"


class NamwonCrawler:
    """남원시청 고시공고 크롤러"""

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
            "boardUid": BOARD_UID,
            "menuUid": MENU_UID,
            "sort": "registerDt,desc",
            "page": str(page),
        }
        if keyword:
            params["searchType"] = "title"
            params["searchKeyword"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15, verify=False)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        m = re.search(r'총\s*(\d[\d,]*)\s*건', soup.get_text())
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        table = soup.select_one("table.bbs_table") or soup.select_one("table")
        if not table:
            return items, total_count

        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 7:
                continue

            # td[0]=번호, td[1]=공고번호, td[2]=제목, td[3]=담당부서, td[4]=첨부, td[5]=등록일, td[6]=조회
            number = tds[0].get_text(strip=True).replace(",", "")
            if not total_count and number.isdigit():
                total_count = int(number)

            gosi_no_text = tds[1].get_text(strip=True)
            # Remove prefix like "공고번호"
            gosi_no = re.sub(r'^공고번호', '', gosi_no_text).strip()

            a_tag = tds[2].find("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            href = a_tag.get("href", "")
            if href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href

            # Date from td[5] - has "등록일" prefix
            date_text = tds[5].get_text(strip=True)
            m_date = re.search(r'(\d{4}-\d{2}-\d{2})', date_text)
            date_str = m_date.group(1) if m_date else date_text.replace("등록일", "").strip()

            display_title = f"[{gosi_no}] {title}" if gosi_no else title

            items.append({
                "number": number,
                "title": display_title,
                "date": date_str,
                "url": detail_url,
                "organization": ORGANIZATION_NAME,
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
        print(f"[{ORGANIZATION_NAME} 고시공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = NamwonCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
