# -*- coding: utf-8 -*-
"""
LH 기술혁신파트너몰 - 자재·공법 심의 크롤러
POST 요청 + HTML 파싱 방식
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup


class LHCrawler:
    """LH 파트너몰 자재·공법 심의 크롤러"""

    def __init__(self, concurrency: int = 10):
        self.base_url = "https://partner.lh.or.kr"
        self.search_url = f"{self.base_url}/deliberate/deliberate.asp"
        self.concurrency = concurrency

    async def _fetch_page(self, session, keyword: str, page_no: int, search_item: str = ""):
        """페이지 데이터 가져오기"""
        data = {
            "searchKeyword": keyword,
            "searchItem": search_item,  # '': 전체, 'title': 공사명, 'tech': 기술명
            "reType": "",  # 분류: 전체
            "coType": "",  # 공종: 전체
            "page": page_no
        }

        try:
            async with session.post(self.search_url, data=data, timeout=aiohttp.ClientTimeout(total=30)) as response:
                html = await response.text()
                return page_no, html
        except Exception as e:
            print(f"[오류] 페이지 {page_no}: {e}")
            return page_no, None

    def _parse_page(self, html: str):
        """HTML 파싱하여 데이터 추출"""
        results = []
        soup = BeautifulSoup(html, "html.parser")

        tables = soup.find_all("table")
        if len(tables) < 2:
            return results

        rows = tables[1].find_all("tr")

        for row in rows[1:]:  # 헤더 제외
            cells = row.find_all("td")
            if not cells:
                continue

            title = cells[0].get_text(strip=True)

            # "검색된 공고가 없습니다" 제외
            if not title or "검색된 공고가 없습니다" in title:
                continue

            # 데이터 추출
            category = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            period = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            selection_date = cells[3].get_text(strip=True) if len(cells) > 3 else ""
            review_date = cells[4].get_text(strip=True) if len(cells) > 4 else ""

            # 상세보기 링크에서 idx 추출 (openView(1694) 형식)
            idx = ""
            view_link = row.find("a", onclick=lambda x: x and "openView" in x)
            if view_link:
                import re
                match = re.search(r"openView\((\d+)\)", view_link.get("onclick", ""))
                if match:
                    idx = match.group(1)

            # 공모기간에서 시작/종료일 추출 (예: "26.01.28, 10시~26.02.03, 18시")
            date_start = ""
            date_end = ""
            if "~" in period:
                parts = period.split("~")
                date_start = parts[0].strip().split(",")[0].strip() if parts[0] else ""
                date_end = parts[1].strip().split(",")[0].strip() if len(parts) > 1 else ""

            # 상세 링크 (JavaScript에서 idx로 POST 폼 전송)
            detail_link = "https://partner.lh.or.kr/deliberate/deliberate.asp"

            results.append({
                "title": title,
                "organization": "LH 파트너몰",
                "category": category,  # 분류/공종
                "type": category.split("/")[0].strip() if "/" in category else category,
                "period": period,  # 공모기간
                "date": date_start,  # 게시일 (공모 시작일)
                "deadline": date_end,  # 마감일 (공모 종료일)
                "selection_date": selection_date,  # 심의대상 업체선정
                "review_date": review_date,  # 심의
                "url": detail_link,
                "idx": idx,  # 상세보기 ID
            })

        return results

    async def _search_async(self, keyword: str = "", search_item: str = "", max_pages: int = 100):
        """비동기 검색 - 빈 페이지 발견시 조기 종료"""
        all_results = []
        semaphore = asyncio.Semaphore(self.concurrency)

        async def fetch_with_semaphore(session, page_no):
            async with semaphore:
                return await self._fetch_page(session, keyword, page_no, search_item)

        print(f"[LH] 검색 중 (키워드: '{keyword or '전체'}')...")

        async with aiohttp.ClientSession() as session:
            # 첫 페이지로 전체 페이지 수 추정
            _, first_html = await self._fetch_page(session, keyword, 1, search_item)
            if not first_html:
                return all_results

            first_results = self._parse_page(first_html)
            all_results.extend(first_results)

            if len(first_results) == 0:
                print("[LH] 검색 결과 없음")
                return all_results

            # 배치 단위로 페이지 조회 (빈 페이지 발견시 중단)
            batch_size = 10  # 한 번에 10페이지씩 조회
            page_no = 2

            while page_no <= max_pages:
                # 다음 배치 생성
                batch_end = min(page_no + batch_size, max_pages + 1)
                tasks = [fetch_with_semaphore(session, p) for p in range(page_no, batch_end)]
                responses = await asyncio.gather(*tasks)

                # 결과 처리
                found_empty = False
                for _, html in sorted(responses, key=lambda x: x[0]):  # 페이지 순서대로 처리
                    if not html:
                        continue
                    page_results = self._parse_page(html)
                    if not page_results:
                        found_empty = True
                        break
                    all_results.extend(page_results)

                # 빈 페이지 발견시 중단
                if found_empty:
                    break

                page_no = batch_end

        print(f"[LH] 완료: 총 {len(all_results)}건")
        return all_results

    def search(self, keyword: str = "", search_item: str = "", max_pages: int = 100):
        """
        LH 자재·공법 심의 검색

        Args:
            keyword: 검색 키워드
            search_item: 검색 조건 ('': 전체, 'title': 공사명, 'tech': 기술명)
            max_pages: 최대 페이지 수

        Returns:
            검색 결과 리스트
        """
        return asyncio.run(self._search_async(keyword, search_item, max_pages))


def search_lh(keyword: str = "", max_pages: int = 100):
    """간단한 검색 함수"""
    crawler = LHCrawler()
    return crawler.search(keyword, max_pages=max_pages)


def main():
    """테스트 실행"""
    import sys

    keyword = sys.argv[1] if len(sys.argv) > 1 else ""

    print(f"\n{'='*60}")
    print(f" LH 기술혁신파트너몰 - 자재·공법 심의 검색")
    print(f" 키워드: {keyword or '전체'}")
    print(f"{'='*60}\n")

    results = search_lh(keyword, max_pages=20)

    print(f"\n{'='*60}")
    print(f" 검색 결과: {len(results)}건")
    print(f"{'='*60}\n")

    for i, r in enumerate(results[:15], 1):
        print(f"{i}. {r['title']}")
        print(f"   분류: {r['category']} | 공모기간: {r['period']}")
        print()

    if len(results) > 15:
        print(f"... 외 {len(results) - 15}건")


if __name__ == "__main__":
    main()
