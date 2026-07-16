# -*- coding: utf-8 -*-
"""
광주광역시도시공사 (gmcc) - xlsx 38행
통합검색(findeepSearch.es) 직접 크롤.

빈 키워드 검색 불가 → 여러 고빈도 키워드로 검색 후 dedup.
"""
import re
import time
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


class GMCCCrawler:
    """광주광역시도시공사 통합검색 크롤러."""

    BASE_URL = "https://www.gmcc.co.kr"
    SEARCH_URL = f"{BASE_URL}/findeepSearch.es"
    MID = "a10603000000"

    # 키워드: DB에서 xlsx 기본 25개 + 사용자 추가분 로드 + 광범위 6개
    # DB 실패 시 xlsx 기본 25개 폴백 → crawler_config 관리
    BROAD_KEYWORDS = ["공사", "용역", "입찰", "공고", "사", "공"]

    @property
    def KEYWORDS(self):
        """런타임 로드 - 관리자 페이지에서 검색어 추가 시 즉시 반영."""
        from crawler_config import get_keywords
        return get_keywords() + self.BROAD_KEYWORDS

    PAGE_CNT = 100  # 페이지당 큼(요청수 감소)
    MAX_PAGES = 600
    MAX_RETRIES = 4
    PAGE_DELAY = 0.25

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/131.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9",
        })
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.verify = False

    def _fetch(self, keyword, page):
        data = {
            "mid": self.MID,
            "act": "vw_search_board",
            "allKeyWord": keyword,
            "nPage": str(page),
            "pageCnt": str(self.PAGE_CNT),
            "sort": "created:desc",
        }
        for attempt in range(self.MAX_RETRIES):
            try:
                r = self.session.post(
                    f"{self.SEARCH_URL}?mid={self.MID}",
                    data=data, timeout=30,
                )
                r.raise_for_status()
                r.encoding = 'utf-8'
                return BeautifulSoup(r.text, 'lxml'), r.text
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1.5 * (attempt + 1))
        return None, ''

    def _get_last_page(self, soup):
        """마지막 페이지 번호 파싱."""
        last = soup.select_one('a.arr.last')
        if last:
            m = re.search(r'nPage=(\d+)', last.get('href', ''))
            if m:
                return int(m.group(1))
        nums = []
        for a in soup.select('a[href*="nPage="]'):
            m = re.search(r'nPage=(\d+)', a.get('href', ''))
            if m:
                nums.append(int(m.group(1)))
        return max(nums) if nums else 1

    def _parse_items(self, soup):
        """검색결과 리스트 파싱."""
        results = []
        if not soup:
            return results
        # 게시물 검색 결과 리스트: div.search_view_box.result_b > ul.list > li
        section = soup.select_one('div.search_view_box.result_b')
        if not section:
            # act=vw_search_board 페이지에서는 result_b 대신 다른 컨테이너일 수도 있음
            section = soup

        for li in section.select('li'):
            title_a = li.select_one('div.title strong a')
            if not title_a:
                continue
            href = title_a.get('href', '') or ''
            if 'board.es' not in href or 'list_no=' not in href:
                continue
            m = re.search(r'list_no=(\d+)', href)
            if not m:
                continue
            list_no = m.group(1)

            # 제목: 하이라이트 <i> 태그 제거 후 텍스트
            title = title_a.get_text(' ', strip=True)
            title = re.sub(r'\s+', ' ', title).strip()
            if not title or len(title) < 2:
                continue

            # 날짜: span.date
            date = ''
            date_el = li.select_one('span.date')
            if date_el:
                t = date_el.get_text(' ', strip=True)
                m2 = re.search(r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})', t)
                if m2:
                    date = f"{m2.group(1)}-{m2.group(2).zfill(2)}-{m2.group(3).zfill(2)}"

            # 카테고리(경로) 파싱: span.path
            board_name = ''
            path_el = li.select_one('span.path a')
            if path_el:
                board_name = path_el.get_text(' ', strip=True)
                board_name = re.sub(r'\s+', ' ', board_name).strip()

            results.append({
                'title': title,
                'date': date,
                'url': href,
                'organization': board_name or '통합검색',
                'number': list_no,
            })
        return results

    def _crawl_keyword(self, keyword):
        results = []
        first_soup, _ = self._fetch(keyword, 1)
        if not first_soup:
            return results
        last_p = self._get_last_page(first_soup)
        if last_p > self.MAX_PAGES:
            last_p = self.MAX_PAGES

        results.extend(self._parse_items(first_soup))

        empty_streak = 0
        for page in range(2, last_p + 1):
            time.sleep(self.PAGE_DELAY)
            soup, _ = self._fetch(keyword, page)
            page_items = self._parse_items(soup)
            if not page_items:
                empty_streak += 1
                if empty_streak >= 3:
                    break
            else:
                empty_streak = 0
                results.extend(page_items)
        return results

    def search(self, keyword='', max_pages=999, start_date=None, end_date=None):
        all_results = {}
        for kw in self.KEYWORDS:
            try:
                items = self._crawl_keyword(kw)
                added = 0
                for r in items:
                    if r['number'] not in all_results:
                        all_results[r['number']] = r
                        added += 1
                print(f"  [키워드 '{kw}'] {len(items)}건 (신규 {added})", flush=True)
            except Exception as e:
                print(f"  [키워드 '{kw}'] 에러: {str(e)[:80]}", flush=True)
            time.sleep(0.5)

        items = list(all_results.values())
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        items = [it for it in items
                 if not it['date'] or (start_date <= it['date'][:10] <= end_date)]
        items.sort(key=lambda x: x['date'] or '', reverse=True)
        print(f"[광주광역시도시공사] 완료: 총 {len(items)}건", flush=True)
        return items


def main():
    import urllib3
    urllib3.disable_warnings()
    c = GMCCCrawler()
    t0 = time.time()
    items = c.search(start_date='2000-01-01', end_date='2099-12-31')
    print(f'{len(items)}건 / {time.time()-t0:.0f}초')
    from collections import Counter
    for k, v in Counter(it['organization'] for it in items).most_common(20):
        print(f'  {k}: {v}')


if __name__ == "__main__":
    main()
