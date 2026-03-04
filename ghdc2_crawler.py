# -*- coding: utf-8 -*-
"""
김해시도시개발공사 입찰공고(온비드) 크롤러
POST 검색 + HTML 테이블 파싱 방식
"""
import re
import requests
from bs4 import BeautifulSoup


class GHDCOnbidBidCrawler:
    """김해시도시개발공사 입찰공고(온비드) 크롤러"""

    BASE_URL = "https://ghdc.or.kr"
    BOARD_CODE = "03_04_06"
    ITEMS_PER_PAGE = 15
    ORGANIZATION = "김해시도시개발공사"
    BOARD_NAME = "입찰공고(온비드)"

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
            "Referer": f"{self.BASE_URL}/sub.html?code={self.BOARD_CODE}&Radd={self.BOARD_CODE}",
        })

    def _build_list_url(self, page: int = 1, keyword: str = "", search_type: str = "B"):
        """게시판 목록 URL 생성"""
        url = (
            f"{self.BASE_URL}/sub.html"
            f"?code={self.BOARD_CODE}&Radd={self.BOARD_CODE}"
            f"&mode=list&cate1="
        )
        if keyword:
            url += f"&search={search_type}&keyword={keyword}"
        url += f"&page={page}"
        return url

    def _fetch_page(self, keyword: str, page: int):
        """
        단일 페이지 조회

        첫 페이지는 POST 방식, 이후 페이지는 GET 방식으로 조회합니다.
        """
        if page == 1 and keyword:
            # 첫 검색은 POST 방식
            url = (
                f"{self.BASE_URL}/sub.html"
                f"?code={self.BOARD_CODE}&Radd={self.BOARD_CODE}"
                f"&mode=list&cate1="
            )
            data = {
                "search": "B",  # B = 제목 검색
                "keyword": keyword,
                "search_old": "",
                "keyword_old": "",
                "path": f"/sub.html?code={self.BOARD_CODE}&Radd={self.BOARD_CODE}",
            }
            try:
                response = self.session.post(url, data=data, timeout=30)
                response.raise_for_status()
                response.encoding = "utf-8"
                return response.text
            except Exception as e:
                print(f"[오류] 페이지 {page} POST 요청 실패: {e}")
                return None
        else:
            # 페이지네이션 또는 키워드 없는 조회는 GET 방식
            url = self._build_list_url(page=page, keyword=keyword)
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                response.encoding = "utf-8"
                return response.text
            except Exception as e:
                print(f"[오류] 페이지 {page} GET 요청 실패: {e}")
                return None

    def _parse_total_count(self, html: str):
        """총 게시물 수 파싱"""
        match = re.search(r"총\s*(?:&nbsp;)?\s*<strong>(\d+)</strong>\s*건", html)
        if match:
            return int(match.group(1))
        return 0

    def _parse_page(self, html: str):
        """HTML 테이블 파싱하여 결과 리스트 반환"""
        results = []
        soup = BeautifulSoup(html, "html.parser")

        bbs_div = soup.find("div", class_="bbsTable")
        if not bbs_div:
            return results

        table = bbs_div.find("table")
        if not table:
            return results

        tbody = table.find("tbody")
        if not tbody:
            return results

        rows = tbody.find_all("tr")

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue

            num_text = cells[0].get_text(strip=True)
            is_notice = not num_text.isdigit()

            # 제목과 링크
            title_cell = cells[1]
            link_tag = title_cell.find("a")
            title = ""
            link = ""
            if link_tag:
                # 검색 결과에서는 <span class="searchon"> 태그가 포함됨
                title = link_tag.get_text(strip=True)
                href = link_tag.get("href", "")
                if href:
                    # &amp; -> & 변환은 BeautifulSoup이 처리함
                    if href.startswith("http"):
                        link = href
                    elif href.startswith("/"):
                        link = f"{self.BASE_URL}{href}"
                    else:
                        link = f"{self.BASE_URL}/{href}"

            writer = cells[2].get_text(strip=True)
            date = cells[3].get_text(strip=True)
            views = cells[4].get_text(strip=True)

            results.append({
                "num": num_text,
                "title": title,
                "writer": writer,
                "date": date,
                "views": views,
                "link": link,
                "is_notice": is_notice,
                "organization": self.ORGANIZATION,
            })

        return results

    def search(self, keyword: str = "", max_pages: int = 5):
        """
        입찰공고(온비드) 검색

        Args:
            keyword: 검색 키워드 (제목 기준 검색, 빈 문자열이면 전체 조회)
            max_pages: 최대 크롤링 페이지 수 (기본 5)

        Returns:
            검색 결과 리스트 (날짜 내림차순 정렬)
        """
        print(f"[{self.ORGANIZATION} {self.BOARD_NAME}] 검색 시작 (키워드: '{keyword or '전체'}')")

        # 첫 페이지 조회
        first_html = self._fetch_page(keyword, page=1)
        if not first_html:
            print("[오류] 첫 페이지 조회 실패")
            return []

        total_count = self._parse_total_count(first_html)
        total_pages = (total_count + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE if total_count > 0 else 1
        pages_to_crawl = min(total_pages, max_pages)

        print(f"[{self.ORGANIZATION} {self.BOARD_NAME}] 총 {total_count}건, {total_pages}페이지 (최대 {pages_to_crawl}페이지 크롤링)")

        all_results = []

        # 첫 페이지 파싱
        page_results = self._parse_page(first_html)
        all_results.extend(page_results)

        # 나머지 페이지 크롤링
        for page in range(2, pages_to_crawl + 1):
            html = self._fetch_page(keyword, page)
            if not html:
                break

            page_results = self._parse_page(html)
            if not page_results:
                break

            all_results.extend(page_results)

        # 날짜 내림차순 정렬
        all_results.sort(key=lambda x: x.get("date", ""), reverse=True)

        notice_count = len([r for r in all_results if r["is_notice"]])
        data_count = len(all_results) - notice_count
        print(
            f"[{self.ORGANIZATION} {self.BOARD_NAME}] 완료: "
            f"총 {len(all_results)}건 (일반: {data_count}건, 공지: {notice_count}건)"
        )
        return all_results


def search_ghdc_onbid_bid(keyword: str = "", max_pages: int = 5):
    """간단한 검색 함수"""
    crawler = GHDCOnbidBidCrawler()
    return crawler.search(keyword=keyword, max_pages=max_pages)


def main():
    """테스트 실행"""
    import sys

    keyword = sys.argv[1] if len(sys.argv) > 1 else ""

    print(f"\n{'='*60}")
    print(f" {GHDCOnbidBidCrawler.ORGANIZATION} {GHDCOnbidBidCrawler.BOARD_NAME} 검색")
    print(f" 키워드: {keyword or '전체'}")
    print(f"{'='*60}\n")

    results = search_ghdc_onbid_bid(keyword, max_pages=3)

    print(f"\n{'='*60}")
    print(f" 검색 결과: {len(results)}건")
    print(f"{'='*60}\n")

    for i, r in enumerate(results[:10], 1):
        notice = "[공지] " if r["is_notice"] else ""
        print(f"{i}. {notice}[{r['num']}] {r['title'][:60]}")
        print(f"   날짜: {r['date']} | 작성자: {r['writer']} | 조회: {r['views']}")
        print(f"   링크: {r['link']}")
        print()


if __name__ == "__main__":
    main()
