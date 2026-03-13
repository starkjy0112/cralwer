# -*- coding: utf-8 -*-
"""
GH 경기주택도시공사 통합검색 크롤러
https://www.gh.or.kr/gh/search.do
AJAX 기반: /gh/search/ajax/result.do
카테고리: menu, content, board, attach
"""
import math
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.gh.or.kr"
SEARCH_URL = f"{BASE_URL}/gh/search.do"
AJAX_URL = f"{BASE_URL}/gh/search/ajax/result.do"

# 크롤링 대상 카테고리 (staff 제외 - 항상 0건)
CATEGORIES = {
    "menu": "메뉴",
    "content": "웹페이지",
    "board": "게시판",
    "attach": "첨부파일",
}


class GHCrawler:
    """GH 경기주택도시공사 통합검색 크롤러"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })
        self.session.verify = False

    def _init_session(self, keyword):
        """검색 페이지를 GET해서 세션 쿠키와 카테고리별 총 건수를 확보합니다."""
        resp = self.session.get(
            SEARCH_URL,
            params={"keyword": keyword, "mode": "list"},
            timeout=30,
        )
        resp.encoding = "utf-8"
        # 카테고리별 총 건수 추출
        self._cat_totals = {}
        for cat, name in CATEGORIES.items():
            m = re.search(
                r'<span[^>]*>' + name + r'</span>.*?총\s*<strong[^>]*>([\d,]+)</strong>\s*건',
                resp.text, re.DOTALL,
            )
            self._cat_totals[cat] = int(m.group(1).replace(",", "")) if m else 0

    def _fetch_page(self, keyword, cat, page, total_count):
        """AJAX로 특정 카테고리의 한 페이지를 가져옵니다."""
        self.session.headers["X-Requested-With"] = "XMLHttpRequest"
        self.session.headers["Referer"] = SEARCH_URL

        resp = self.session.post(
            AJAX_URL,
            data={
                "keyword": keyword,
                "cat": cat,
                "pageNo": str(page),
                "totalCount": str(total_count),
            },
            timeout=30,
        )
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        items = []
        for li in soup.select(".search-result-wrap li"):
            a = li.select_one("a")
            if not a:
                continue

            tit_el = a.select_one(".tit")
            loc_el = a.select_one(".location")
            content_el = a.select_one(".content")

            title = tit_el.get_text(strip=True) if tit_el else ""
            organization = loc_el.get_text(strip=True) if loc_el else ""
            href = a.get("href", "")
            url = f"{BASE_URL}{href}" if href.startswith("/") else href

            # content에서 날짜 추출 시도
            date = ""
            if content_el:
                content_text = content_el.get_text(strip=True)
                dm = re.search(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', content_text)
                if dm:
                    date = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
                else:
                    dm = re.search(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', content_text)
                    if dm:
                        date = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"

            items.append({
                "number": "",
                "title": title,
                "date": date,
                "url": url,
                "organization": organization,
            })

        return items

    WORKERS = 5

    def _fetch_category(self, keyword, cat, max_pages):
        """한 카테고리의 모든 페이지를 가져옵니다."""
        total_count = self._cat_totals.get(cat, 0)
        if total_count == 0:
            return []

        total_pages = max(1, math.ceil(total_count / 10))
        actual_pages = min(total_pages, max_pages)

        first_items = self._fetch_page(keyword, cat, 1, total_count)
        print(f"  [{CATEGORIES[cat]}] Page 1/{actual_pages} - {len(first_items)}건 (전체 {total_count}건)")

        if actual_pages <= 1:
            return first_items

        page_results = {1: first_items}
        with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
            futures = {
                executor.submit(self._fetch_page, keyword, cat, p, total_count): p
                for p in range(2, actual_pages + 1)
            }
            for future in as_completed(futures):
                p = futures[future]
                try:
                    items = future.result()
                    if items:
                        page_results[p] = items
                except Exception:
                    pass

        all_items = []
        for p in sorted(page_results.keys()):
            all_items.extend(page_results[p])
        return all_items

    def search(self, keyword="", max_pages=10):
        """통합검색 (모든 카테고리)을 실행합니다."""
        if not keyword:
            keyword = " "

        self._init_session(keyword)
        total = sum(self._cat_totals.values())
        print(f"  [경기주택도시공사] 전체 {total}건 "
              + " / ".join(f"{n}:{c}건" for n, c in
                           [(CATEGORIES[k], v) for k, v in self._cat_totals.items() if v > 0]))

        all_items = []
        for cat in CATEGORIES:
            items = self._fetch_category(keyword, cat, max_pages)
            all_items.extend(items)

        all_items.sort(key=lambda x: x["date"], reverse=True)
        print(f"[경기주택도시공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")

    crawler = GHCrawler()
    print("=== '공고' 검색 (3페이지) ===")
    results = crawler.search("공고", max_pages=3)
    for r in results[:10]:
        print(f"  [{r['date']}] {r['title'][:50]} | {r['organization'][:30]}")
