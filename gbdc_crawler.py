# -*- coding: utf-8 -*-
"""
경상북도개발공사 통합검색 크롤러
- xlsx 안내 URL: https://www.gbdc.co.kr/totalSearch.do?searchKeywordTotal=&pageIndex=1&tapIdx=2&seqId=0000003893
- tapIdx=2 = 게시판 검색
- 빈 검색 불가 → 고빈도 키워드 다중 검색 후 IPDS_IDX 기준 dedup
- 10건/페이지, pageIndex 페이징
"""
import re
import time
import requests
import urllib3
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings()


class GBDCCrawler:
    """경상북도개발공사 통합검색(tapIdx=2, 게시판 검색) 크롤러"""

    BASE_URL = "https://www.gbdc.co.kr"
    SEARCH_URL = f"{BASE_URL}/totalSearch.do"
    SEQ_ID = "0000003893"
    TAP_IDX = "2"          # 게시판 검색
    PAGE_SIZE = 10
    WORKERS = 4  # 안정성 우선 (rate-limit 회피)
    MAX_RETRIES = 5  # 재시도 강화

    # 사이트 전 게시판을 커버하는 고빈도 키워드 세트
    # xlsx 지정 25개 기술 키워드 + 광범위 커버리지용 6개 = 총 31개
    DEFAULT_KEYWORDS = [
        # xlsx ① 기술 키워드 (특허/신기술 관련 - 25개)
        '기본설계', '실시설계', '기술제안', '제안서', '신기술', '공법', '특허', '특정',
        '발파', '암발파', '미진동', '무진동', '암절취', '흙깍기', '절토', '토공',
        '토목', '토건', '제출', '제안', '부지조성', '단지조성', '산업단지',
        '조성공사', '개발사업',
        # 광범위 커버리지 (일반 공고 커버 - 6개)
        '공사', '용역', '입찰', '공고', '경상', '2',
    ]

    _IPDS_RE = re.compile(r'IPDS_IDX=([^&]+)')
    _TOTAL_RE = re.compile(r'게시판\s*검색\s*\[<span[^>]*>(\d+)')
    _DATE_RE = re.compile(r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})')

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36"),
        })
        adapter = HTTPAdapter(pool_connections=self.WORKERS,
                              pool_maxsize=self.WORKERS * 2)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.verify = False

    def _fetch(self, keyword, page):
        params = {
            'searchKeywordTotal': keyword,
            'pageIndex': str(page),
            'tapIdx': self.TAP_IDX,
            'seqId': self.SEQ_ID,
        }
        for attempt in range(self.MAX_RETRIES):
            try:
                r = self.session.get(self.SEARCH_URL, params=params, timeout=30)
                r.raise_for_status()
                # rate-limit 회피: 각 요청 후 짧은 딜레이
                time.sleep(0.1)
                return r.text
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1.5 * (attempt + 1))  # 백오프
        return ''

    def _total(self, html):
        m = self._TOTAL_RE.search(html or '')
        return int(m.group(1)) if m else 0

    def _parse(self, html):
        """페이지 HTML에서 게시물 리스트 파싱"""
        items = []
        if not html:
            return items
        soup = BeautifulSoup(html, 'lxml')
        for wrap in soup.select('div.sch-list-wrap'):
            a = wrap.select_one('a')
            title_el = wrap.select_one('p.title')
            if not a or not title_el:
                continue
            href = a.get('href', '')
            if 'boardview' not in href:
                continue
            m = self._IPDS_RE.search(href)
            key = m.group(1) if m else href  # 고유 dedup key
            # 하이라이트 <span> 제거하여 원문 제목 복원
            title = title_el.get_text('', strip=True)
            if not title:
                continue
            # 날짜 (write-info의 첫 span)
            date = ''
            write_info = wrap.select_one('div.write-info')
            if write_info:
                dm = self._DATE_RE.search(write_info.get_text(' ', strip=True))
                if dm:
                    date = f'{dm.group(1)}-{dm.group(2).zfill(2)}-{dm.group(3).zfill(2)}'
            # 카테고리 (locate)
            locate_el = wrap.select_one('li.locate')
            board = locate_el.get_text(' ', strip=True) if locate_el else ''
            full_url = href if href.startswith('http') else self.BASE_URL + href
            items.append({
                'key': key,
                'title': title,
                'date': date,
                'url': full_url,
                'organization': '경상북도개발공사',
                'board': board,
                'number': '',
            })
        return items

    def _crawl_keyword(self, keyword):
        """단일 키워드의 전 페이지 순회 (병렬)"""
        first_html = self._fetch(keyword, 1)
        if not first_html:
            return []
        total = self._total(first_html)
        if total == 0:
            return []
        pages = (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE

        results = {}
        for it in self._parse(first_html):
            results[it['key']] = it
        if pages <= 1:
            return list(results.values())

        with ThreadPoolExecutor(max_workers=self.WORKERS) as ex:
            futures = {ex.submit(self._fetch, keyword, pg): pg
                       for pg in range(2, pages + 1)}
            for fut in as_completed(futures):
                try:
                    for it in self._parse(fut.result()):
                        results.setdefault(it['key'], it)
                except Exception:
                    pass
        return list(results.values())

    def search(self, keyword='', max_pages=None, start_date=None, end_date=None):
        """
        통합검색 게시판 tab의 전 게시글 수집
        keyword 지정 시 → 해당 키워드만 검색
        keyword 없음 → DEFAULT_KEYWORDS 다중 검색 후 dedup
        """
        keywords = [keyword] if keyword else self.DEFAULT_KEYWORDS

        merged = {}
        for kw in keywords:
            t0 = time.time()
            items = self._crawl_keyword(kw)
            added = 0
            for it in items:
                if it['key'] not in merged:
                    merged[it['key']] = it
                    added += 1
            print(f"[경상북도개발공사] '{kw}': {len(items)}건 수집, +{added}건 추가 ({int(time.time()-t0)}s)")

        items = list(merged.values())

        # 날짜 필터
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        items = [it for it in items
                 if not it['date'] or (start_date <= it['date'][:10] <= end_date)]
        items.sort(key=lambda x: x['date'] or '', reverse=True)
        print(f"[경상북도개발공사] 완료: 총 {len(items)}건")
        return items


def main():
    c = GBDCCrawler()
    t0 = time.time()
    items = c.search(start_date='2000-01-01', end_date='2099-12-31')
    print(f'{len(items)}건 / {time.time()-t0:.0f}초')
    for r in items[:5]:
        print(f'  [{r["date"]}] {r["title"][:60]}')


if __name__ == "__main__":
    main()
