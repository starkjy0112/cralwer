"""
Crawler for Saemangeum Development Corporation (새만금개발공사) 고시/공고 board.

Target: https://www.sdco.or.kr/board.es?mid=a10601020000&bid=0007
"""

import requests
from bs4 import BeautifulSoup
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


class SDCOCrawler:
    """Crawler for SDCO (새만금개발공사) 고시/공고 announcements."""

    BASE_URL = "https://www.sdco.or.kr/board.es"
    MID = "a10601020000"
    BID = "0007"

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

    def _get_total_pages(self, soup: BeautifulSoup) -> int:
        """Extract total page count from the page info section."""
        page_info = soup.select_one("p.page span.current b")
        if page_info:
            try:
                return int(page_info.text.strip())
            except ValueError:
                pass
        return 1

    def _parse_rows(self, soup: BeautifulSoup, page: int) -> list[dict]:
        """Parse table rows from a single page into list of dicts."""
        results = []
        rows = soup.select("div.board-list table tbody tr")

        for row in rows:
            tds = row.select("td")
            if len(tds) < 4:
                continue

            # Extract number (번호)
            number_text = tds[0].text.strip()

            # Extract title and URL (제목)
            title_td = tds[1]
            title_a = title_td.select_one("a")
            if title_a:
                title = title_a.text.strip()
                href = title_a.get("href", "")
                if href and not href.startswith("http"):
                    url = f"https://www.sdco.or.kr{href}"
                else:
                    url = href
            else:
                title = title_td.text.strip()
                url = ""

            # Extract organization/author (작성자)
            organization = tds[2].text.strip() if len(tds) > 2 else ""

            # Extract date (등록일)
            date = tds[3].text.strip() if len(tds) > 3 else ""

            results.append({
                "number": number_text,
                "title": title,
                "date": date,
                "url": url,
                "organization": organization,
            })

        return results

    def _fetch_page(
        self,
        page: int,
        keyword: str = "",
    ) -> Optional[BeautifulSoup]:
        """Fetch a single page of results, optionally with a keyword filter."""
        params = {
            "mid": self.MID,
            "bid": self.BID,
            "nPage": str(page),
        }
        if keyword:
            params["keyField"] = "T"  # 제목 (title search only)
            params["keyWord"] = keyword

        try:
            resp = self.session.get(self.BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as e:
            print(f"[ERROR] Failed to fetch page {page}: {e}")
            return None

    WORKERS = 5

    def _fetch_and_parse(self, page: int, keyword: str) -> list[dict]:
        """페이지 조회 + 파싱"""
        soup = self._fetch_page(page, keyword)
        if soup is None:
            return []
        return self._parse_rows(soup, page)

    def search(self, keyword: str = "", max_pages: int = 10) -> list[dict]:
        """
        Search 고시/공고 board by title keyword.

        Args:
            keyword: Search keyword for title field. Empty string returns all items.
            max_pages: Maximum number of pages to crawl (default: 10).

        Returns:
            List of dicts, each containing:
                - number: Post number (번호)
                - title: Post title (제목)
                - date: Registration date (등록일)
                - url: Full URL to the post detail page
                - organization: Author/department (작성자)
        """
        soup = self._fetch_page(1, keyword)
        if soup is None:
            return []

        total_pages = self._get_total_pages(soup)
        actual_pages = min(total_pages, max_pages)
        first_results = self._parse_rows(soup, 1)

        if not first_results or actual_pages <= 1:
            return first_results

        # 나머지 페이지 병렬 조회
        page_results = {1: first_results}
        with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
            futures = {
                executor.submit(self._fetch_and_parse, p, keyword): p
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

        all_results = []
        for p in sorted(page_results.keys()):
            all_results.extend(page_results[p])

        return all_results


def main():
    crawler = SDCOCrawler()

    # Test 1: Empty keyword (all items)
    print("=" * 80)
    print("TEST 1: Search with empty keyword (all items, max 10 pages)")
    print("=" * 80)
    results = crawler.search(keyword="", max_pages=10)
    print(f"Total results fetched: {len(results)}")
    print(f"Return type: {type(results)}")
    if results:
        print(f"Item type: {type(results[0])}")
        print()
        print("First 5 results:")
        for i, item in enumerate(results[:5], 1):
            print(f"  [{i}]")
            print(f"      number:       {item['number']}")
            print(f"      title:        {item['title']}")
            print(f"      date:         {item['date']}")
            print(f"      organization: {item['organization']}")
            print(f"      url:          {item['url']}")
        print()
        print("Last 3 results:")
        for i, item in enumerate(results[-3:], len(results) - 2):
            print(f"  [{i}]")
            print(f"      number:       {item['number']}")
            print(f"      title:        {item['title']}")
            print(f"      date:         {item['date']}")
            print(f"      organization: {item['organization']}")
            print(f"      url:          {item['url']}")

    print()
    print("=" * 80)
    print('TEST 2: Search with keyword "공고"')
    print("=" * 80)
    results_keyword = crawler.search(keyword="공고", max_pages=10)
    print(f"Total results fetched: {len(results_keyword)}")
    print(f"Return type: {type(results_keyword)}")
    if results_keyword:
        print(f"Item type: {type(results_keyword[0])}")
        print()
        print("First 5 results:")
        for i, item in enumerate(results_keyword[:5], 1):
            print(f"  [{i}]")
            print(f"      number:       {item['number']}")
            print(f"      title:        {item['title']}")
            print(f"      date:         {item['date']}")
            print(f"      organization: {item['organization']}")
            print(f"      url:          {item['url']}")
        print()
        print("Last 3 results:")
        for i, item in enumerate(results_keyword[-3:], len(results_keyword) - 2):
            print(f"  [{i}]")
            print(f"      number:       {item['number']}")
            print(f"      title:        {item['title']}")
            print(f"      date:         {item['date']}")
            print(f"      organization: {item['organization']}")
            print(f"      url:          {item['url']}")

    # Validation checks
    print()
    print("=" * 80)
    print("VALIDATION")
    print("=" * 80)
    assert isinstance(results, list), "Results must be a list"
    assert isinstance(results_keyword, list), "Keyword results must be a list"
    if results:
        assert isinstance(results[0], dict), "Each item must be a dict"
        required_keys = {"number", "title", "date", "url", "organization"}
        assert required_keys.issubset(results[0].keys()), (
            f"Missing keys: {required_keys - results[0].keys()}"
        )
    if results_keyword:
        assert isinstance(results_keyword[0], dict), "Each keyword item must be a dict"
    print("All validations passed.")
    print(f"  - Empty keyword returned {len(results)} items (list[dict])")
    print(f'  - Keyword "공고" returned {len(results_keyword)} items (list[dict])')


if __name__ == "__main__":
    main()
