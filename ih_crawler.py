# -*- coding: utf-8 -*-
"""
인천도시공사 게시물 검색 크롤러
https://www.ih.co.kr/search/searchBbs.do?query=
GET 기반, 10건/페이지, pgno 파라미터
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.ih.co.kr"
SEARCH_URL = f"{BASE_URL}/search/searchBbs.do"
PAGE_SIZE = 10


class IHCrawler:
    """인천도시공사 게시물 검색 크롤러"""

    WORKERS = 20

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
            "query": keyword,
            "pgno": page,
        }
        resp = self.session.get(SEARCH_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        m = re.search(r'(\d[\d,]*)\s*건', soup.get_text())
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        for dl in soup.find_all("dl"):
            dt = dl.find("dt")
            if not dt:
                continue

            link = dt.find("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            if not title:
                continue

            href = link.get("href", "")
            detail_url = f"{BASE_URL}{href}" if href.startswith("/") else href

            date = ""
            dds = dl.find_all("dd")
            for dd in dds:
                m2 = re.search(r'(\d{4}[-./]\d{1,2}[-./]\d{1,2})', dd.get_text())
                if m2:
                    date = m2.group(1)
                    break

            items.append({
                "number": "",
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "인천도시공사",
            })

        return items, total_count

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
        if not keyword:
            print("[인천도시공사] 통합검색은 키워드가 필요합니다")
            return []

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
        print(f"[인천도시공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = IHCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
