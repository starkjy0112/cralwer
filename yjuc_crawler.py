# -*- coding: utf-8 -*-
"""
양주도시공사 통합검색 크롤러
https://www.yjuc.or.kr/contents/search_result.asp?tsearchOpt1=2&tsearchName=
GET 기반, 게시판 검색 (게시판별 페이지네이션 + URL 중복제거)
"""

import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.yjuc.or.kr"
SEARCH_URL = f"{BASE_URL}/contents/search_result.asp"


class YJUCCrawler:
    """양주도시공사 통합검색 크롤러"""

    WORKERS = 5

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            }
        )

    def _parse_items(self, soup):
        """검색 결과 페이지에서 게시글 항목 파싱"""
        items = []
        for a in soup.select("a[href*='content.asp']"):
            href = a.get("href", "")
            if "fboard" not in href or "num=" not in href:
                continue

            title = a.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            if href.startswith("../"):
                detail_url = f"{BASE_URL}/{href[3:]}"
            elif href.startswith("/"):
                detail_url = f"{BASE_URL}{href}"
            else:
                detail_url = href

            date = ""
            li = a.find_parent("li")
            if li:
                m = re.search(r"(\d{4}[-./]\d{1,2}[-./]\d{1,2})", li.get_text())
                if m:
                    date = m.group(1)

            items.append(
                {
                    "number": "",
                    "title": title,
                    "date": date,
                    "url": detail_url,
                    "organization": "양주도시공사",
                }
            )
        return items

    def _fetch_board_page(self, keyword, board, page):
        """특정 게시판의 특정 페이지 크롤링"""
        params = {
            "tsearchOpt1": "2",
            "tsearchName": keyword,
            "fboard": board,
            "fpage": page,
            "intPageSize": "10",
        }
        resp = self.session.get(SEARCH_URL, params=params, timeout=15)
        resp.encoding = "euc-kr"
        soup = BeautifulSoup(resp.text, "html.parser")
        return self._parse_items(soup)

    def _get_boards_and_max_pages(self, keyword):
        """첫 페이지에서 게시판 목록과 각 게시판의 최대 페이지 수 추출"""
        params = {
            "tsearchOpt1": "2",
            "tsearchName": keyword,
            "fpage": "1",
            "intPageSize": "10",
        }
        resp = self.session.get(SEARCH_URL, params=params, timeout=15)
        resp.encoding = "euc-kr"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 첫 페이지 결과
        first_items = self._parse_items(soup)

        # 게시판별 최대 페이지 추출
        board_pages = {}
        for a in soup.select("a[href*='fboard']"):
            href = a.get("href", "")
            board_m = re.search(r"fboard=(\w+)", href)
            page_m = re.search(r"fpage=(\d+)", href)
            if board_m and page_m:
                board = board_m.group(1)
                page = int(page_m.group(1))
                if board not in board_pages or page > board_pages[board]:
                    board_pages[board] = page

        return first_items, board_pages

    def search(self, keyword="", max_pages=100):
        if not keyword:
            print("[양주도시공사] 통합검색은 키워드가 필요합니다")
            return []

        first_items, board_pages = self._get_boards_and_max_pages(keyword)
        print(f"  [첫 페이지] {len(first_items)}건, 게시판 {len(board_pages)}개 발견")

        # URL 기반 중복제거 (첫 페이지 결과 등록)
        seen_urls = set()
        all_items = []
        for item in first_items:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                all_items.append(item)

        # 각 게시판별로 나머지 페이지 크롤링
        tasks = []
        for board, max_page in board_pages.items():
            actual_max = min(max_page, max_pages)
            for page in range(2, actual_max + 1):
                tasks.append((board, page))

        if tasks:
            print(f"  [크롤링] {len(tasks)}개 페이지 수집 중...")
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_board_page, keyword, board, page): (board, page)
                    for board, page in tasks
                }
                for future in as_completed(futures):
                    try:
                        items = future.result()
                        for item in items:
                            if item["url"] not in seen_urls:
                                seen_urls.add(item["url"])
                                all_items.append(item)
                    except Exception:
                        pass

        # 날짜 역순 정렬
        all_items.sort(key=lambda x: x["date"], reverse=True)

        print(f"[양주도시공사] 완료: 총 {len(all_items)}건")
        return all_items


if __name__ == "__main__":
    crawler = YJUCCrawler()
    print("=== '공고' 검색 ===")
    results = crawler.search("공고")
    print(f"\n전체 검색 결과: {len(results)}건")
    for r in results[:10]:
        print(f"  [{r['date']}] {r['title'][:50]}")
