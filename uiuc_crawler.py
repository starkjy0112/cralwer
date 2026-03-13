# -*- coding: utf-8 -*-
"""
의정부도시공사 입찰공고/고시 크롤러
https://www.uiuc.or.kr/companyNotice/announcementPage/announcement/list.do
GET 기반, 15건/페이지
"""
import math
import re
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.uiuc.or.kr"
LIST_URL = f"{BASE_URL}/companyNotice/announcementPage/announcement/list.do"
PAGE_SIZE = 15


class UIUCCrawler:
    """의정부도시공사 입찰공고/고시 크롤러"""

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
            "pageNum": page,
            "searchField0": "a.BBS_ID",
            "searchKeyword0": "BBSMSTR_000000000078",
        }
        if keyword:
            params["searchField1"] = "NTT_SJ"  # 제목
            params["searchKeyword1"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 총 건수: "286건"
        total_count = 0
        m = re.search(r'(\d[\d,]*)\s*건', soup.get_text())
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_count

        rows = table.select("tr")[1:]
        for row in rows:
            cells = row.select("td")
            if len(cells) < 4:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            views = cells[2].get_text(strip=True)
            date = cells[3].get_text(strip=True)

            link = title_cell.select_one("a")
            title = ""
            detail_url = ""
            if link:
                title = link.get_text(strip=True)
                onclick = link.get("onclick", "") or link.get("href", "")
                m2 = re.search(r"nttId=(\d+)", onclick)
                if m2:
                    ntt_id = m2.group(1)
                    detail_url = f"{BASE_URL}/companyNotice/announcementPage/announcement/view.do?bbsId=BBSMSTR_000000000078&nttId={ntt_id}"
                else:
                    m2 = re.search(r"goViewContents\('([^']+)'\)", onclick)
                    if m2:
                        qs = m2.group(1)
                        detail_url = f"{LIST_URL}?{qs}"

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "의정부도시공사",
            })

        return items, total_count

    def search(self, keyword="", max_pages=10):
        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 {total_count}건)")

        all_items = first_items
        for page in range(2, actual_pages + 1):
            items, _ = self._fetch_page(keyword, page)
            if not items:
                break
            all_items.extend(items)

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[의정부도시공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = UIUCCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
