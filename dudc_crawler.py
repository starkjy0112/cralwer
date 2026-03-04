# -*- coding: utf-8 -*-
"""
대구도시개발공사 공지사항 크롤러
GET 요청 + HTML 파싱 방식 (서버사이드 렌더링)
"""
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


class DUDCCrawler:
    """대구도시개발공사 공지사항 크롤러"""

    ORGANIZATION = "대구도시개발공사"

    def __init__(self):
        self.base_url = "https://www.dudc.or.kr"
        self.list_url = f"{self.base_url}/ko/page.do"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        }

    def _fetch_page(self, keyword: str, page: int):
        """단일 페이지 HTML 조회"""
        params = {
            "mnu_uid": 100,
            "appId": "notice",
            "srchColumn": "board_title",
            "srchKwd": keyword,
            "pageNo": page,
        }

        try:
            response = requests.get(
                self.list_url, params=params,
                headers=self.headers, timeout=15,
            )
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"[오류] 페이지 {page} 조회 실패: {e}")
            return None

    def _parse_total_info(self, soup: BeautifulSoup):
        """전체 게시물 수 및 페이지 수 파싱"""
        total_count = 0
        total_pages = 1

        page_info = soup.find("div", class_="pageInfo")
        if page_info:
            strongs = page_info.find_all("strong")
            if len(strongs) >= 2:
                try:
                    total_count = int(strongs[0].get_text(strip=True))
                    total_pages = int(strongs[1].get_text(strip=True))
                except ValueError:
                    pass

        return total_count, total_pages

    def _parse_page(self, html: str):
        """HTML에서 게시물 목록 파싱"""
        results = []
        soup = BeautifulSoup(html, "html.parser")

        table = soup.find("table", class_="tbl_board")
        if not table:
            return results, 0, 1

        total_count, total_pages = self._parse_total_info(soup)

        tbody = table.find("tbody")
        if not tbody:
            return results, total_count, total_pages

        rows = tbody.find_all("tr")

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue

            num_text = cells[0].get_text(strip=True)
            is_notice = not num_text.isdigit()

            # 제목 및 링크
            title_cell = cells[1]
            link_tag = title_cell.find("a")
            title = link_tag.get_text(strip=True) if link_tag else title_cell.get_text(strip=True)

            link = ""
            if link_tag and link_tag.get("href"):
                href = link_tag["href"]
                if href.startswith("?"):
                    link = f"{self.list_url}{href}"
                elif href.startswith("/"):
                    link = f"{self.base_url}{href}"
                elif not href.startswith("http"):
                    link = f"{self.base_url}/{href}"
                else:
                    link = href

            writer = cells[2].get_text(strip=True)
            date = cells[3].get_text(strip=True)
            views = cells[4].get_text(strip=True)

            results.append({
                "organization": self.ORGANIZATION,
                "number": num_text,
                "title": title,
                "date": date,
                "views": views,
                "url": link,
                "is_notice": is_notice,
            })

        return results, total_count, total_pages

    WORKERS = 5

    def _fetch_and_parse(self, keyword: str, page: int):
        """페이지 조회 + 파싱"""
        html = self._fetch_page(keyword, page)
        if not html:
            return []
        results, _, _ = self._parse_page(html)
        return results

    def search(self, keyword: str = "", max_pages: int = 50):
        """
        공지사항 검색 (제목 기준, 페이지네이션 지원)

        Args:
            keyword: 검색 키워드 (빈 문자열이면 전체 조회)
            max_pages: 최대 조회 페이지 수

        Returns:
            검색 결과 리스트 (날짜 내림차순 정렬)
        """
        print(f"[{self.ORGANIZATION}] 검색 시작 (키워드: '{keyword or '전체'}')")

        # 첫 페이지 조회로 전체 건수/페이지 파악
        first_html = self._fetch_page(keyword, 1)
        if not first_html:
            return []

        first_results, total_count, total_pages = self._parse_page(first_html)
        actual_pages = min(total_pages, max_pages)

        print(f"[{self.ORGANIZATION}] 전체 {total_count}건, {total_pages}페이지 (최대 {actual_pages}페이지 조회)")

        if actual_pages <= 1:
            all_results = first_results
        else:
            # 나머지 페이지 병렬 조회
            page_results = {1: first_results}
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_and_parse, keyword, p): p
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

        # 날짜 내림차순 정렬
        all_results.sort(key=lambda x: x.get("date", ""), reverse=True)

        notice_count = len([r for r in all_results if r["is_notice"]])
        print(f"[{self.ORGANIZATION}] 완료: 총 {len(all_results)}건 (공지: {notice_count}건)")

        return all_results


def search_dudc(keyword: str = "", max_pages: int = 50):
    """간단한 검색 함수"""
    crawler = DUDCCrawler()
    return crawler.search(keyword, max_pages)


def main():
    """테스트 실행"""
    import sys

    keyword = sys.argv[1] if len(sys.argv) > 1 else ""

    print(f"\n{'='*60}")
    print(f" 대구도시개발공사 공지사항 검색")
    print(f" 키워드: {keyword or '전체'}")
    print(f"{'='*60}\n")

    results = search_dudc(keyword, max_pages=3)

    print(f"\n{'='*60}")
    print(f" 검색 결과: {len(results)}건")
    print(f"{'='*60}\n")

    for i, r in enumerate(results[:10], 1):
        notice_tag = "[공지] " if r["is_notice"] else ""
        print(f"{i}. {notice_tag}{r['title'][:60]}")
        print(f"   번호: {r['num']} | 작성자: {r['writer']} | 날짜: {r['date']} | 조회: {r['views']}")
        print(f"   기관: {r['organization']}")
        print(f"   링크: {r['link']}")
        print()


if __name__ == "__main__":
    main()
