# -*- coding: utf-8 -*-
"""
마포구청 고시공고 크롤러
https://www.mapo.go.kr/site/main/nPortal/list
GET 기반, nPortal 시스템, 10건/페이지
테이블: 순번, 고시공고번호, 제목, 게재기간, 담당부서, 등록일(YYYYMMDD)
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.mapo.go.kr"
LIST_URL = f"{BASE_URL}/site/main/nPortal/list"
PAGE_SIZE = 10
ORGANIZATION_NAME = "마포구청"


class MapoCrawler:
    """마포구청 고시공고 크롤러"""

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
            params["sv"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        text = soup.get_text()
        m = re.search(r'총\s*(\d[\d,]*)\s*건', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_count

        # Table has no tbody, use tr directly, skip header row
        rows = table.select("tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 5:
                continue

            # 순번, 고시공고번호(pc), 제목, 게재기간(pc), 담당부서(pc), 등록일(pc)
            number = cells[0].get_text(strip=True)
            gosi_no = cells[1].get_text(strip=True)
            title_cell = cells[2]
            a_tag = title_cell.select_one("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)

            href = a_tag.get("href", "")
            if href and not href.startswith("http"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href or LIST_URL

            dept = cells[4].get_text(strip=True) if len(cells) > 4 else ORGANIZATION_NAME
            date_raw = cells[5].get_text(strip=True) if len(cells) > 5 else ""

            # Parse date: YYYYMMDD or YYYY-MM-DD
            date_str = ""
            dm = re.match(r'^(\d{4})(\d{2})(\d{2})$', date_raw)
            if dm:
                date_str = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
            else:
                dm2 = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', date_raw)
                if dm2:
                    date_str = f"{dm2.group(1)}-{int(dm2.group(2)):02d}-{int(dm2.group(3)):02d}"
                else:
                    date_str = date_raw

            items.append({
                "number": number,
                "title": title,
                "date": date_str,
                "url": detail_url,
                "organization": dept if dept else ORGANIZATION_NAME,
            })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
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

        # 날짜 필터 (기본: 최근 30일)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        filtered = []
        for item in all_items:
            d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
            if not d:
                continue
            if start_date <= d <= end_date:
                filtered.append(item)
        all_items = filtered

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[{ORGANIZATION_NAME}] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = MapoCrawler()
    print("=== 전체 조회 ===")
    results = crawler.search("", max_pages=1)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
