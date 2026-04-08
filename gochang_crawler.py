# -*- coding: utf-8 -*-
"""
고창군청 고시공고 크롤러
https://www.gochang.go.kr/board/list.gochang?boardId=BBS_0000180&menuCd=DOM_000000102003007000&contentsSid=2682
GET 기반, ul.bbs_list (li/a/strong/em), 10건/페이지, startPage 파라미터
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.gochang.go.kr"
LIST_URL = f"{BASE_URL}/board/list.gochang"
BOARD_ID = "BBS_0000180"
MENU_CD = "DOM_000000102003007000"
CONTENTS_SID = "2682"
PAGE_SIZE = 10
ORGANIZATION_NAME = "고창군청"


class GochangCrawler:
    """고창군청 고시공고 크롤러"""

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
            "boardId": BOARD_ID,
            "menuCd": MENU_CD,
            "contentsSid": CONTENTS_SID,
            "searchType": "DATA_TITLE",
            "startPage": str(page),
        }
        if keyword:
            params["keyword"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15, verify=False)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        m = re.search(r'총\s*(\d[\d,]*)\s*건', soup.get_text())
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        bbs_list = soup.select_one("ul.bbs_list")
        if not bbs_list:
            return items, total_count

        for li in bbs_list.find_all("li"):
            link = li.find("a")
            if not link:
                continue

            # Title from <strong> (excluding ico_notice and ico_file)
            strong = link.find("strong")
            if not strong:
                continue
            # Get number from em.ico_notice like [43688]
            number = ""
            ico = strong.find("em", class_="ico_notice")
            if ico:
                m_num = re.search(r'\[(\d+)\]', ico.get_text())
                if m_num:
                    number = m_num.group(1)

            title = strong.get_text(strip=True)
            # Clean up: remove [number], 첨부파일 있음
            title = re.sub(r'\[\d+\]', '', title).strip()
            title = title.replace("첨부파일 있음", "").strip()

            href = link.get("href", "")
            if href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href

            # Date and gosi_no from em.info
            em_info = link.find("em", class_="info")
            date_str = ""
            gosi_no = ""
            if em_info:
                info_text = em_info.get_text()
                m_date = re.search(r'등록일\s*:\s*(\d{4}-\d{2}-\d{2})', info_text)
                if m_date:
                    date_str = m_date.group(1)
                # First line is gosi_no
                lines = [l.strip() for l in info_text.split('\n') if l.strip()]
                if lines:
                    gosi_no = lines[0].strip()

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
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    crawler = GochangCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
