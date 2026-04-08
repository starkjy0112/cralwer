# -*- coding: utf-8 -*-
"""
춘천도시공사 입찰정보(기타) 크롤러
https://www.cuc.or.kr/listBoard.do?divId=155
GET 기반, 10건/페이지
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.cuc.or.kr"
LIST_URL = f"{BASE_URL}/listBoard.do"
PAGE_SIZE = 15


class CUCBidCrawler:
    """춘천도시공사 입찰정보(기타) 크롤러"""

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
            "divId": "155",
            "pageIndex": page,
        }
        if keyword:
            params["searchWord"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # 총 건수: "Total 1109"
        total_count = 0
        m = re.search(r'Total\s*(\d[\d,]*)', soup.get_text(), re.IGNORECASE)
        if not m:
            m = re.search(r'총\s*(\d[\d,]*)', soup.get_text())
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        # ul.board-list > li.board-list-box 구조
        for li in soup.select("li.board-list-box"):
            link = li.select_one("a.board-list-lnk")
            if not link:
                continue

            data_id = link.get("data-id", "")
            detail_url = f"{BASE_URL}/viewBoard.do?divId=155&nttId={data_id}" if data_id else ""

            num_el = li.select_one(".board-list-item.num .cont")
            number = num_el.get_text(strip=True) if num_el else ""

            tit_el = li.select_one(".board-list-item.tit .cont")
            title = " ".join(tit_el.get_text().split()) if tit_el else ""

            date_el = li.select_one(".board-list-item.date .cont")
            date = date_el.get_text(strip=True) if date_el else ""

            writer_el = li.select_one(".board-list-item.writer .cont")
            author = " ".join(writer_el.get_text().split()) if writer_el else "춘천도시공사"

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": author,
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
        print(f"[춘천도시공사 입찰] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = CUCBidCrawler()
    print("=== 전체 조회 (3페이지) ===")
    results = crawler.search("", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")

    print("\n=== '공고' 검색 ===")
    results2 = crawler.search("공고", max_pages=3)
    for r in results2[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
