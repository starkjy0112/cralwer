"""
Crawler for 한국농어촌공사 (Korea Rural Community Corporation) 공지사항.
Target: https://www.ekr.or.kr/planweb/board/list.krc
"""

import re
import warnings
from urllib.parse import urljoin, parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# Suppress SSL warnings for this site
warnings.filterwarnings("ignore", message="Unverified HTTPS request")
warnings.filterwarnings("ignore", category=DeprecationWarning)


class EkrCrawler:
    """한국농어촌공사 공지사항 크롤러"""

    BASE_URL = "https://www.ekr.or.kr/planweb/board/"
    LIST_URL = "https://www.ekr.or.kr/planweb/board/list.krc"

    # Fixed board parameters
    BOARD_PARAMS = {
        "boardUid": "402880317cc0644a017cc5e8000f06b7",
        "contentUid": "402880317cc0644a017cc0c9da9f0120",
        "categoryUid2": "8a8bb3529665d71401996fb31ede7592",
        "categoryUid3": "8a8bb3529665d7140199700049800553",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )
        self.session.verify = False

    WORKERS = 5

    def search(self, keyword="", max_pages=10):
        """
        Search 공지사항 by title keyword.

        Args:
            keyword: Search keyword for title search (제목). Empty string returns all.
            max_pages: Maximum number of pages to crawl.

        Returns:
            list[dict]: List of dicts with keys: title, date, url, organization, number
        """
        first_items, total_pages = self._fetch_page(keyword, 1)
        actual_pages = min(total_pages, max_pages)

        if actual_pages <= 1:
            raw_items = first_items
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

            raw_items = []
            for p in sorted(page_results.keys()):
                raw_items.extend(page_results[p])

        # Deduplicate pinned/notice posts that appear on every page
        all_items = []
        seen_data_uids = set()
        for item in raw_items:
            data_uid = self._extract_data_uid(item["url"])
            if data_uid and data_uid not in seen_data_uids:
                seen_data_uids.add(data_uid)
                all_items.append(item)
            elif not data_uid:
                dedup_key = (item["title"], item["date"])
                if dedup_key not in seen_data_uids:
                    seen_data_uids.add(dedup_key)
                    all_items.append(item)

        all_items.sort(key=lambda x: x["date"], reverse=True)
        return all_items

    def _fetch_page(self, keyword, page):
        """
        Fetch a single page of board listings.

        Args:
            keyword: Search keyword.
            page: Page number (1-based).

        Returns:
            tuple: (list of item dicts, total number of pages)
        """
        params = {
            **self.BOARD_PARAMS,
            "page": str(page),
            "searchType": "dataTitle" if keyword else "",
            "keyword": keyword,
        }

        resp = self.session.get(self.LIST_URL, params=params, timeout=15)
        resp.encoding = "utf-8"
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        items = self._parse_items(soup)
        total_pages = self._parse_total_pages(soup)

        return items, total_pages

    def _parse_items(self, soup):
        """Parse board items from the table."""
        items = []

        table = soup.find("table", class_="bbs_table")
        if not table:
            return items

        tbody = table.find("tbody")
        if not tbody:
            return items

        rows = tbody.find_all("tr")
        for row in rows:
            tds = row.find_all("td")
            if len(tds) < 5:
                continue

            item = self._parse_row(tds)
            if item:
                items.append(item)

        return items

    def _parse_row(self, tds):
        """Parse a single table row into a dict."""
        num_td = tds[0]
        title_td = tds[1]
        author_td = tds[2]
        date_td = tds[4]

        # Number: either a numeric value or "공지" for pinned posts
        is_notice = "icoNotice" in num_td.get("class", [])
        number = num_td.get_text(strip=True)
        if is_notice:
            number = "공지"

        # Title and URL
        title_link = title_td.find("a")
        if not title_link:
            return None

        title = title_link.get_text(strip=True)
        href = title_link.get("href", "")
        url = urljoin(self.BASE_URL, href) if href else ""

        # Date
        date = date_td.get_text(strip=True)

        # Organization (작성자 / author)
        organization = author_td.get_text(strip=True)

        return {
            "title": title,
            "date": date,
            "url": url,
            "organization": organization,
            "number": number,
        }

    @staticmethod
    def _extract_data_uid(url):
        """Extract dataUid parameter from a URL for deduplication."""
        match = re.search(r"dataUid=([^&]+)", url)
        return match.group(1) if match else None

    def _parse_total_pages(self, soup):
        """Parse the total number of pages from the pagination div."""
        paging = soup.find("div", class_="paging")
        if not paging:
            return 1

        # The "btn_end" (끝) link contains the last page number in its href
        btn_end = paging.find("a", class_="btn_end")
        if btn_end:
            href = btn_end.get("href", "")
            match = re.search(r"page=(\d+)", href)
            if match:
                return int(match.group(1))

        # Fallback: find the highest numbered page link
        max_page = 1
        for link in paging.find_all("a"):
            classes = link.get("class", [])
            if any(
                c in classes
                for c in ["btn_start", "btn_prev", "btn_next", "btn_end"]
            ):
                continue
            text = link.get_text(strip=True)
            if text.isdigit():
                max_page = max(max_page, int(text))

        return max_page


if __name__ == "__main__":
    crawler = EkrCrawler()

    # Test 1: Empty keyword (all notices)
    print("=" * 80)
    print("Test 1: Search with empty keyword (first 3 pages)")
    print("=" * 80)
    results = crawler.search(keyword="", max_pages=3)
    print(f"Total results: {len(results)}")
    print()
    for i, item in enumerate(results):
        print(
            f"  [{i+1:3d}] [{item['number']:>5s}] {item['date']}  "
            f"{item['organization']:>6s}  {item['title']}"
        )
    print()

    # Test 2: Keyword search
    print("=" * 80)
    print("Test 2: Search with keyword '공고' (first 3 pages)")
    print("=" * 80)
    results2 = crawler.search(keyword="공고", max_pages=3)
    print(f"Total results: {len(results2)}")
    print()
    for i, item in enumerate(results2):
        print(
            f"  [{i+1:3d}] [{item['number']:>5s}] {item['date']}  "
            f"{item['organization']:>6s}  {item['title']}"
        )
    print()

    # Show sample dict structure
    if results:
        print("=" * 80)
        print("Sample item dict structure:")
        print("=" * 80)
        import json

        print(json.dumps(results[0], ensure_ascii=False, indent=2))
