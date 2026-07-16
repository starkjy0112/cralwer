# -*- coding: utf-8 -*-
"""
의왕도시공사 (uuc) - xlsx 54행
통합검색 페이지 (base/search/view?searchType=BOARD) 기반.

빈 검색이 허용되지 않으므로, 광범위 커버리지를 갖는 다중 키워드
('의', '이', '다', '의왕')를 조합하여 결과를 dedup 한다.
"""
import re
import ssl
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs


class _TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=0')
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            ctx.minimum_version = ssl.TLSVersion.TLSv1
        except Exception:
            pass
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)


class UUCCrawler:
    """의왕도시공사 통합검색 크롤러."""

    BASE_URL = "https://www.uuc.or.kr"
    SEARCH_PATH = "/base/search/view"

    # 공백(+) 검색이 전량 반환 (14,138건, 1,414페이지). 사이트 실측과 일치.
    KEYWORDS = [' ']

    MAX_RETRIES = 4
    PAGE_DELAY = 0.15
    MAX_PAGES_PER_KEYWORD = 1000  # 안전 상한

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9",
        })
        self.session.mount("https://", _TLSAdapter(pool_connections=1, pool_maxsize=20))
        self.session.verify = False

    # ------------------------------------------------------------------ HTTP
    def _fetch(self, keyword, page):
        params = {
            'searchType': 'BOARD',
            'searchWord': keyword,
            'page': page,
        }
        for attempt in range(self.MAX_RETRIES):
            try:
                r = self.session.get(
                    self.BASE_URL + self.SEARCH_PATH,
                    params=params,
                    timeout=30,
                )
                r.raise_for_status()
                r.encoding = 'utf-8'
                return BeautifulSoup(r.text, 'lxml')
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1.5 * (attempt + 1))
        return None

    # ------------------------------------------------------------------ PARSE
    @staticmethod
    def _last_page(soup):
        """페이지네이션에서 최종 페이지 번호 반환. 실패 시 0."""
        if not soup:
            return 0
        maxp = 0
        for a in soup.select('.pagination a, .paging a, a[href*="page="]'):
            href = a.get('href', '') or ''
            m = re.search(r'[?&]page=(\d+)', href)
            if m:
                p = int(m.group(1))
                if p > maxp:
                    maxp = p
        return maxp

    @staticmethod
    def _normalize_url(href):
        """의왕도시공사 결과 링크를 canonical URL로 변환.
        - 스킴/호스트 유지
        - menuLevel/menuNo 제거 (같은 게시글이 여러 menu로 노출됨)
        - boardManagementNo, boardNo만 유지
        """
        if not href:
            return None, None, None
        try:
            u = urlparse(href)
            qs = parse_qs(u.query)
            bm = (qs.get('boardManagementNo') or [None])[0]
            bn = (qs.get('boardNo') or [None])[0]
            if not (bm and bn):
                return None, None, None
            canon = (
                f"https://www.uuc.or.kr/base/board/read"
                f"?boardManagementNo={bm}&boardNo={bn}"
            )
            return canon, bm, bn
        except Exception:
            return None, None, None

    def _parse_items(self, soup):
        items = []
        if not soup:
            return items
        for li in soup.select('.sch_result_page_list.type2 > li'):
            a = li.select_one('a.tit_link') or li.select_one('a[href*="boardNo="]')
            if not a:
                continue
            canon, bm, bn = self._normalize_url(a.get('href', ''))
            if not canon:
                continue

            # 제목: [카테고리] 접두를 걷어내고 정리
            title_raw = a.get_text(' ', strip=True)
            title_raw = re.sub(r'\s+', ' ', title_raw).strip()
            # 앞머리 대괄호 카테고리 제거 (예: "[감사 · 윤리] 제목")
            m = re.match(r'^\[([^\]]{1,40})\]\s*(.+)$', title_raw)
            category = ''
            if m:
                category = m.group(1).strip()
                title = m.group(2).strip()
            else:
                title = title_raw

            if not title or len(title) < 2:
                continue

            # 날짜
            date = ''
            date_el = li.select_one('.date')
            if date_el:
                m2 = re.search(
                    r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})',
                    date_el.get_text(),
                )
                if m2:
                    date = f"{m2.group(1)}-{m2.group(2).zfill(2)}-{m2.group(3).zfill(2)}"

            # 게시판 경로 (예: "커뮤니티 > 공지사항")
            board_path = ''
            depth_el = li.select_one('.depth')
            if depth_el:
                board_path = re.sub(r'\s+', ' ', depth_el.get_text(' ', strip=True))
                board_path = board_path.replace(' > ', '>').replace('>', ' > ')

            items.append({
                'title': title,
                'date': date,
                'url': canon,
                'organization': board_path or category or '통합검색',
                'number': bn,
            })
        return items

    # ------------------------------------------------------------------ MAIN
    def _crawl_keyword(self, keyword, seen):
        soup = self._fetch(keyword, 1)
        if not soup:
            return 0
        last = self._last_page(soup)
        if last <= 0:
            last = 1

        page1_items = self._parse_items(soup)
        added = 0
        for it in page1_items:
            if it['url'] not in seen:
                seen[it['url']] = it
                added += 1

        empty_streak = 0
        for page in range(2, min(last, self.MAX_PAGES_PER_KEYWORD) + 1):
            time.sleep(self.PAGE_DELAY)
            soup = self._fetch(keyword, page)
            if not soup:
                empty_streak += 1
                if empty_streak >= 3:
                    break
                continue
            items = self._parse_items(soup)
            if not items:
                empty_streak += 1
                if empty_streak >= 3:
                    break
                continue
            empty_streak = 0
            page_added = 0
            for it in items:
                if it['url'] not in seen:
                    seen[it['url']] = it
                    page_added += 1
            added += page_added

        print(
            f"  [의왕도시공사] kw='{keyword}' last_page={last} 신규+{added}",
            flush=True,
        )
        return added

    def search(self, keyword='', max_pages=999, start_date=None, end_date=None):
        seen = {}
        for kw in self.KEYWORDS:
            try:
                self._crawl_keyword(kw, seen)
            except Exception as e:
                print(f"  [의왕도시공사] kw='{kw}' 에러: {str(e)[:120]}", flush=True)
            time.sleep(0.3)

        items = list(seen.values())

        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        items = [
            it for it in items
            if not it['date'] or (start_date <= it['date'][:10] <= end_date)
        ]
        items.sort(key=lambda x: x['date'] or '', reverse=True)
        print(f"[의왕도시공사] 완료: 총 {len(items)}건", flush=True)
        return items


def main():
    import urllib3
    urllib3.disable_warnings()
    c = UUCCrawler()
    t0 = time.time()
    items = c.search(start_date='2000-01-01', end_date='2099-12-31')
    print(f'{len(items)}건 / {time.time()-t0:.0f}초')
    from collections import Counter
    for k, v in Counter(it['organization'] for it in items).most_common(20):
        print(f'  {k}: {v}')


if __name__ == "__main__":
    main()
