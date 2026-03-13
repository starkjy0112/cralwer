# -*- coding: utf-8 -*-
"""
시흥도시공사 고시/공고 크롤러
https://www.shsi.or.kr/main/cop/bbs/selectBoardList.do
GET 기반, bbsId=Announcement_main
"""
import re
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.shsi.or.kr"
LIST_URL = f"{BASE_URL}/main/cop/bbs/selectBoardList.do"


class SHSICrawler:
    """시흥도시공사 고시/공고 크롤러"""

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
            "bbsId": "Announcement_main",
            "menuNo": "030000",
            "subMenuNo": "030500",
            "thirdMenuNo": "",
            "pageIndex": page,
        }
        if keyword:
            params["searchCnd"] = "0"  # 제목
            params["searchWrd"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        total_count = 0
        m = re.search(r'총\s*(\d[\d,]*)\s*건', soup.get_text())
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
            author = cells[2].get_text(strip=True) if len(cells) >= 5 else "시흥도시공사"
            date = cells[-2].get_text(strip=True) if len(cells) >= 5 else cells[-1].get_text(strip=True)

            link = title_cell.select_one("a")
            title = ""
            detail_url = ""
            if link:
                title = link.get_text(strip=True)
                onclick = link.get("onclick", "")
                m2 = re.search(r"goBbs\('([^']*)',\s*'(\d+)'", onclick)
                if m2:
                    bbs_id = m2.group(1)
                    ntt_id = m2.group(2)
                    detail_url = f"{BASE_URL}/main/cop/bbs/selectBoardArticle.do?bbsId={bbs_id}&nttId={ntt_id}"
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
        print(f"  [Page 1] {len(first_items)}건 수집 (전체 {total_count}건)")

        all_items = first_items
        page = 2
        while page <= max_pages and len(all_items) < total_count:
            items, _ = self._fetch_page(keyword, page)
            if not items:
                break
            all_items.extend(items)
            page += 1

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[시흥도시공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = SHSICrawler()
    print("=== 전체 조회 ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
