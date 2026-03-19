# -*- coding: utf-8 -*-
"""
강원특별자치도청 공고/고시 크롤러
https://state.gwd.go.kr/portal/bulletin/notification
GET 기반, 15건/페이지
"""
import math
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date


BASE_URL = "https://state.gwd.go.kr"
LIST_URL = f"{BASE_URL}/portal/bulletin/notification"
PAGE_SIZE = 100


class GangwonCrawler:
    """강원특별자치도청 공고/고시 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })

    def _fetch_page(self, keyword, page, start_date=None, end_date=None):
        today = date.today().isoformat()
        params = {
            "pageIndex": page,
            "recordCountPerPage": PAGE_SIZE,
            "searchFromDate": start_date if start_date else "2021-01-01",
            "searchToDate": end_date if end_date else today,
            "searchCondition": "TITLE",
            "searchKeyword": keyword,
        }

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 총 건수: "총 게시물 : 6546 | page 1 / 437"
        total_count = 0
        text = soup.get_text()
        m = re.search(r'총\s*게시물\s*:\s*(\d[\d,]*)', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))
        else:
            # fallback: pager-num "1/437"
            pager = soup.select_one(".pager-num")
            if pager:
                pm = re.search(r'\d+/(\d+)', pager.get_text())
                if pm:
                    total_count = int(pm.group(1)) * PAGE_SIZE

        items = []
        table = soup.select_one("table")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) < 4:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[1]
            dept = cells[2].get_text(strip=True)
            date_str = cells[3].get_text(strip=True)

            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)

            # goPage(267554) -> articleSeq, build detail URL
            onclick = link.get("onclick", "")
            seq_match = re.search(r'goPage\((\d+)\)', onclick)
            if seq_match:
                article_seq = seq_match.group(1)
                detail_url = f"{LIST_URL}?articleSeq={article_seq}"
            else:
                href = link.get("href", "")
                if href.startswith("/"):
                    detail_url = f"{BASE_URL}{href}"
                else:
                    detail_url = href

            items.append({
                "number": number,
                "title": title,
                "date": date_str,
                "url": detail_url,
                "organization": dept if dept else "강원특별자치도청",
            })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
        first_items, total_count = self._fetch_page(keyword, 1, start_date, end_date)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 {total_count}건)")

        if actual_pages <= 1:
            all_items = first_items
        else:
            page_results = {1: first_items}
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_page, keyword, p, start_date, end_date): p
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
        print(f"[강원특별자치도청] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = GangwonCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
