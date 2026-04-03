# -*- coding: utf-8 -*-
"""
합천군청 고시공고 크롤러
https://www.hc.go.kr/04923/04924/04948.web
GET 기반, div.list1f1t3i1, 10건/페이지, cpage 파라미터
"""
import math
import re
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.hc.go.kr"
LIST_URL = f"{BASE_URL}/04923/04924/04948.web"
PAGE_SIZE = 10
ORGANIZATION_NAME = "합천군청"


class HapcheonCrawler:
    """합천군청 고시공고 크롤러"""

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
            "cpage": str(page),
        }
        if keyword:
            params["stype"] = "title"
            params["sstring"] = keyword

        resp = self.session.get(LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        total_count = 0
        items = []

        # 페이지네이션에서 최대 페이지 추출
        page_links = [a for a in soup.select("a") if "cpage=" in a.get("href", "")]
        max_page = 0
        for a in page_links:
            href = a.get("href", "")
            m = re.search(r'cpage=(\d+)', href)
            if m:
                p = int(m.group(1))
                if p > max_page:
                    max_page = p
        if max_page > 0:
            total_count = max_page * PAGE_SIZE

        # div.list1f1t3i1 안의 a 태그들
        items_div = soup.select_one("div.list1f1t3i1")
        if not items_div:
            return items, total_count

        links = [a for a in items_div.select("a") if "amode=view" in a.get("href", "")]
        for a in links:
            href = a.get("href", "")
            title_span = a.select_one("span.wrap1texts")
            if not title_span:
                continue

            # 제목: <strong> 태그 또는 첫 텍스트 노드
            title = ""
            strong = title_span.find("strong")
            if strong:
                title = strong.get_text(strip=True)
            else:
                for child in title_span.children:
                    if isinstance(child, str):
                        title = child.strip()
                        if title:
                            break

            # 메타데이터
            meta_spans = title_span.select("span.t3")
            number = ""
            date = ""
            for sp in meta_spans:
                txt = sp.get_text(strip=True)
                if "고시번호" in txt and ":" in txt:
                    number = txt.split(":", 1)[1].strip()
                elif "등록일" in txt and ":" in txt:
                    date = txt.split(":", 1)[1].strip()

            # URL
            if href.startswith("?"):
                detail_url = f"{LIST_URL}{href}"
            elif href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href if href.startswith("http") else LIST_URL

            if not number and page == 1:
                # 번호 없으면 ID 추출
                m_id = re.search(r'not_ancmt_mgt_no=(\d+)', href)
                if m_id:
                    number = m_id.group(1)

            items.append({
                "number": number,
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": ORGANIZATION_NAME,
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
        print(f"[{ORGANIZATION_NAME} 고시공고] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = HapcheonCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=1)
    for r in results[:3]:
        print(f"  [{r['date']}] {r['title'][:50]}")
