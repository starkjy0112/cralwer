# -*- coding: utf-8 -*-
"""
고령군청 고시/공고 크롤러
https://www.goryeong.go.kr/kor/boardList.do?IDX=154&BRD_ID=1023
POST 기반, table.boardList_table, 10건/페이지
컬럼: 번호, 구분, 제목, 작성자, 작성일, 첨부, 조회수
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.goryeong.go.kr"
LIST_URL = f"{BASE_URL}/kor/boardList.do"
VIEW_URL = f"{BASE_URL}/kor/boardView.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "고령군청"


class GoryeongCrawler:
    """고령군청 고시/공고 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
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
        data = {
            "BRD_ID": "1023",
            "IDX": "154",
            "page": str(page),
        }
        if keyword:
            data["searchOk"] = "Y"
            data["searchType"] = "subject"
            data["keyword"] = keyword

        resp = self.session.post(
            f"{LIST_URL}?IDX=154&BRD_ID=1023", data=data, timeout=15
        )
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []
        table = soup.find("table", class_="boardList_table") or soup.find("table")
        if not table:
            return items, total_count

        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue
            number = tds[0].get_text(strip=True).replace(",", "")
            if not total_count and number.isdigit():
                total_count = int(number)

            category = tds[1].get_text(strip=True)
            a_tag = tds[2].find("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            # Detail link via javascript - construct from onclick or use list URL
            onclick = a_tag.get("onclick", "")
            m = re.search(r"boardView\.do\?([^'\"]+)", onclick)
            if m:
                detail_url = f"{VIEW_URL}?{m.group(1)}"
            else:
                detail_url = f"{LIST_URL}?IDX=154&BRD_ID=1023"

            dept = tds[3].get_text(strip=True)
            date_str = tds[4].get_text(strip=True).replace(".", "-")

            display_title = f"[{category}] {title}" if category else title

            items.append({
                "number": number,
                "title": display_title,
                "date": date_str,
                "url": detail_url,
                "organization": f"{ORGANIZATION_NAME} ({dept})" if dept else ORGANIZATION_NAME,
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
        print(f"[{ORGANIZATION_NAME} 고시/공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = GoryeongCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
