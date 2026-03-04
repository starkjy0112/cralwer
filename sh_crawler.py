"""
SH 서울주택도시공사 (Seoul Housing & Communities Corporation) 공고 및 공지 Crawler

Crawls announcements from:
https://www.i-sh.co.kr/main/lay2/program/S1T294C295/www/brd/m_241/list.do

POST-based board with pagination (10 items/page).
Search by title (srchTp=0).
Uses concurrent requests for faster crawling.
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


class SHCrawler:
    """Crawler for SH서울주택도시공사 공고 및 공지."""

    LIST_URL = "https://www.i-sh.co.kr/main/lay2/program/S1T294C295/www/brd/m_241/list.do"
    VIEW_URL = "https://www.i-sh.co.kr/main/lay2/program/S1T294C295/www/brd/m_241/view.do"
    WORKERS = 20  # 동시 요청 수

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        self.session.verify = False

    def _fetch_page(self, page: int, keyword: str = "") -> Optional[BeautifulSoup]:
        """Fetch a single page via POST."""
        data = {
            "page": str(page),
            "srchTp": "0",
            "srchWord": keyword,
        }
        try:
            resp = self.session.post(self.LIST_URL, data=data, timeout=30)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as e:
            print(f"[ERROR] Failed to fetch page {page}: {e}")
            return None

    def _get_total_pages(self, soup: BeautifulSoup) -> int:
        """Extract total page count from 'totalN건 [page/totalPages페이지]'."""
        mentcount = soup.select_one("div.mentcount")
        if mentcount:
            text = mentcount.get_text(strip=True)
            m = re.search(r'\[(\d+)/(\d+)페이지\]', text)
            if m:
                return int(m.group(2))
        return 1

    def _parse_rows(self, soup: BeautifulSoup) -> list[dict]:
        """Parse table rows from a page."""
        results = []
        tables = soup.select("table")
        if len(tables) < 2:
            return results

        rows = tables[1].select("tr")
        for row in rows:
            tds = row.select("td")
            if len(tds) < 5:
                continue

            number = tds[0].get_text(strip=True)
            if not number.isdigit():
                continue

            title_a = tds[1].select_one("a")
            if title_a:
                title = title_a.get_text(strip=True)
                onclick = title_a.get("onclick", "")
                seq_match = re.search(r"getDetailView\('(\d+)'\)", onclick)
                if seq_match:
                    seq = seq_match.group(1)
                    url = f"{self.VIEW_URL}?seq={seq}"
                else:
                    url = ""
            else:
                title = tds[1].get_text(strip=True)
                url = ""

            org = tds[2].get_text(strip=True)
            date = tds[3].get_text(strip=True)

            results.append({
                "number": number,
                "title": title,
                "date": date,
                "url": url,
                "organization": org,
            })

        return results

    def _fetch_and_parse(self, page: int, keyword: str) -> tuple[int, list[dict]]:
        """Fetch and parse a single page. Returns (page_number, rows)."""
        soup = self._fetch_page(page, keyword)
        if soup is None:
            return (page, [])
        return (page, self._parse_rows(soup))

    def search(self, keyword: str = "", max_pages: int = 10) -> list[dict]:
        """Search 공고 및 공지 board.

        Args:
            keyword: Search keyword for title. Empty string returns all.
            max_pages: Maximum pages to crawl.

        Returns:
            List of dicts with: number, title, date, url, organization.
        """
        # 1페이지를 먼저 가져와서 총 페이지 수 확인
        soup = self._fetch_page(1, keyword)
        if soup is None:
            return []

        total_pages = min(self._get_total_pages(soup), max_pages)
        first_rows = self._parse_rows(soup)
        if not first_rows:
            return []

        # 결과를 페이지 번호별로 저장
        page_results = {1: first_rows}

        # 나머지 페이지를 병렬로 가져오기
        if total_pages > 1:
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_and_parse, p, keyword): p
                    for p in range(2, total_pages + 1)
                }
                for future in as_completed(futures):
                    page_num, rows = future.result()
                    if rows:
                        page_results[page_num] = rows

        # 페이지 순서대로 정렬하여 합치기
        all_results = []
        for p in sorted(page_results.keys()):
            all_results.extend(page_results[p])

        return all_results


def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    import time

    crawler = SHCrawler()

    print("=" * 80)
    print('TEST: Keyword "공고" (all pages, concurrent)')
    print("=" * 80)
    start = time.time()
    results = crawler.search(keyword="공고", max_pages=1000)
    elapsed = time.time() - start
    print(f"Total results: {len(results)}건, 소요시간: {elapsed:.1f}초")
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
