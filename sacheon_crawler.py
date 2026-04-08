# -*- coding: utf-8 -*-
"""
사천시청 공고/고시/시험 크롤러
https://www.sacheon.go.kr/news/00009/00014.web
GET 기반, div.list1f1t3i1, 10건/페이지, cpage 파라미터
"""
import math
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.sacheon.go.kr"
LIST_URL = f"{BASE_URL}/news/00009/00014.web"
PAGE_SIZE = 10
ORGANIZATION_NAME = "사천시청"


class SacheonCrawler:
    """사천시청 공고/고시/시험 크롤러"""

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
        params = {"cpage": str(page)}
        if keyword:
            params["stype"] = "title"
            params["sstring"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []

        text = soup.get_text()
        m = re.search(r'총\s*(\d[\d,]*)\s*건', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items_div = soup.select_one("div.list1f1t3i1")
        if not items_div:
            return items, total_count

        links = [a for a in items_div.select("a") if "amode=view" in a.get("href", "")]
        for a in links:
            href = a.get("href", "")
            title_span = a.select_one("span.wrap1texts")
            if not title_span:
                continue

            title = ""
            strong = title_span.find("strong")
            if strong:
                title = re.sub(r'\s+', ' ', strong.get_text(strip=True)).strip()

            meta_spans = title_span.select("span.t3")
            number = ""
            date = ""
            for sp in meta_spans:
                txt = sp.get_text(strip=True)
                if "고시번호" in txt and ":" in txt:
                    number = txt.split(":", 1)[1].strip()
                elif re.match(r'\d{4}-\d{2}-\d{2}', txt):
                    date = txt.strip()
                elif "등록일" in txt and ":" in txt:
                    date = txt.split(":", 1)[1].strip().replace(".", "-")

            # 날짜가 없으면 첫 번째 날짜 패턴 span.t3에서 추출
            if not date:
                for sp in meta_spans:
                    txt = sp.get_text(strip=True)
                    dm = re.search(r'(\d{4}[-./]\d{2}[-./]\d{2})', txt)
                    if dm:
                        date = dm.group(1).replace(".", "-")
                        break

            if href.startswith("?"):
                detail_url = f"{LIST_URL}{href}"
            elif href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href if href.startswith("http") else LIST_URL

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": ORGANIZATION_NAME,
            })

        return items, total_count

    WORKERS = 20

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
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
        print(f"[{ORGANIZATION_NAME} 공고/고시] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = SacheonCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n=== '용역' 검색 ===")
    results2 = crawler.search("용역", max_pages=1)
    for r in results2[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
    print(f"\n공고: {len(results)}건, 용역: {len(results2)}건")
