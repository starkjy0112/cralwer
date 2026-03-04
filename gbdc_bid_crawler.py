# -*- coding: utf-8 -*-
"""
경상북도개발공사 입찰공고 게시판 크롤러
Target: https://www.gbdc.co.kr/boardlist.do?seqId=0000003730
Board: 입찰공고 (Bid Announcements)
API: /getBbsArticleList.do (GET)
"""

import requests


class GBDCBidCrawler:
    """경상북도개발공사 입찰공고 크롤러"""

    def __init__(self):
        self.base_url = "https://www.gbdc.co.kr"
        self.api_url = f"{self.base_url}/getBbsArticleList.do"
        self.bbs_id = "8e8a7886-32ae-4235-a7d2-1ffccfef6062"
        self.seq_id = "0000003730"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            "X-Requested-With": "XMLHttpRequest",
        }

    def _fetch_page(self, keyword, page):
        """API에서 게시글 목록 한 페이지를 가져옵니다."""
        params = {
            "BBS_ID": self.bbs_id,
            "BBS_TYPE": "L",
            "CURRENT_PAGE": page,
            "SEARCH_CONTITION": "CPDS_SUBJECT",
            "SEARCH_KEYWORD": keyword,
        }
        response = requests.get(
            self.api_url, params=params, headers=self.headers, timeout=10
        )
        response.raise_for_status()
        return response.json()

    def _parse_response(self, data):
        """API 응답 데이터를 파싱하여 결과 리스트를 반환합니다."""
        results = []
        for item in data.get("resultList", []):
            idx = item.get("IPDS_IDX", "")
            is_notice = item.get("MUST_LVL", 0) > 0
            date_str = item.get("CPDS_WDATE", "")
            date = date_str[:10] if date_str else ""

            results.append(
                {
                    "num": "공지" if is_notice else str(item.get("BNUM", "")),
                    "title": item.get("CPDS_SUBJECT", ""),
                    "writer": item.get("CPDS_NAME", ""),
                    "organization": item.get("DEPT_NAME", ""),
                    "date": date,
                    "views": str(item.get("IPDS_COUNTS", "")),
                    "link": (
                        f"{self.base_url}/boardview/boardview.do"
                        f"?seqId={self.seq_id}"
                        f"&BBS_ID={self.bbs_id}"
                        f"&IPDS_IDX={idx}"
                    )
                    if idx
                    else "",
                    "is_notice": is_notice,
                }
            )
        return results

    def search(self, keyword="", max_pages=1):
        """
        입찰공고 게시판을 검색합니다.

        Args:
            keyword: 검색어 (제목 검색, 빈 문자열이면 전체 조회)
            max_pages: 최대 페이지 수

        Returns:
            dict: {
                "total_count": int,
                "page_info": dict,
                "results": list[dict]
            }
        """
        all_results = []
        total_count = 0
        page_info = {}

        for page in range(1, max_pages + 1):
            try:
                data = self._fetch_page(keyword, page)
            except requests.RequestException as e:
                print(f"[오류] 페이지 {page} 요청 실패: {e}")
                break

            page_info = data.get("pageInfo", {})
            total_count = page_info.get("totalRecordCount", 0)

            items = self._parse_response(data)
            if not items:
                break

            all_results.extend(items)

            # 마지막 페이지에 도달하면 중단
            total_pages = page_info.get("totalPageCount", 1)
            if page >= total_pages:
                break

        # 날짜 내림차순 정렬 (공지사항 우선)
        all_results.sort(
            key=lambda x: (not x["is_notice"], x["date"]),
            reverse=False,
        )
        # 공지사항이 상단, 그 다음 날짜 내림차순
        notices = [r for r in all_results if r["is_notice"]]
        non_notices = [r for r in all_results if not r["is_notice"]]
        non_notices.sort(key=lambda x: x["date"], reverse=True)
        sorted_results = notices + non_notices

        print(f"[경북개발공사 입찰] 완료: 총 {len(sorted_results)}건")
        return sorted_results


def search_gbdc_bid(keyword="", max_pages=1):
    """
    경상북도개발공사 입찰공고 검색 편의 함수

    Args:
        keyword: 검색어 (제목 검색)
        max_pages: 최대 페이지 수

    Returns:
        dict: 검색 결과
    """
    crawler = GBDCBidCrawler()
    return crawler.search(keyword=keyword, max_pages=max_pages)


def main():
    """테스트 실행"""
    import sys
    keyword = sys.argv[1] if len(sys.argv) > 1 else ""

    print(f"\n{'='*60}")
    print(f" 경상북도개발공사 입찰공고 검색")
    print(f" 키워드: {keyword or '전체'}")
    print(f"{'='*60}\n")

    results = search_gbdc_bid(keyword, max_pages=3)

    print(f"\n{'='*60}")
    print(f" 검색 결과: {len(results)}건")
    print(f"{'='*60}\n")

    for i, r in enumerate(results[:10], 1):
        notice = "[공지] " if r["is_notice"] else ""
        print(f"{i}. {notice}{r['title'][:50]}")
        print(f"   날짜: {r['date']} | 부서: {r['organization']}")
        print()


if __name__ == "__main__":
    main()
