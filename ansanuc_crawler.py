# -*- coding: utf-8 -*-
"""
안산도시공사 입찰공고 크롤러
https://www.ansanuc.net/homenew/12435/20359/bbsList.do
GET 기반
"""
import math
import re
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.ansanuc.net"
LIST_URL = f"{BASE_URL}/homenew/12435/20359/bbsList.do"
PAGE_SIZE = 10


class ANSANUCCrawler:
    """안산도시공사 입찰공고 크롤러"""

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
        params = {"currentPageNo": page}
        if keyword:
            params["searchCondition"] = "title"  # 제목
            params["searchKeyword"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        items = []
        table = soup.select_one("table")
        if not table:
            return items, 0

        rows = table.select("tr")[1:]

        # 총 건수: 첫 행의 번호가 역순이므로 첫 번호 = 전체 건수
        total_count = 0
        if rows:
            first_cells = rows[0].select("td")
            if first_cells:
                try:
                    total_count = int(first_cells[0].get_text(strip=True))
                except ValueError:
                    pass
        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            author = cells[3].get_text(strip=True)
            date = cells[4].get_text(strip=True)

            link = title_cell.select_one("a")
            title = ""
            detail_url = ""
            if link:
                title = link.get_text(strip=True)
                onclick = link.get("onclick", "")
                m2 = re.search(r"fnDetail\('(\d+)'\)", onclick)
                if m2:
                    bbs_idx = m2.group(1)
                    detail_url = f"{BASE_URL}/homenew/12435/20359/bbsDetail.do?bbsIdx={bbs_idx}"
                else:
                    href = link.get("href", "")
                    if href and href != "#":
                        detail_url = f"{BASE_URL}{href}" if href.startswith("/") else href

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": author,
            })

        return items, total_count

    def search(self, keyword="", max_pages=10):
        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE)) if total_count else 1
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 {total_count}건)")

        all_items = first_items
        for p in range(2, actual_pages + 1):
            items, _ = self._fetch_page(keyword, p)
            if not items:
                break
            all_items.extend(items)

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[안산도시공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = ANSANUCCrawler()
    print("=== 전체 조회 ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
