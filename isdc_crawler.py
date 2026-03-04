"""
성남도시개발공사 통합검색 크롤러

Target URL: https://www.isdc.co.kr/guidance/search.asp
1단계: 통합검색에서 게시판별 건수/BbsNo 파악 + 소규모 게시판 직접 파싱
2단계: 대규모 게시판은 searchBbsList.asp로 전체 페이지 조회 (제목+본문 검색)
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


class ISDCCrawler:
    """성남도시개발공사 통합검색 크롤러"""

    BASE_URL = "https://www.isdc.co.kr"
    SEARCH_URL = f"{BASE_URL}/guidance/search.asp"
    SEARCH_BBS_URL = f"{BASE_URL}/guidance/searchBbsList.asp"
    WORKERS = 10

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

    def _fetch_search_page(self, keyword: str) -> Optional[BeautifulSoup]:
        """통합검색 페이지 조회"""
        try:
            if keyword:
                resp = self.session.post(
                    self.SEARCH_URL, data={"searchTxt": keyword}, timeout=30
                )
            else:
                resp = self.session.get(self.SEARCH_URL, timeout=30)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException as e:
            print(f"[ERROR] Search failed: {e}")
            return None

    def _parse_search_page(self, soup: BeautifulSoup) -> tuple[list[dict], list[tuple[str, str]]]:
        """통합검색 페이지에서:
        1) 소규모 게시판(더보기 없음) 결과를 직접 파싱
        2) 대규모 게시판(더보기 있음)의 (BbsNo, board_name) 목록 반환
        """
        small_results = []
        big_boards = []

        for section in soup.find_all("div", class_="totalSearch"):
            tit_div = section.find("div", class_="totalSchTit")
            if not tit_div:
                continue
            tit_text = tit_div.get_text(strip=True)
            m = re.match(r"(.+?)\(총\s*(\d+)건\)", tit_text)
            if not m:
                continue
            board_name = m.group(1)
            count = int(m.group(2))

            if count == 0:
                continue

            # 더보기 링크에서 BbsNo 추출
            bbs_no = ""
            for a in section.find_all("a"):
                onclick = a.get("onclick", "")
                bm = re.search(r"HiddenBbsNo=(\d+)", onclick)
                if bm:
                    bbs_no = bm.group(1)
                    break

            if bbs_no and count > 5:
                # 대규모 게시판 → searchBbsList.asp로 전체 조회
                big_boards.append((bbs_no, board_name))
            else:
                # 소규모 게시판 → 통합검색 페이지에서 직접 파싱
                ul = section.find("ul", class_="totalSchList")
                if not ul:
                    continue
                for dl in ul.find_all("dl"):
                    dt = dl.find("dt")
                    if not dt:
                        continue
                    a = dt.find("a")
                    if not a:
                        continue
                    title = a.get_text(strip=True)
                    href = a.get("href", "")
                    url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
                    span = dt.find("span")
                    date = span.get_text(strip=True) if span else ""
                    small_results.append({
                        "number": "",
                        "title": title,
                        "date": date,
                        "url": url,
                        "organization": board_name,
                    })

        return small_results, big_boards

    def _fetch_bbs_page(self, bbs_no: str, keyword: str, page: int) -> Optional[BeautifulSoup]:
        """searchBbsList.asp 단일 페이지 조회"""
        data = {
            "HiddenBbsNo": bbs_no,
            "searchTxt": keyword,
            "HiddenPageNum": str(page),
        }
        try:
            resp = self.session.post(self.SEARCH_BBS_URL, data=data, timeout=30)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException as e:
            print(f"[ERROR] BbsNo={bbs_no} Page {page}: {e}")
            return None

    def _get_total_pages(self, soup: BeautifulSoup) -> int:
        """페이지네이션에서 최대 페이지 수 추출"""
        page_wrap = soup.find("div", class_="pageWrap")
        if not page_wrap:
            return 1
        max_page = 1
        for link in page_wrap.find_all("a", onclick=True):
            m = re.search(r"ChagePageNum\((\d+)", link.get("onclick", ""))
            if m:
                max_page = max(max_page, int(m.group(1)))
        return max_page

    def _parse_bbs_page(self, soup: BeautifulSoup, board_name: str) -> list[dict]:
        """searchBbsList.asp 결과 파싱 (dl/dt/dd 구조)"""
        results = []
        for dl in soup.find_all("dl"):
            dt = dl.find("dt")
            if not dt:
                continue
            a = dt.find("a")
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get("href", "")
            url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
            span = dt.find("span")
            date = span.get_text(strip=True) if span else ""
            results.append({
                "number": "",
                "title": title,
                "date": date,
                "url": url,
                "organization": board_name,
            })
        return results

    def _fetch_board_all(self, bbs_no: str, board_name: str, keyword: str) -> list[dict]:
        """한 게시판의 전체 페이지를 조회"""
        soup = self._fetch_bbs_page(bbs_no, keyword, 1)
        if soup is None:
            return []

        total_pages = self._get_total_pages(soup)
        page_results = {1: self._parse_bbs_page(soup, board_name)}

        if total_pages > 1:
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {}
                for p in range(2, total_pages + 1):
                    futures[executor.submit(self._fetch_bbs_page, bbs_no, keyword, p)] = p
                for future in as_completed(futures):
                    p = futures[future]
                    try:
                        s = future.result()
                        if s:
                            rows = self._parse_bbs_page(s, board_name)
                            if rows:
                                page_results[p] = rows
                    except Exception:
                        pass

        all_rows = []
        for p in sorted(page_results.keys()):
            all_rows.extend(page_results[p])
        return all_rows

    def search(self, keyword: str = "", max_pages: int = 1000) -> list[dict]:
        """통합검색 전체 게시판 조회

        Args:
            keyword: 검색 키워드 (제목+본문 검색)
            max_pages: 미사용

        Returns:
            List of dicts with: number, title, date, url, organization
        """
        # 1단계: 통합검색 페이지 조회
        soup = self._fetch_search_page(keyword)
        if soup is None:
            return []

        # 2단계: 소규모 게시판 직접 파싱 + 대규모 게시판 목록 추출
        small_results, big_boards = self._parse_search_page(soup)

        # 3단계: 대규모 게시판 병렬 전체 조회
        big_results = []
        if big_boards:
            with ThreadPoolExecutor(max_workers=len(big_boards)) as executor:
                futures = {
                    executor.submit(self._fetch_board_all, bbs_no, name, keyword): name
                    for bbs_no, name in big_boards
                }
                for future in as_completed(futures):
                    try:
                        rows = future.result()
                        if rows:
                            big_results.extend(rows)
                    except Exception:
                        pass

        return small_results + big_results


def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    import time

    crawler = ISDCCrawler()

    print("=" * 80)
    print('TEST: Keyword "공고"')
    print("=" * 80)
    start = time.time()
    results = crawler.search(keyword="공고")
    elapsed = time.time() - start
    print(f"Total results: {len(results)}건, {elapsed:.1f}초")

    # 게시판별 건수
    from collections import Counter
    board_counts = Counter(r["organization"] for r in results)
    for board, cnt in board_counts.most_common():
        print(f"  {board}: {cnt}건")

    print()
    if results:
        for i, item in enumerate(results[:5], 1):
            print(f"  [{i}] {item['date']} | {item['organization']} | {item['title'][:50]}")

    print()
    print("VALIDATION")
    assert isinstance(results, list)
    assert len(results) > 0
    required = {"number", "title", "date", "url", "organization"}
    assert required.issubset(results[0].keys())
    print(f"  Passed: {len(results)} items")


if __name__ == "__main__":
    main()
