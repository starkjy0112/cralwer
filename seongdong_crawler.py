# -*- coding: utf-8 -*-
"""
성동구청 고시공고 크롤러
https://www.sd.go.kr/main/selectBbsNttList.do?bbsNo=184&key=1473
GET 기반, p-table simple 테이블, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.sd.go.kr"
LIST_URL = f"{BASE_URL}/main/selectBbsNttList.do"
PAGE_SIZE = 10
ORGANIZATION_NAME = "성동구청"


class SeongdongCrawler:
    """성동구청 고시공고 크롤러"""

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
            "bbsNo": "184",
            "key": "1473",
            "pageIndex": str(page),
            "pageUnit": str(PAGE_SIZE),
        }
        if keyword:
            params["searchCnd"] = "SJ"
            params["searchKrwd"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        text = soup.get_text()
        m = re.search(r'총\s*(\d[\d,]*)\s*건', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))
        if not total_count:
            # Find from pagination or hidden input
            m2 = re.search(r'전체\s*(\d[\d,]*)', text)
            if m2:
                total_count = int(m2.group(1).replace(",", ""))

        items = []
        table = soup.select_one("table.p-table, table.simple, table")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 3:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            a_tag = title_cell.select_one("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            # Clean up NEW badge
            title = re.sub(r'\s*NEW\s*$', '', title).strip()

            href = a_tag.get("href", "")
            if href and not href.startswith("http"):
                detail_url = f"{BASE_URL}/main/{href.lstrip('./')}"
            elif href:
                detail_url = href
            else:
                detail_url = LIST_URL

            # Date from <time> tag or td
            date_str = ""
            time_tag = row.select_one("time")
            if time_tag:
                date_str = time_tag.get("datetime", "") or time_tag.get_text(strip=True)
            else:
                date_cell = cells[2] if len(cells) > 2 else None
                if date_cell:
                    date_str = date_cell.get_text(strip=True)

            m = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', date_str)
            if m:
                date_str = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

            items.append({
                "number": number,
                "title": title,
                "date": date_str,
                "url": detail_url,
                "organization": ORGANIZATION_NAME,
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
    crawler = SeongdongCrawler()
    print("=== 전체 조회 ===")
    results = crawler.search("", max_pages=1)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
