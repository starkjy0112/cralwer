# -*- coding: utf-8 -*-
"""
경남개발공사 공고 크롤러
requests + API 방식 (헤더 설정으로 한글 정상 출력)
"""
import re
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


class GNDCCrawler:
    """경남개발공사 공고 크롤러"""

    # xlsx URL: seqId=6241 통합공고 (전체 602건, 임대/분양 통합)
    BOARDS = [
        ("0000006241", "통합공고"),
    ]
    BBS_ID = "B491A490314446318099F9D828047900"

    def __init__(self):
        self.base_url = "https://www.gndc.co.kr"
        self.api_url = f"{self.base_url}/getBbsArticleList.do"
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'X-Requested-With': 'XMLHttpRequest',
        }

    def _init_session(self):
        """세션 초기화 (쿠키 획득만 하면 됨)"""
        self.session = requests.Session()
        try:
            # 임의 게시판 페이지로 쿠키 확보
            self.session.get(
                f"{self.base_url}/boardlist.do?seqId={self.BOARDS[0][0]}",
                headers=self.headers, timeout=15,
            )
            return True
        except Exception as e:
            print(f"[오류] 세션 초기화: {e}")
            return False

    def _fetch_page(self, seq_id: str, keyword: str, page: int):
        """API로 페이지 조회 (GET 방식)"""
        params = {
            "BBS_ID": self.BBS_ID,
            "BBS_TYPE": "L",
            "CURRENT_PAGE": str(page),
            "SEARCH_CONTITION": "CPDS_SUBJECT_CONTENT",
            "SEARCH_KEYWORD": keyword,
        }
        try:
            response = self.session.get(
                self.api_url, params=params, headers=self.headers, timeout=15,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[오류] seq={seq_id} 페이지 {page}: {e}")
            return None

    def _parse_response(self, data, seq_id: str, board_name: str):
        """API 응답 파싱"""
        results = []
        articles = data.get("resultList", []) or []

        for item in articles:
            idx = item.get("IPDS_IDX", "") or ""
            must_lvl = item.get("MUST_LVL")
            try:
                is_notice = must_lvl is not None and int(must_lvl) >= 1
            except (TypeError, ValueError):
                is_notice = False

            date_val = (
                item.get("RGST_DTM")
                or item.get("CPDS_WDATE")
                or ""
            )
            date_val = (date_val or "")[:10]

            results.append({
                "number": "공지" if is_notice else str(item.get("BNUM", "") or item.get("RNUM", "")),
                "category": board_name,
                "title": item.get("CPDS_SUBJECT", ""),
                "organization": item.get("CPDS_NAME", ""),
                "writer": item.get("CPDS_NAME", ""),
                "date": date_val,
                "views": str(item.get("IPDS_COUNTS", "") or ""),
                "url": (
                    f"{self.base_url}/boardview/boardview.do?seqId={seq_id}"
                    f"&BBS_ID={self.BBS_ID}&IPDS_IDX={idx}&BBS_TYPE=L"
                ) if idx else "",
                "is_notice": is_notice,
            })

        return results

    WORKERS = 20

    def _fetch_and_parse(self, seq_id: str, board_name: str, keyword: str, page: int):
        """페이지 조회 + 파싱"""
        data = self._fetch_page(seq_id, keyword, page)
        if not data:
            return []
        return self._parse_response(data, seq_id, board_name)

    def _search_board(self, seq_id: str, board_name: str, keyword: str, max_pages: int):
        """단일 게시판 전체 페이지 수집"""
        first_data = self._fetch_page(seq_id, keyword, 1)
        if not first_data:
            return []

        paging = first_data.get("pageInfo", {}) or {}
        total_count = paging.get("totalRecordCount", 0)
        total_pages = min(paging.get("totalPageCount", 1) or 1, max_pages)

        print(f"[경남개발공사] {board_name}: 총 {total_count}건, {total_pages}페이지")

        first_results = self._parse_response(first_data, seq_id, board_name)

        if total_pages <= 1:
            return first_results

        # 나머지 페이지 병렬 조회
        page_results = {1: first_results}
        with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
            futures = {
                executor.submit(self._fetch_and_parse, seq_id, board_name, keyword, p): p
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

        combined = []
        for p in sorted(page_results.keys()):
            combined.extend(page_results[p])
        return combined

    def search(self, keyword: str = "", max_pages: int = 200, start_date=None, end_date=None):
        """
        공고 검색 - 모든 공고성 게시판 수집

        Args:
            keyword: 검색 키워드
            max_pages: 게시판당 최대 페이지 수

        Returns:
            검색 결과 리스트
        """
        print(f"[경남개발공사] 검색 중 (키워드: '{keyword or '전체'}')...")

        # 세션 초기화
        if not self._init_session():
            print("[오류] 세션 초기화 실패")
            return []

        all_results = []
        for seq_id, board_name in self.BOARDS:
            try:
                results = self._search_board(seq_id, board_name, keyword, max_pages)
                all_results.extend(results)
            except Exception as e:
                print(f"[오류] {board_name}: {e}")

        # 날짜순 정렬 (최신순)
        all_results.sort(key=lambda x: x.get("date", ""), reverse=True)

        # 공지 제외 건수
        data_count = len([r for r in all_results if not r["is_notice"]])
        print(f"[경남개발공사] 완료: 총 {len(all_results)}건 (공지 제외: {data_count}건)")

        # 날짜 필터 (기본: 최근 30일)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        all_results = [_item for _item in all_results
                     if (lambda d: d and start_date <= d <= end_date)(
                         (_item.get("date") or "").replace(".", "-").replace("/", "-")[:10])]

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
