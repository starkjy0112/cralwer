# -*- coding: utf-8 -*-
"""
경남개발공사 공고 크롤러
requests + API 방식 (헤더 설정으로 한글 정상 출력)
"""
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


class GNDCCrawler:
    """경남개발공사 공고 크롤러"""

    def __init__(self):
        self.base_url = "https://www.gndc.co.kr"
        self.board_url = f"{self.base_url}/boardlist.do?seqId=0000000048"
        self.api_url = f"{self.base_url}/getBbsArticleList.do"
        self.bbs_id = "B491A490314446318099F9D828047900"
        self.session = None
        self.tokens = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        }

    def _init_session(self):
        """세션 초기화 및 토큰 획득"""
        self.session = requests.Session()
        response = self.session.get(self.board_url, headers=self.headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        form = soup.find("form", {"name": "search_form"})
        if form:
            pt_sig = form.find("input", {"name": "ptSignature"})
            cs_sig = form.find("input", {"name": "csSignature"})
            self.tokens = {
                "ptSignature": pt_sig["value"] if pt_sig else "",
                "csSignature": cs_sig["value"] if cs_sig else ""
            }
        return bool(self.tokens)

    def _fetch_page(self, keyword: str, page: int):
        """API로 페이지 조회"""
        data = {
            "BBS_ID": self.bbs_id,
            "BBS_TYPE": "L",
            "CURRENT_PAGE": page,
            "SEARCH_CONTITION": "CPDS_SUBJECT",  # 제목 검색 (오타 아님, 서버가 이렇게 씀)
            "SEARCH_KEYWORD": keyword,
            **self.tokens
        }

        try:
            response = self.session.post(self.api_url, data=data, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[오류] 페이지 {page}: {e}")
            return None

    def _parse_response(self, data):
        """API 응답 파싱"""
        results = []
        articles = data.get("articallist", [])

        for item in articles:
            idx = item.get("IPDS_IDX", "")
            is_notice = item.get("MUST_LVL", 0) > 0

            results.append({
                "number": "공지" if is_notice else str(item.get("RN", "")),
                "category": item.get("CTGR_NM", ""),
                "title": item.get("CPDS_SUBJECT", ""),
                "organization": item.get("CPDS_NAME", ""),
                "date": item.get("RGST_DTM", "")[:10] if item.get("RGST_DTM") else "",
                "views": str(item.get("IPDS_COUNTS", "")),
                "url": f"{self.base_url}/boardview.do?seqId=0000000048&BBS_ID={self.bbs_id}&IPDS_IDX={idx}" if idx else "",
                "is_notice": is_notice,
            })

        return results

    WORKERS = 5

    def _fetch_and_parse(self, keyword: str, page: int):
        """페이지 조회 + 파싱"""
        data = self._fetch_page(keyword, page)
        if not data:
            return []
        return self._parse_response(data)

    def search(self, keyword: str = "", max_pages: int = 50):
        """
        공고 검색 (페이지네이션 지원)

        Args:
            keyword: 검색 키워드
            max_pages: 최대 페이지 수

        Returns:
            검색 결과 리스트
        """
        print(f"[경남개발공사] 검색 중 (키워드: '{keyword or '전체'}')...")

        # 세션 초기화
        if not self._init_session():
            print("[오류] 세션 초기화 실패")
            return []

        # 첫 페이지로 전체 페이지 수 파악
        first_data = self._fetch_page(keyword, 1)
        if not first_data:
            return []

        paging = first_data.get("paginginfo", {})
        total_count = paging.get("totalCount", 0)
        total_pages = min(paging.get("totalPage", 1), max_pages)

        print(f"[경남개발공사] 총 {total_count}건, {total_pages}페이지")

        first_results = self._parse_response(first_data)

        if total_pages <= 1:
            all_results = first_results
        else:
            # 나머지 페이지 병렬 조회
            page_results = {1: first_results}
            with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_and_parse, keyword, p): p
                    for p in range(2, total_pages + 1)
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

        # 날짜순 정렬 (최신순)
        all_results.sort(key=lambda x: x.get("date", ""), reverse=True)

        # 공지 제외 건수
        data_count = len([r for r in all_results if not r["is_notice"]])
        print(f"[경남개발공사] 완료: 총 {len(all_results)}건 (공지 제외: {data_count}건)")
        return all_results


def search_gndc(keyword: str = ""):
    """간단한 검색 함수"""
    crawler = GNDCCrawler()
    return crawler.search(keyword)


def main():
    """테스트 실행"""
    import sys

    keyword = sys.argv[1] if len(sys.argv) > 1 else ""

    print(f"\n{'='*60}")
    print(f" 경남개발공사 공고 검색")
    print(f" 키워드: {keyword or '전체'}")
    print(f"{'='*60}\n")

    results = search_gndc(keyword)

    print(f"\n{'='*60}")
    print(f" 검색 결과: {len(results)}건")
    print(f"{'='*60}\n")

    for i, r in enumerate(results[:10], 1):
        notice = "[공지] " if r["is_notice"] else ""
        print(f"{i}. {notice}[{r['category']}] {r['title'][:40]}")
        print(f"   날짜: {r['date']} | 작성자: {r['writer']}")
        print()


if __name__ == "__main__":
    main()
