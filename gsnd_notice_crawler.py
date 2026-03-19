# -*- coding: utf-8 -*-
"""
경상남도청 공지사항 크롤러
https://www.gyeongnam.go.kr/board/list.gyeong?boardId=BBS_0000057&menuCd=DOM_000000135001001000&contentsSid=6951
GET 기반, 10건/페이지
"""
import math
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.gyeongnam.go.kr"
LIST_URL = f"{BASE_URL}/board/list.gyeong"
PAGE_SIZE = 10


class GSNDNoticeCrawler:
    """경상남도청 공지사항 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })

    def _fetch_page(self, keyword, page):
        params = {
            "boardId": "BBS_0000057",
            "menuCd": "DOM_000000135001001000",
            "contentsSid": "6951",
            "searchType": "DATA_TITLE",
            "paging": "ok",
            "startPage": page,
        }
        if keyword:
            params["keyword"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 총 건수: "총 게시물 :7785건, 페이지 : 1/779"
        total_count = 0
        total_el = soup.select_one("p.page")
        if total_el:
            count_span = total_el.select_one("span.count-1")
            if count_span:
                total_count = int(count_span.get_text(strip=True).replace(",", ""))

        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            # 컬럼: 번호(num), 제목(title), 첨부(file), 부서명(name), 작성일(date), 조회(hit)
            num_cell = row.select_one("td.num")
            title_cell = row.select_one("td.title")
            name_cell = row.select_one("td.name")
            date_cell = row.select_one("td.date")

            if not title_cell:
                continue

            link = title_cell.select_one("a")
            if not link:
                continue

            number = num_cell.get_text(strip=True) if num_cell else ""
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href

            date = date_cell.get_text(strip=True) if date_cell else ""
            # 날짜 형식 변환: "26.03.13" -> "2026-03-13"
            if date and re.match(r'^\d{2}\.\d{2}\.\d{2}$', date):
                parts = date.split(".")
                date = f"20{parts[0]}-{parts[1]}-{parts[2]}"

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "경상남도청",
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
        print(f"[경상남도청 공지사항] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = GSNDNoticeCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
