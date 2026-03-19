# -*- coding: utf-8 -*-
"""
대구광역시청 고시공고 크롤러
https://www.daegu.go.kr/index.do?menu_id=00940170&menu_link=/front/daeguSidoGosi/daeguSidoGosiList.do
POST 기반, 10건/페이지, pageIndex 방식
"""
import math
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.daegu.go.kr"
LIST_URL = f"{BASE_URL}/index.do"
PAGE_SIZE = 10


class DaeguCrawler:
    """대구광역시청 고시공고 크롤러"""

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
        post_data = {
            "menu_id": "00940170",
            "menu_link": "/front/daeguSidoGosi/daeguSidoGosiList.do",
            "pageIndex": str(page),
            "sno": "",
            "gosi_gbn": "",
            "searchBgnDe": "",
            "searchEndDe": "",
            "searchAnnounce_no": "",
            "searchGosi_gbn": "",
            "searchDept_nm": "",
            "postPerPage": "0",
        }
        if keyword:
            post_data["searchTitle"] = keyword

        resp = self.session.post(LIST_URL, data=post_data, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 총 건수: pagination에서 마지막 페이지 번호로 추정
        total_count = 0
        pagination = soup.select_one("div.pagination")
        if pagination:
            # 마지막 페이지 링크에서 총 페이지 수 추출
            last_link = pagination.select("a.page_nextend")
            if last_link:
                onclick = last_link[0].get("onclick", "")
                m = re.search(r'fn_egov_link_page\((\d+)', onclick)
                if m:
                    total_pages = int(m.group(1))
                    total_count = total_pages * PAGE_SIZE

        items = []
        table = soup.select_one("table#bbsList")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            dept = cells[2].get_text(strip=True)
            date = cells[3].get_text(strip=True)

            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)

            # href는 javascript:fn_goLinkView('45528', 'A') 형식
            href = link.get("href", "")
            m = re.search(r"fn_goLinkView\('(\d+)',\s*'([^']+)'\)", href)
            if m:
                sno = m.group(1)
                gosi_gbn = m.group(2)
                detail_url = (
                    f"{BASE_URL}/index.do?menu_id=00940170"
                    f"&menu_link=/front/daeguSidoGosi/daeguSidoGosiView.do"
                    f"&sno={sno}&gosi_gbn={gosi_gbn}"
                )
            else:
                detail_url = f"{BASE_URL}/index.do?menu_id=00940170"

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": dept if dept else "대구광역시청",
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
        print(f"[대구광역시청] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = DaeguCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
