# -*- coding: utf-8 -*-
"""
거제해양관광개발공사 입찰공고 크롤러
GET 요청 + HTML 파싱 방식
"""
import requests
from bs4 import BeautifulSoup


class GMDCCrawler:
    """거제해양관광개발공사 입찰공고 크롤러"""

    def __init__(self):
        self.base_url = "https://www.gmdc.co.kr"
        self.search_url = f"{self.base_url}/bbs/board.php"

    def _fetch_page(self, keyword: str, search_field: str, page: int):
        """단일 페이지 조회"""
        params = {
            "bo_table": "sub04_02",
            "page": page,
        }
        if keyword:
            params["sfl"] = search_field
            params["stx"] = keyword

        try:
            response = requests.get(self.search_url, params=params, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"[오류] 페이지 {page}: {e}")
            return None

    def _parse_page(self, html: str):
        """HTML 파싱"""
        results = []
        soup = BeautifulSoup(html, "html.parser")

        table = soup.find("table")
        if not table:
            return results

        rows = table.find_all("tr")[1:]  # 헤더 제외

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue

            num = cells[0].get_text(strip=True)
            title_cell = cells[1]
            title = title_cell.get_text(strip=True)
            writer = cells[2].get_text(strip=True)
            views = cells[3].get_text(strip=True)
            date = cells[4].get_text(strip=True)

            # 링크 추출
            link_tag = title_cell.find("a")
            link = ""
            if link_tag and link_tag.get("href"):
                href = link_tag.get("href")
                if href.startswith("/"):
                    link = self.base_url + href
                elif not href.startswith("http"):
                    link = self.base_url + "/" + href
                else:
                    link = href

            results.append({
                "number": num,
                "title": title,
                "date": date,
                "url": link,
                "organization": writer,
            })

        return results

    def search(self, keyword: str = "", search_field: str = "wr_subject", max_pages: int = 100):
        """
        입찰공고 검색 (페이지네이션 지원)

        Args:
            keyword: 검색 키워드
            search_field: 검색 필드 ('wr_subject': 제목, 'wr_content': 내용, 'wr_subject||wr_content': 제목+내용)
            max_pages: 최대 페이지 수

        Returns:
            검색 결과 리스트
        """
        print(f"[검색] 키워드: '{keyword or '전체'}'")

        all_results = []

        for page in range(1, max_pages + 1):
            html = self._fetch_page(keyword, search_field, page)
            if not html:
                break

            page_results = self._parse_page(html)
            if not page_results:
                break

            all_results.extend(page_results)

            # 페이지당 15건 미만이면 마지막 페이지
            if len(page_results) < 15:
                break

        print(f"[완료] 총 {len(all_results)}건")
        return all_results


def search_gmdc(keyword: str = ""):
    """간단한 검색 함수"""
    crawler = GMDCCrawler()
    return crawler.search(keyword)


def main():
    """테스트 실행"""
    import sys

    keyword = sys.argv[1] if len(sys.argv) > 1 else ""

    print(f"\n{'='*60}")
    print(f" 거제해양관광개발공사 입찰공고 검색")
    print(f" 키워드: {keyword or '전체'}")
    print(f"{'='*60}\n")

    results = search_gmdc(keyword)

    print(f"\n{'='*60}")
    print(f" 검색 결과: {len(results)}건")
    print(f"{'='*60}\n")

    for i, r in enumerate(results[:10], 1):
        print(f"{i}. [{r['number']}] {r['title'][:50]}")
        print(f"   날짜: {r['date']} | 글쓴이: {r['writer']}")
        print()


if __name__ == "__main__":
    main()
