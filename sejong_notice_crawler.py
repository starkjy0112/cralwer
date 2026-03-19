# -*- coding: utf-8 -*-
"""
세종특별자치시청 공지사항 크롤러
https://www.sejong.go.kr/bbs/R0071/list.do
POST 기반, 10건/페이지
"""
import math
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.sejong.go.kr"
LIST_URL = f"{BASE_URL}/bbs/R0071/list.do"
PAGE_SIZE = 10


class SejongNoticeCrawler:
    """세종특별자치시청 공지사항 크롤러"""

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
        data = {
            "pageIndex": page,
        }
        if keyword:
            data["searchCondition"] = "all"
            data["searchKeyword"] = keyword

        resp = self.session.post(LIST_URL, data=data, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 총 건수: "총 게시물 <strong> 19,037</strong>"
        total_count = 0
        m = re.search(r'총\s*게시물\s*<strong>\s*([\d,]+)', resp.text)
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

            # 번호 column: notice rows have "공지", regular rows have number
            num_cell = row.select_one("td[data-cell-header='번호']")
            notice_cell = row.select_one("td[data-cell-header='공지']")
            if num_cell:
                number = num_cell.get_text(strip=True)
            elif notice_cell:
                number = "공지"
            else:
                number = cells[0].get_text(strip=True)

            # 제목
            title_cell = row.select_one("td[data-cell-header='제목']")
            if not title_cell:
                title_cell = row.select_one("td.subject")
            if not title_cell:
                continue

            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")
            # Clean jsessionid from URL
            href = re.sub(r';jsessionid=[^?]*', '', href)
            if href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href

            # 작성자
            author_cell = row.select_one("td[data-cell-header='작성자']")
            author = author_cell.get_text(strip=True) if author_cell else "세종특별자치시청"

            # 등록일
            date_cell = row.select_one("td[data-cell-header='등록일']")
            date = date_cell.get_text(strip=True) if date_cell else ""

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "세종특별자치시청",
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
        print(f"[세종특별자치시청 공지사항] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = SejongNoticeCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
