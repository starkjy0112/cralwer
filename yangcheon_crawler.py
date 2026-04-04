# -*- coding: utf-8 -*-
"""
양천구청 고시/공고 크롤러
https://www.yangcheon.go.kr/site/yangcheon/ex/seol/seolCollectList.do
GET 기반, SeolCollectVo form, basic-list 테이블, 10건/페이지
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.yangcheon.go.kr"
LIST_URL = f"{BASE_URL}/site/yangcheon/ex/seol/seolCollectList.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "양천구청"


class YangcheonCrawler:
    """양천구청 고시/공고 크롤러"""

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
            "pageIndex": str(page),
        }
        if keyword:
            params["searchKeyword"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        text = soup.get_text()
        m = re.search(r'총\s*(\d[\d,]*)\s*건', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))
        if not total_count:
            m2 = re.search(r'전체\s*(\d[\d,]*)', text)
            if m2:
                total_count = int(m2.group(1).replace(",", ""))

        items = []
        table = soup.select_one("table.basic-list, table")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 4:
                continue

            number = cells[0].get_text(strip=True)
            # gosi_no cell (공고번호)
            gosi_cell = cells[1]
            gosi_no = gosi_cell.get_text(strip=True)

            # title cell with subject class
            title_cell = cells[2] if len(cells) > 2 else cells[1]
            a_tag = title_cell.select_one("a")
            if not a_tag:
                # Try gosi_cell for link
                a_tag = gosi_cell.select_one("a")
                if not a_tag:
                    continue

            title = a_tag.get_text(strip=True)
            href = a_tag.get("href", "")
            onclick = a_tag.get("onclick", "")

            if "doSeolContentDeailView" in (href + onclick):
                seq_m = re.search(r"doSeolContentDeailView\('(\d+)'\)", href + onclick)
                if seq_m:
                    detail_url = f"{LIST_URL}?mode=view&not_ancmt_mgt_no={seq_m.group(1)}"
                else:
                    detail_url = LIST_URL
            elif href and not href.startswith("http") and not href.startswith("javascript"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href if href and href.startswith("http") else LIST_URL

            dept = cells[3].get_text(strip=True) if len(cells) > 3 else ORGANIZATION_NAME
            date_str = cells[4].get_text(strip=True) if len(cells) > 4 else ""

            m = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', date_str)
            if m:
                date_str = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

            items.append({
                "number": number,
                "title": title,
                "date": date_str,
                "url": detail_url,
                "organization": dept if dept else ORGANIZATION_NAME,
            })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10):
        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE)) if total_count else max_pages
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
        print(f"[{ORGANIZATION_NAME}] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = YangcheonCrawler()
    print("=== 전체 조회 ===")
    results = crawler.search("", max_pages=1)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
