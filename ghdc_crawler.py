# -*- coding: utf-8 -*-
"""
김해시도시개발공사 통합검색 크롤러

Target: https://ghdc.or.kr/sub.html?code=08_05&Radd=08_05
통합검색 > 게시글 검색결과, 키워드 필수, ~31건/페이지(페이지네이션 없음)
상세 페이지에서 날짜 병렬 조회
"""
import re
import requests
from bs4 import BeautifulSoup
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


class GhdcCrawler:
    """김해시도시개발공사 통합검색 크롤러"""

    BASE_URL = "https://ghdc.or.kr"
    SEARCH_URL = f"{BASE_URL}/sub.html"
    SEARCH_CODE = "08_05"
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
        self._init_cookies = False

    def _ensure_cookies(self):
        """PHPSESSID 쿠키 획득"""
        if not self._init_cookies:
            self.session.get(f"{self.BASE_URL}/", timeout=10)
            self._init_cookies = True

    def _fetch_search(self, keyword: str) -> Optional[BeautifulSoup]:
        """통합검색 페이지 조회"""
        params = {
            "code": self.SEARCH_CODE,
            "Radd": self.SEARCH_CODE,
            "keyword": keyword,
            "x": "0",
            "y": "0",
        }
        try:
            resp = self.session.get(self.SEARCH_URL, params=params, timeout=30)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException as e:
            print(f"[ERROR] Search failed: {e}")
            return None

    def _parse_search_results(self, soup: BeautifulSoup) -> list[dict]:
        """게시글 검색결과에서 dt/dd 파싱"""
        results = []

        h3_board = None
        for h3 in soup.select("h3"):
            if "게시글" in h3.get_text():
                h3_board = h3
                break

        if not h3_board:
            return results

        dl = h3_board.find_next_sibling("dl")
        if not dl:
            return results

        dts = dl.select("dt")

        for dt in dts:
            a = dt.select_one("a")
            if not a:
                continue

            raw_title = a.get_text(strip=True)
            href = a.get("href", "")
            url = f"{self.BASE_URL}{href}" if href else ""

            # 제목에서 게시판명 분리: "채용정보 | 김해시도시개발공사 > 실제제목"
            if " > " in raw_title:
                prefix, title = raw_title.split(" > ", 1)
                board = prefix.split(" | ")[0].strip() if " | " in prefix else prefix.strip()
            else:
                title = raw_title
                board = ""

            results.append({
                "number": "",
                "title": title,
                "date": "",
                "url": url,
                "organization": board or "김해시도시개발공사",
            })

        return results

    def _fetch_date(self, url: str) -> str:
        """상세 페이지에서 날짜 추출"""
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            for dl in soup.select("dl"):
                dts = dl.select("dt")
                dds = dl.select("dd")
                for dt, dd in zip(dts, dds):
                    dt_text = dt.get_text(strip=True)
                    dd_text = dd.get_text(strip=True)
                    if dt_text in ("등록일", "접수시작", "작성일", "게시일"):
                        # "26-01-15 17:16" -> "2026-01-15"
                        m = re.match(r"(\d{2})-(\d{2})-(\d{2})", dd_text)
                        if m:
                            return f"20{m.group(1)}-{m.group(2)}-{m.group(3)}"
                        # "2026-02-27" -> as-is
                        m2 = re.match(r"(\d{4}-\d{2}-\d{2})", dd_text)
                        if m2:
                            return m2.group(1)
                        return dd_text.split()[0]
        except Exception:
            pass
        return ""

    def _fetch_dates_parallel(self, results: list[dict]):
        """상세 페이지에서 날짜를 병렬로 가져오기"""
        urls = [(i, r["url"]) for i, r in enumerate(results) if r["url"]]
        if not urls:
            return

        with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
            futures = {
                executor.submit(self._fetch_date, url): idx
                for idx, url in urls
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    date = future.result()
                    if date:
                        results[idx]["date"] = date
                except Exception:
                    pass

    def search(self, keyword: str = "", max_pages: int = 10) -> list[dict]:
        """통합검색으로 게시글 검색

        Args:
            keyword: 검색 키워드 (필수, 빈 문자열이면 0건)
            max_pages: 미사용 (페이지네이션 없음)

        Returns:
            List of dicts with: number, title, date, url, organization
        """
        if not keyword:
            return []

        self._ensure_cookies()

        soup = self._fetch_search(keyword)
        if soup is None:
            return []

        results = self._parse_search_results(soup)
        if not results:
            return []

        # 상세 페이지에서 날짜를 병렬로 가져오기
        self._fetch_dates_parallel(results)

        return results


def main():
    import time

    crawler = GhdcCrawler()

    print("=" * 80)
    print('TEST: Keyword "공고"')
    print("=" * 80)
    start = time.time()
    results = crawler.search(keyword="공고")
    elapsed = time.time() - start
    print(f"Total results: {len(results)}건, {elapsed:.1f}초")
    if results:
        for i, item in enumerate(results[:5], 1):
            print(f"  [{i}] {item['date']} | {item['organization']} | {item['title'][:50]}")
        print(f"  ...")
        print(f"  Last: {results[-1]['date']} | {results[-1]['title'][:50]}")

    assert isinstance(results, list)
    if results:
        required = {"number", "title", "date", "url", "organization"}
        assert required.issubset(results[0].keys())
    print("Validation passed.")


if __name__ == "__main__":
    main()
