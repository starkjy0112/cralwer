# -*- coding: utf-8 -*-
"""
여수시청 통합검색 크롤러
https://www.yeosu.go.kr/total_search/total_search.html?query=&collection=ysboard
GET 기반, HTML 파싱, startCount 파라미터 (0, 10, 20...), li 기반 결과
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.yeosu.go.kr"
SEARCH_URL = f"{BASE_URL}/total_search/total_search.html"
PAGE_SIZE = 10
ORGANIZATION_NAME = "여수시청"


class YeosuCrawler:
    """여수시청 통합검색 크롤러"""

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
        start_count = (page - 1) * PAGE_SIZE
        params = {
            "query": keyword or "",
            "collection": "ALL",
            "sortField": "DATE",
            "searchField": "ALL",
            "startCount": str(start_count),
            "startDate": "1980/01/01",
            "endDate": "2030/12/31",
        }

        resp = self.session.get(SEARCH_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        # 카테고리별 "총 N건"을 합산
        all_counts = re.findall(r'총\s*([\d,]+)\s*건', resp.text)
        for c_str in all_counts:
            total_count += int(c_str.replace(",", ""))

        items = []
        # Results are in <ul> > <li> with h4 > span.site_name + a > span.tit + span.date
        result_lis = soup.select("ul li")
        for li in result_lis:
            h4 = li.select_one("h4")
            if not h4:
                continue
            link = h4.select_one("a[href]")
            if not link:
                continue
            href = link.get("href", "")
            if "mode=view" not in href and "yeosu.go.kr" not in href:
                continue

            tit_span = link.select_one("span.tit")
            title = tit_span.get_text(strip=True) if tit_span else link.get_text(strip=True)
            # Clean highlight spans
            title = re.sub(r'<[^>]+>', '', title)

            date_span = h4.select_one("span.date")
            date = ""
            if date_span:
                date_text = date_span.get_text(strip=True)
                m = re.search(r'(\d{4}-\d{2}-\d{2})', date_text)
                if m:
                    date = m.group(1)

            site_span = h4.select_one("span.site_name")
            org = site_span.get_text(strip=True) if site_span else ORGANIZATION_NAME

            # Path info for category
            path_link = li.select_one("a[href*='mode=view']")
            if not path_link:
                path_link = link

            detail_url = href if href.startswith("http") else f"{BASE_URL}{href}"

            items.append({
                "number": "",
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": org if org else ORGANIZATION_NAME,
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
        print(f"[{ORGANIZATION_NAME}] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = YeosuCrawler()
    results = crawler.search("공고", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization']}")
