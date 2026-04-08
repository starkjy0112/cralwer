# -*- coding: utf-8 -*-
"""
하남시청 고시공고 크롤러
https://www.hanam.go.kr/www/selectGosiList.do?key=171&not_ancmt_se_code=01,04
GET 기반, 10건/페이지
컬럼: 번호, 공고번호, 등록일, 제목, 담당부서, 게재기간
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.hanam.go.kr"
LIST_URL = f"{BASE_URL}/www/selectGosiList.do"
PAGE_SIZE = 10


class HanamGosiCrawler:
    """하남시청 고시공고 크롤러"""

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
            "key": "171",
            "not_ancmt_se_code": "01,04",
            "pageIndex": page,
        }
        if keyword:
            params["searchCnd"] = "SJ"
            params["searchKrwd"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 총 건수
        total_count = 0
        text = soup.get_text()
        m = re.search(r'총\s*(\d[\d,]*)\s*건', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        table = soup.select_one("table.p-table") or soup.select_one("table")
        if not table:
            return items, total_count

        rows = table.select("tbody tr")
        if not rows:
            rows = table.select("tr")[1:]

        for row in rows:
            cells = row.select("td")
            if len(cells) < 6:
                continue

            # 번호, 공고번호, 등록일, 제목, 담당부서, 게재기간
            number = cells[0].get_text(strip=True)

            if total_count == 0 and number.isdigit():
                total_count = int(number)

            # 등록일: "20260319" 형식 -> "2026-03-19"
            raw_date = cells[2].get_text(strip=True)
            if len(raw_date) == 8 and raw_date.isdigit():
                date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            else:
                date = raw_date

            # 제목 + 링크
            title_cell = cells[3]
            link = title_cell.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")
            if href.startswith("./"):
                detail_url = f"{BASE_URL}/www/{href[2:]}"
            elif href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href if href.startswith("http") else f"{LIST_URL}?key=171&not_ancmt_se_code=01,04"

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "하남시청",
            })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
        # 날짜 기본값 (최근 30일)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 {total_count}건)")

        all_items = []
        stop = False

        # 첫 페이지 날짜 필터
        for item in first_items:
            d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
            if not d:
                continue
            if d < start_date:
                stop = True
                continue
            if d <= end_date:
                all_items.append(item)

        # 나머지 페이지 순차 수집 + early stop
        if not stop and actual_pages > 1:
            page = 2
            while page <= actual_pages and not stop:
                # 배치 단위로 병렬 수집
                batch_end = min(page + self.WORKERS, actual_pages + 1)
                with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                    futures = {
                        executor.submit(self._fetch_page, keyword, p): p
                        for p in range(page, batch_end)
                    }
                    batch_results = {}
                    for future in as_completed(futures):
                        p = futures[future]
                        try:
                            items, _ = future.result()
                            if items:
                                batch_results[p] = items
                        except Exception:
                            pass

                # 페이지 순서대로 날짜 체크
                for p in sorted(batch_results.keys()):
                    for item in batch_results[p]:
                        d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
                        if not d:
                            continue
                        if d < start_date:
                            stop = True
                            break
                        if d <= end_date:
                            all_items.append(item)
                    if stop:
                        break

                page = batch_end

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[하남시청 고시공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = HanamGosiCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
