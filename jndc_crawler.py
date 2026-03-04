"""
Crawler for 전남개발공사 (Jeonnam Development Corporation) 통합검색 > 게시판
Target URL: https://www.jndc.co.kr/cf/search.do

Search mechanism:
- Main search form POSTs to /cf/search.do with parameters:
    searchKeyword, pageIndex, detail, orderCondition
- Board search results are loaded via AJAX at /cf/search/board/dataAjax.do
- Title-only search uses detail=detail&orderCondition=title
- Each result page shows 5 items
- Dates and writer info are only available on detail pages
- Board number is extracted from the URL pattern /cf/Board/{number}/detailView.do
"""

import re
import logging
import requests
from typing import Optional
from html import unescape
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.jndc.co.kr"
BOARD_AJAX_URL = f"{BASE_URL}/cf/search/board/dataAjax.do"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def _strip_html(text: str) -> str:
    """Remove HTML tags and clean whitespace from a string."""
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class JNDCCrawler:
    """
    Crawler for 전남개발공사 통합검색 > 게시판 section.

    Uses the AJAX endpoint /cf/search/board/dataAjax.do for paginated
    board search results and fetches individual detail pages for date
    and organization information.
    """

    WORKERS = 10

    def __init__(self, timeout: int = 30):
        """
        Args:
            timeout: Request timeout in seconds.
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _fetch_board_page(
        self, keyword: str, page: int, title_only: bool = True
    ) -> str:
        """Fetch one page of board search results via AJAX.

        Args:
            keyword: Search keyword.
            page: 1-based page index.
            title_only: If True, search by title only (제목).

        Returns:
            HTML fragment containing the result list items.
        """
        data = {
            "searchKeyword": keyword,
            "pageIndex": str(page),
        }
        if title_only:
            data["detail"] = "detail"
            data["orderCondition"] = "title"
        else:
            data["detail"] = ""

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BASE_URL}/cf/search.do",
        }
        resp = self.session.post(
            BOARD_AJAX_URL,
            data=data,
            headers=headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.text

    def _parse_board_items(self, html: str) -> list[dict]:
        """Parse board search result items from an AJAX response HTML fragment.

        Each <li> contains:
          - <a href="/cf/Board/{id}/detailView.do" title="..."> for the link and title
          - <p> with a text snippet (no structured date/org in list view)

        Returns:
            A list of dicts with keys: title, url, number (board id).
        """
        items: list[dict] = []
        # Match each <li> block containing a board link
        li_pattern = re.compile(
            r'<li>\s*<a\s+href="(/cf/Board/(\d+)/detailView\.do)"'
            r'[^>]*title="([^"]*)"[^>]*class="subject"[^>]*>'
            r'(.*?)</a>',
            re.DOTALL,
        )
        for match in li_pattern.finditer(html):
            path = match.group(1)
            board_id = match.group(2)
            title_attr = unescape(match.group(3)).strip()
            url = BASE_URL + path

            items.append(
                {
                    "title": title_attr,
                    "url": url,
                    "number": int(board_id),
                }
            )
        return items

    def _get_last_page(self, html: str) -> int:
        """Extract the last page number from the pagination HTML.

        The pagination contains links like:
            onclick="pf_linkpage_board(320);return false;"
        The last page link has class="last".
        """
        last_match = re.search(
            r'class="last"\s+onclick="pf_linkpage_board\((\d+)\)', html
        )
        if last_match:
            return int(last_match.group(1))
        # Fallback: find the highest page number referenced
        pages = re.findall(r"pf_linkpage_board\((\d+)\)", html)
        if pages:
            return max(int(p) for p in pages)
        return 1

    def _fetch_detail(self, url: str) -> dict:
        """Fetch a detail page and extract date and organization info.

        Args:
            url: Full URL to the board detail page.

        Returns:
            A dict with 'date' and 'organization' keys.
        """
        result = {"date": "", "organization": ""}
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            html = resp.text

            # Extract date from: <span class="date">등록일 : 2026-02-20 </span>
            date_match = re.search(
                r'<span\s+class="date">[^:]*:\s*([\d]{4}-[\d]{2}-[\d]{2})',
                html,
            )
            if date_match:
                result["date"] = date_match.group(1).strip()

            # Extract organization/writer from: <span class="writer">작성자 : 곽수현</span>
            writer_match = re.search(
                r'<span\s+class="writer">[^:]*:\s*([^<]+)', html
            )
            if writer_match:
                result["organization"] = writer_match.group(1).strip()

        except requests.RequestException as e:
            logger.warning("Failed to fetch detail page %s: %s", url, e)

        return result

    def _fetch_and_parse_page(self, keyword: str, page: int) -> list[dict]:
        """Fetch and parse a single board search page."""
        try:
            html = self._fetch_board_page(keyword, page, title_only=True)
        except requests.RequestException as e:
            logger.error("Failed to fetch page %d: %s", page, e)
            return []
        return self._parse_board_items(html)

    def search(self, keyword: str = "", max_pages: int = 10) -> list[dict]:
        """Search the 게시판 (board) section of the unified search.

        Searches by title only (제목) when a keyword is provided.

        Args:
            keyword: Search keyword. The site requires a non-empty keyword.
            max_pages: Maximum number of result pages to fetch.

        Returns:
            A list of dicts, each containing:
                - title (str): Post title.
                - date (str): Registration date (YYYY-MM-DD).
                - url (str): Full URL to the detail page.
                - organization (str): Writer/author name if available.
                - number (int): Board post ID number.
        """
        if not keyword:
            logger.warning(
                "Empty keyword provided. The site requires a search keyword."
            )
            return []

        # Fetch page 1 to determine total pages
        logger.info("Fetching board search page 1 for keyword '%s'...", keyword)
        try:
            first_html = self._fetch_board_page(keyword, 1, title_only=True)
        except requests.RequestException as e:
            logger.error("Failed to fetch page 1: %s", e)
            return []

        first_items = self._parse_board_items(first_html)
        if not first_items:
            return []

        last_page = self._get_last_page(first_html)
        actual_pages = min(last_page, max_pages)
        logger.info("Total pages available: %d (fetching %d)", last_page, actual_pages)

        if actual_pages <= 1:
            all_items = first_items
        else:
            # Parallel fetch remaining pages
            page_results = {1: first_items}
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_and_parse_page, keyword, p): p
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

        # Parallel fetch detail pages to get date and organization
        logger.info("Fetching detail pages for %d items...", len(all_items))
        with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
            futures = {
                executor.submit(self._fetch_detail, item["url"]): i
                for i, item in enumerate(all_items)
            }
            done = 0
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    detail = future.result()
                    all_items[idx]["date"] = detail["date"]
                    all_items[idx]["organization"] = detail["organization"]
                except Exception:
                    pass
                done += 1
                if done % 20 == 0:
                    logger.info("  Detail progress: %d/%d", done, len(all_items))

        return all_items


def main():
    crawler = JNDCCrawler(timeout=30)

    keyword = "공고"
    max_pages = 2  # Fetch first 2 pages for testing (10 items)
    print(f"Searching for keyword: '{keyword}' (max {max_pages} pages)")
    print("=" * 80)

    results = crawler.search(keyword=keyword, max_pages=max_pages)

    print(f"\nTotal results fetched: {len(results)}")
    print("=" * 80)

    for i, item in enumerate(results, start=1):
        print(f"\n[{i}]")
        print(f"  Number : {item['number']}")
        print(f"  Title  : {item['title']}")
        print(f"  Date   : {item['date']}")
        print(f"  Org    : {item['organization']}")
        print(f"  URL    : {item['url']}")

    # Verify return type
    print("\n" + "=" * 80)
    print(f"Return type: {type(results).__name__}")
    if results:
        print(f"Item type  : {type(results[0]).__name__}")
        print(f"Item keys  : {list(results[0].keys())}")

    return results


if __name__ == "__main__":
    main()
