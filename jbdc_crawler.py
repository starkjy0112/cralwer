"""
Crawler for 전북개발공사 (Jeonbuk Development Corporation) 통합검색 > 게시판
Target URL: https://www.jbdc.co.kr/search/board.do?searchWrd=

The unified board search page returns all matching results in a single page
(no server-side pagination). Each result contains:
  - Board category (e.g., 공지사항, 입찰공고, 언론보도, etc.)
  - Title
  - Link to detail page (with bbsId and nttId parameters)

Note: The unified search list page does NOT provide dates.
Dates are only available on individual detail pages.
"""

from __future__ import annotations

import re
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.jbdc.co.kr"
SEARCH_URL = f"{BASE_URL}/search/board.do"
ITEMS_PER_PAGE = 10


class JBDCCrawler:
    """
    Crawler for 전북개발공사 통합검색 > 게시판.

    The unified search endpoint returns all matching results on a single HTML page.
    Since there is no server-side pagination, the `max_pages` parameter controls
    how many "virtual pages" of results to return, with each page containing
    up to 10 items.
    """

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
            "Referer": BASE_URL,
        })

    def _fetch_search_page(self, keyword: str) -> Optional[str]:
        """
        Fetch the unified board search page for the given keyword.

        Uses POST with stype=board and searchWrd=keyword.
        Falls back to GET if POST fails.

        Returns the HTML content as a string, or None on failure.
        """
        # Try POST first (matches the form's submit behavior)
        try:
            resp = self.session.post(
                SEARCH_URL,
                data={"stype": "board", "searchWrd": keyword},
                timeout=30,
            )
            resp.raise_for_status()
            resp.encoding = "utf-8"
            if "comm_search_ul" in resp.text:
                return resp.text
        except requests.RequestException as e:
            logger.warning("POST request failed: %s. Trying GET...", e)

        # Fallback: GET request
        try:
            resp = self.session.get(
                SEARCH_URL,
                params={"searchWrd": keyword},
                timeout=30,
            )
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp.text
        except requests.RequestException as e:
            logger.error("GET request also failed: %s", e)
            return None

    def _parse_results(self, html: str, keyword: str) -> List[Dict]:
        """
        Parse the search result HTML and extract items.

        Each <li> in <ul class="comm_search_ul"> has the structure:
            <li>
              <span class="color_b">[카테고리]</span>
              <a href="/search/view.do?searchWrd=...&bbsId=...&nttId=...">
                제목
                <span class="mgl-20 comm_search_more">내용 자세히보기</span>
              </a>
            </li>

        Returns a list of dicts with keys:
            title, date, url, organization, number
        """
        soup = BeautifulSoup(html, "html.parser")
        results: List[Dict] = []

        # Extract total count for logging
        total_tag = soup.find("p", class_="comm_search_title")
        if total_tag:
            strong_tags = total_tag.find_all("strong")
            if len(strong_tags) >= 2:
                total_count = strong_tags[1].get_text(strip=True)
                logger.info(
                    "Search keyword '%s': total %s results found on server.",
                    keyword,
                    total_count,
                )

        # Find the result list
        result_list = soup.find("ul", class_="comm_search_ul")
        if not result_list:
            logger.warning("No result list (ul.comm_search_ul) found in HTML.")
            return results

        items = result_list.find_all("li")
        for idx, li in enumerate(items, start=1):
            # Extract organization/category: text inside <span class="color_b">
            org_span = li.find("span", class_="color_b")
            organization = ""
            if org_span:
                raw_org = org_span.get_text(strip=True)
                # Remove brackets: [공지사항] -> 공지사항
                organization = raw_org.strip("[]")

            # Extract title and URL from <a> tag
            link_tag = li.find("a")
            if not link_tag:
                continue

            href = link_tag.get("href", "")
            url = urljoin(BASE_URL, href) if href else ""

            # Extract title text, excluding the "내용 자세히보기" span
            # Clone the tag to avoid modifying the original
            title_parts = []
            for child in link_tag.children:
                if hasattr(child, "attrs") and "comm_search_more" in child.get("class", []):
                    continue
                text = child.get_text(strip=True) if hasattr(child, "get_text") else str(child).strip()
                if text:
                    title_parts.append(text)
            title = " ".join(title_parts).strip()

            # Extract nttId from URL as the item number
            ntt_id = ""
            ntt_match = re.search(r"nttId=(\d+)", href)
            if ntt_match:
                ntt_id = ntt_match.group(1)

            results.append({
                "title": title,
                "date": "",  # Not available in unified search list
                "url": url,
                "organization": organization,
                "number": ntt_id,
            })

        return results

    WORKERS = 10

    def _fetch_date(self, url: str) -> str:
        """상세 페이지에서 등록일 추출"""
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            for th in soup.select("th"):
                if "등록일" in th.get_text(strip=True):
                    td = th.find_next_sibling("td")
                    if td:
                        date_text = td.get_text(strip=True)
                        m = re.match(r"(\d{4}[./-]\d{2}[./-]\d{2})", date_text)
                        if m:
                            return m.group(1).replace(".", "-").replace("/", "-")
        except Exception:
            pass
        return ""

    def _fetch_dates_parallel(self, results: List[Dict]):
        """상세 페이지에서 날짜를 병렬로 가져오기"""
        urls = [(i, r["url"]) for i, r in enumerate(results) if r["url"]]
        if not urls:
            return

        with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
            futures = {
                executor.submit(self._fetch_date, url): idx
                for idx, url in urls
            }
            done = 0
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    date = future.result()
                    if date:
                        results[idx]["date"] = date
                except Exception:
                    pass
                done += 1
                if done % 50 == 0:
                    logger.info("  날짜 조회 진행: %d/%d", done, len(urls))

    def search(self, keyword: str = "", max_pages: int = 10) -> List[Dict]:
        """
        Search the 전북개발공사 unified board search (통합검색 > 게시판).

        Args:
            keyword: Search keyword. Empty string returns all posts.
            max_pages: Maximum number of virtual pages to return.
                       Each page contains up to 10 items.
                       The unified search returns all results at once
                       (no server-side pagination), so this parameter
                       limits the total number of returned items to
                       max_pages * 10.

        Returns:
            A list of dicts, each containing:
                - title (str): Post title
                - date (str): Empty string (not available in unified search)
                - url (str): Full URL to the detail page
                - organization (str): Board category (e.g., 공지사항, 입찰공고)
                - number (str): Post ID (nttId)
        """
        logger.info(
            "Starting search: keyword='%s', max_pages=%d", keyword, max_pages
        )

        html = self._fetch_search_page(keyword)
        if not html:
            logger.error("Failed to fetch search page.")
            return []

        all_results = self._parse_results(html, keyword)
        max_items = max_pages * ITEMS_PER_PAGE
        limited_results = all_results[:max_items]

        logger.info(
            "Parsed %d total results, returning %d (max_pages=%d, %d items/page).",
            len(all_results),
            len(limited_results),
            max_pages,
            ITEMS_PER_PAGE,
        )

        # 상세 페이지에서 날짜 병렬 조회
        if limited_results:
            logger.info("날짜 조회 시작 (%d건, %d workers)...", len(limited_results), self.WORKERS)
            self._fetch_dates_parallel(limited_results)

        return limited_results


if __name__ == "__main__":
    crawler = JBDCCrawler()

    keyword = "공고"
    print(f"{'='*80}")
    print(f"  전북개발공사 통합검색 > 게시판 Crawler Test")
    print(f"  Keyword: '{keyword}'")
    print(f"{'='*80}\n")

    results = crawler.search(keyword=keyword, max_pages=3)

    print(f"Total results returned: {len(results)}\n")
    print(f"{'='*80}")

    for i, item in enumerate(results, start=1):
        print(f"\n[{i}]")
        print(f"  Title        : {item['title']}")
        print(f"  Date         : {item['date'] or '(N/A - unified search)'}")
        print(f"  URL          : {item['url']}")
        print(f"  Organization : {item['organization']}")
        print(f"  Number       : {item['number']}")

    print(f"\n{'='*80}")
    print(f"Test complete. {len(results)} items retrieved.")
    print(f"{'='*80}")
