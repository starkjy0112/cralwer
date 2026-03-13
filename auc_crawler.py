# -*- coding: utf-8 -*-
"""
안양도시공사 통합검색 크롤러
https://www.auc.or.kr/base/search/view?searchType=BOARD
GET 기반, 게시판 검색
"""
import re
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.auc.or.kr"
SEARCH_URL = f"{BASE_URL}/base/search/view"


class AUCCrawler:
    """안양도시공사 통합검색 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })

    def _fetch_page(self, keyword, page):
        params = {
            "searchType": "TOTAL",
            "menuLevel": "2",
            "menuNo": "348",
            "searchWord": keyword,
            "pageIndex": page,
        }
        resp = self.session.get(SEARCH_URL, params=params, timeout=30)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 총 건수: 전체(N) 또는 총 N 건
        total_count = 0
        text = soup.get_text()
        m = re.search(r'총\s*(\d[\d,]*)\s*건', text)
        if not m:
            m = re.search(r'전체\s*\(\s*(\d[\d,]*)\s*\)', text)
        if m:
            total_count = int(m.group(1).replace(",", ""))

        items = []
        result_list = soup.select(".sch_result_page_list.type2 li, .sch_result_page_list li")
        for li in result_list:
            title_a = li.select_one("p.tit a")
            if not title_a:
                continue

            title = title_a.get_text(strip=True)
            href = title_a.get("href", "")
            detail_url = f"{BASE_URL}{href}" if href.startswith("/") else href

            # 날짜 추출
            date = ""
            txt_p = li.select_one("p.txt")
            if txt_p:
                m2 = re.search(r'(\d{4}[-./]\d{1,2}[-./]\d{1,2})', txt_p.get_text())
                if m2:
                    date = m2.group(1)

            items.append({
                "number": "",
                "title": title,
                "date": date,
                "url": detail_url,
                "organization": "안양도시공사",
            })

        return items, total_count

    def search(self, keyword="", max_pages=10):
        if not keyword:
            print("[안양도시공사] 통합검색은 키워드가 필요합니다")
            return []

        first_items, total_count = self._fetch_page(keyword, 1)
        print(f"  [Page 1] {len(first_items)}건 수집 (전체 {total_count}건)")

        all_items = first_items
        page = 2
        while page <= max_pages and len(all_items) < total_count:
            items, _ = self._fetch_page(keyword, page)
            if not items:
                break
            all_items.extend(items)
            page += 1

        print(f"[안양도시공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = AUCCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고", max_pages=3)
    for r in results[:5]:
        print(f"  [{r['date']}] {r['title'][:50]}")
