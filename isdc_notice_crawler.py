"""
성남도시개발공사 고시공고 크롤러

Target URL: https://www.isdc.co.kr/board/default/boardDefaultList.asp?HiddenBbsNo=82
POST 기반 게시판, 제목 검색, 페이지네이션 지원.
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


class ISDCNoticeCrawler:
    """성남도시개발공사 고시공고 크롤러"""

    BASE_URL = "https://www.isdc.co.kr"
    LIST_URL = f"{BASE_URL}/board/default/boardDefaultList.asp"
    DETAIL_URL = f"{BASE_URL}/board/default/boardDefaultview.asp"
    BBS_NO = "82"
    WORKERS = 5

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

    def _fetch_page(self, keyword: str, page: int) -> Optional[BeautifulSoup]:
        """게시판 페이지 조회"""
        data = {
            "HiddenBbsNo": self.BBS_NO,
            "HiddenPageNum": str(page),
        }
        if keyword:
            data["EditSearch"] = keyword
            data["ComboSearchKind"] = "Title"
        try:
            resp = self.session.post(self.LIST_URL, data=data, timeout=30)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException as e:
            print(f"[ERROR] Page {page}: {e}")
            return None

    def _get_total_pages(self, soup: BeautifulSoup) -> int:
        """페이지네이션에서 최대 페이지 수 추출"""
        page_wrap = soup.find("div", class_="pageWrap")
        if not page_wrap:
            return 1
        max_page = 1
        for a in page_wrap.find_all("a", onclick=True):
            m = re.search(r"ChagePageNum\((\d+)", a.get("onclick", ""))
            if m:
                max_page = max(max_page, int(m.group(1)))
        return max_page

    def _parse_page(self, soup: BeautifulSoup) -> list[dict]:
        """테이블에서 게시글 목록 파싱"""
        results = []
        tables = soup.find_all("table")
        if not tables:
            return results

        for row in tables[0].find_all("tr")[1:]:  # 헤더 제외
            cells = row.find_all("td")
            if len(cells) < 5:
                continue

            number = cells[0].get_text(strip=True)
            title_cell = cells[2]
            a = title_cell.find("a")
            if not a:
                continue

            title = a.get_text(strip=True)
            onclick = a.get("onclick", "")
            # TransPage('boardDefaultview.asp','VIEW','14')
            m = re.search(r"TransPage\([^,]+,\s*'VIEW',\s*'(\d+)'\)", onclick)
            code = m.group(1) if m else ""
            date = cells[3].get_text(strip=True)

            results.append({
                "number": number,
                "title": title,
                "date": date,
                "url": f"{self.DETAIL_URL}?HiddenBbsNo={self.BBS_NO}&HiddenCode={code}&HiddenState=VIEW" if code else "",
                "organization": "고시공고",
            })

        return results

    def search(self, keyword: str = "", max_pages: int = 1000) -> list[dict]:
        """고시공고 검색

        Args:
            keyword: 검색 키워드 (제목 검색)
            max_pages: 최대 페이지 수

        Returns:
            List of dicts with: number, title, date, url, organization
        """
        soup = self._fetch_page(keyword, 1)
        if soup is None:
            return []

        total_pages = min(self._get_total_pages(soup), max_pages)
        page_results = {1: self._parse_page(soup)}

        if total_pages > 1:
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {}
                for p in range(2, total_pages + 1):
                    futures[executor.submit(self._fetch_page, keyword, p)] = p
                for future in as_completed(futures):
                    p = futures[future]
                    try:
                        s = future.result()
                        if s:
                            rows = self._parse_page(s)
                            if rows:
                                page_results[p] = rows
                    except Exception:
                        pass

        all_rows = []
        for p in sorted(page_results.keys()):
            all_rows.extend(page_results[p])
        return all_rows


def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    import time

    crawler = ISDCNoticeCrawler()

    print("=" * 80)
    print("TEST: All posts (no keyword)")
    print("=" * 80)
    start = time.time()
    results = crawler.search()
    elapsed = time.time() - start
    print(f"Total: {len(results)}건, {elapsed:.1f}초")
    for i, item in enumerate(results[:5], 1):
        print(f"  [{i}] {item['number']} | {item['date']} | {item['title'][:60]}")

    print()
    print("=" * 80)
    print('TEST: Keyword "공고"')
    print("=" * 80)
    start = time.time()
    results2 = crawler.search(keyword="공고")
    elapsed = time.time() - start
    print(f"Total: {len(results2)}건, {elapsed:.1f}초")
    for i, item in enumerate(results2[:5], 1):
        print(f"  [{i}] {item['number']} | {item['date']} | {item['title'][:60]}")

    print()
    print("VALIDATION")
    assert isinstance(results, list)
    assert len(results) > 0
    required = {"number", "title", "date", "url", "organization"}
    assert required.issubset(results[0].keys())
    print(f"  Passed: {len(results)} items")


if __name__ == "__main__":
    main()
