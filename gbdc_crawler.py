# -*- coding: utf-8 -*-
"""
경상북도개발공사 통합검색(게시판) 크롤러

Target: https://www.gbdc.co.kr/totalSearch.do
게시판 검색 탭(tapIdx=2), 키워드 필수, 10건/페이지
병렬 요청으로 빠른 크롤링
"""
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


class GBDCCrawler:
    """경상북도개발공사 통합검색 게시판 크롤러"""

    BASE_URL = "https://www.gbdc.co.kr/totalSearch.do"
    WORKERS = 10

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

    def _fetch_page(self, keyword: str, page: int):
        """Fetch a single page of search results."""
        params = {
            "searchKeywordTotal": keyword,
            "pageIndex": str(page),
            "tapIdx": "2",
            "seqId": "0000003893",
        }
        try:
            resp = self.session.get(self.BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as e:
            print(f"[ERROR] Failed to fetch page {page}: {e}")
            return None

    def _get_total_count(self, soup: BeautifulSoup) -> int:
        """Extract total count from '게시판 검색 (N)'."""
        for el in soup.select("*"):
            text = el.get_text(strip=True)
            if "게시판 검색" in text and "(" in text:
                m = re.search(r"게시판 검색\s*\((\d+)\)", text)
                if m:
                    return int(m.group(1))
        return 0

    def _parse_rows(self, soup: BeautifulSoup) -> list[dict]:
        """Parse search results from page."""
        results = []
        for a in soup.select("div.integrated-search a[href*='boardview']"):
            title = a.get_text(strip=True)
            href = a.get("href", "")
            url = f"https://www.gbdc.co.kr{href}" if href else ""

            date = ""
            parent = a.find_parent()
            gparent = parent.find_parent() if parent else None
            if gparent:
                for span in gparent.select("span, em, dd"):
                    t = span.get_text(strip=True)
                    if re.match(r"\d{4}[-./]\d{2}[-./]\d{2}", t):
                        date = t
                        break

            results.append({
                "number": "",
                "title": title,
                "date": date,
                "url": url,
                "organization": "경상북도개발공사",
            })

        return results

    def _fetch_and_parse(self, keyword: str, page: int) -> tuple[int, list[dict]]:
        """Fetch and parse a single page. Returns (page_number, rows)."""
        soup = self._fetch_page(keyword, page)
        if soup is None:
            return (page, [])
        return (page, self._parse_rows(soup))

    def search(self, keyword: str = "", max_pages: int = 10) -> list[dict]:
        """Search board posts.

        Args:
            keyword: Search keyword (required, empty returns 0 results).
            max_pages: Maximum pages to crawl.

        Returns:
            List of dicts with: number, title, date, url, organization.
        """
        if not keyword:
            return []

        soup = self._fetch_page(keyword, 1)
        if soup is None:
            return []

        total_count = self._get_total_count(soup)
        if total_count == 0:
            return []

        total_pages = min((total_count + 9) // 10, max_pages)
        first_rows = self._parse_rows(soup)

        page_results = {1: first_rows}

        if total_pages > 1:
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_and_parse, keyword, p): p
                    for p in range(2, total_pages + 1)
                }
                for future in as_completed(futures):
                    page_num, rows = future.result()
                    if rows:
                        page_results[page_num] = rows

        all_results = []
        for p in sorted(page_results.keys()):
            all_results.extend(page_results[p])

        return all_results


def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    import time

    crawler = GBDCCrawler()

    print("=" * 80)
    print('TEST: Keyword "공고" (max 20 pages, parallel)')
    print("=" * 80)
    start = time.time()
    results = crawler.search(keyword="공고", max_pages=20)
    elapsed = time.time() - start
    print(f"Total results: {len(results)}건, {elapsed:.1f}초")
    if results:
        print(f"First: {results[0]['date']} | {results[0]['title'][:50]}")
        print(f"Last:  {results[-1]['date']} | {results[-1]['title'][:50]}")

    assert isinstance(results, list)
    assert len(results) > 0
    required = {"number", "title", "date", "url", "organization"}
    assert required.issubset(results[0].keys())
    print("Validation passed.")


if __name__ == "__main__":
    main()
