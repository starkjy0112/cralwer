"""
SH 서울주택도시공사 입찰공고 Crawler

Crawls bid announcements from:
https://www.i-sh.co.kr/main/lay2/program/S1T316C7212/www/m_2428/BidblancList.do

POST-based, 2 categories (용역/공사).
Site only supports monthly queries, so iterates through months.
Detail links redirect to g2b.go.kr.
"""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


class SHBidCrawler:
    """Crawler for SH서울주택도시공사 입찰공고."""

    LIST_URL = "https://www.i-sh.co.kr/main/lay2/program/S1T316C7212/www/m_2428/BidblancList.do"
    DETAIL_TEMPLATE = "https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo={bid_no}&bidPbancOrd={bid_ord}&pbancType=pbanc"

    CATEGORIES = {"2": "용역", "3": "공사"}
    MONTHS_BACK = 72  # 6년 (2021~2026 데이터 커버)

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

    def _build_date_range(self, year: int, month: int) -> tuple[str, str]:
        """Build srchFr/srchTo for a given year/month."""
        srch_fr = f"{year:04d}{month:02d}010000"
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year += 1
        srch_to = f"{next_year:04d}{next_month:02d}012359"
        return srch_fr, srch_to

    def _generate_months(self, months_back: int, start_date: str = "", end_date: str = "") -> list[tuple[int, int]]:
        """Generate (year, month) tuples.

        If start_date/end_date provided (YYYY-MM-DD), only generates months in that range.
        Otherwise goes back months_back months from current month.
        """
        if start_date and end_date:
            sy, sm = int(start_date[:4]), int(start_date[5:7])
            ey, em = int(end_date[:4]), int(end_date[5:7])
            months = []
            y, m = sy, sm
            while (y, m) <= (ey, em):
                months.append((y, m))
                m += 1
                if m > 12:
                    m = 1
                    y += 1
            return months

        now = datetime.now()
        months = []
        y, m = now.year, now.month
        for _ in range(months_back):
            months.append((y, m))
            m -= 1
            if m < 1:
                m = 12
                y -= 1
        return months

    def _fetch_page(self, category: str, keyword: str, srch_fr: str, srch_to: str, page: int):
        """Fetch a single page via POST."""
        data = {
            "bsnsDivNm": category,
            "inqryDiv": "1",
            "srchFr": srch_fr,
            "srchTo": srch_to,
            "bidNtceNm": keyword,
            "pitem": "10",
            "reqPage": str(page) if page > 1 else "",
        }
        try:
            resp = self.session.post(self.LIST_URL, data=data, timeout=30)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as e:
            print(f"[ERROR] cat={category} page={page}: {e}")
            return None

    def _get_total_pages(self, soup: BeautifulSoup) -> int:
        """Extract total pages from '총N건 [page/total페이지]'."""
        mentcount = soup.select_one("div.mentcount")
        if mentcount:
            m = re.search(r'\[(\d+)/(\d+)페이지\]', mentcount.get_text(strip=True))
            if m:
                return int(m.group(2))
        return 1

    def _parse_rows(self, soup: BeautifulSoup, category: str) -> list[dict]:
        """Parse bid announcement rows from table."""
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
                link_match = re.search(r"openBidblancDetail\('([^']+)',\s*'([^']+)'\)", onclick)
                if link_match:
                    url = self.DETAIL_TEMPLATE.format(
                        bid_no=link_match.group(1),
                        bid_ord=link_match.group(2),
                    )
                else:
                    url = ""
            else:
                title = tds[1].get_text(strip=True)
                url = ""

            date = tds[2].get_text(strip=True)
            cat_name = self.CATEGORIES.get(category, category)

            results.append({
                "number": number,
                "title": title,
                "date": date,
                "url": url,
                "organization": cat_name,
            })

        return results

    WORKERS = 20

    def _fetch_month_category(self, year: int, month: int, cat: str, keyword: str, max_pages: int) -> list[dict]:
        """Fetch all pages for one (year, month, category) combination."""
        srch_fr, srch_to = self._build_date_range(year, month)
        results = []

        soup = self._fetch_page(cat, keyword, srch_fr, srch_to, 1)
        if soup is None:
            return results

        total_pages = self._get_total_pages(soup)
        results.extend(self._parse_rows(soup, cat))

        for page in range(2, min(total_pages, max_pages) + 1):
            soup = self._fetch_page(cat, keyword, srch_fr, srch_to, page)
            if soup is None:
                break
            rows = self._parse_rows(soup, cat)
            if not rows:
                break
            results.extend(rows)

        return results

    def search(self, keyword: str = "", max_pages: int = 10, start_date: str = "", end_date: str = "") -> list[dict]:
        """Search bid announcements across all categories and months.

        Args:
            keyword: Search keyword for title. Empty returns all.
            max_pages: Max pages per category/month combination.
            start_date: Start date (YYYY-MM-DD). Empty = use MONTHS_BACK.
            end_date: End date (YYYY-MM-DD). Empty = use MONTHS_BACK.

        Returns:
            List of dicts with: number, title, date, url, organization.
        """
        months = self._generate_months(self.MONTHS_BACK, start_date, end_date)

        # Build all (year, month, category) tasks
        tasks = [
            (year, month, cat)
            for year, month in months
            for cat in self.CATEGORIES
        ]

        # Parallel fetch all month × category combinations
        all_raw: list[list[dict]] = []
        with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
            futures = {
                executor.submit(self._fetch_month_category, y, m, c, keyword, max_pages): (y, m, c)
                for y, m, c in tasks
            }
            for future in as_completed(futures):
                try:
                    items = future.result()
                    if items:
                        all_raw.append(items)
                except Exception:
                    pass

        # Dedup
        all_results: list[dict] = []
        seen: set[str] = set()
        for items in all_raw:
            for item in items:
                key = item["url"] or f"{item['title']}_{item['date']}"
                if key not in seen:
                    seen.add(key)
                    all_results.append(item)

        return all_results


def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    import time

    crawler = SHBidCrawler()

    print("=" * 80)
    print("TEST: Empty keyword (all categories, 5 years)")
    print("=" * 80)
    start = time.time()
    results = crawler.search(keyword="", max_pages=10)
    elapsed = time.time() - start
    print(f"Total results: {len(results)}건, 소요시간: {elapsed:.1f}초")
    for i, item in enumerate(results[:5], 1):
        print(f"  [{i}] {item['number']} | {item['date']} | {item['organization']} | {item['title'][:50]}")

    print()
    print("VALIDATION")
    assert isinstance(results, list)
    assert len(results) > 0
    assert isinstance(results[0], dict)
    required = {"number", "title", "date", "url", "organization"}
    assert required.issubset(results[0].keys())
    print(f"  All passed: {len(results)} items")


if __name__ == "__main__":
    main()
