# -*- coding: utf-8 -*-
"""
GH 경기주택도시공사 (gh) - xlsx 39행
다게시판 직접 크롤. article.offset 페이징.
"""
import re
import time
import math
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


class GHCrawler:
    """GH 경기주택도시공사 다게시판 통합 크롤러."""

    BASE_URL = "https://www.gh.or.kr"
    PAGE_SIZE = 10

    # (path, 표시명)
    BOARDS = [
        ('/gh/technical-suggestion-notice-list.do', '기술제안공고'),
    ]

    MAX_RETRIES = 5
    PAGE_DELAY = 0.3

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

    def _fetch(self, path, offset):
        url = f"{self.BASE_URL}{path}?mode=list&articleLimit={self.PAGE_SIZE}&article.offset={offset}"
        for attempt in range(self.MAX_RETRIES):
            try:
                r = self.session.get(url, timeout=30)
                r.raise_for_status()
                r.encoding = 'utf-8'
                return BeautifulSoup(r.text, 'lxml'), r.text
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1.5 * (attempt + 1))
        return None, ''

    def _get_total(self, html):
        m = re.search(r'총\s*<[^>]*>\s*(\d+)', html)
        if m:
            return int(m.group(1))
        # last offset
        m2 = re.search(r'article\.offset=(\d+)[^"]*"[^>]*(?:title="[^"]*마지막|class="[^"]*last)', html)
        if m2:
            return int(m2.group(1)) + self.PAGE_SIZE
        return 0

    def _parse_rows(self, soup, board_name, path):
        results = []
        if not soup:
            return results
        for tr in soup.select('tbody tr'):
            a = tr.select_one('td.title a, .b-title-box a, a[href*="mode=view"], a[href*="articleNo"]')
            if not a:
                continue
            href = a.get('href', '') or ''
            m = re.search(r'articleNo=(\d+)', href)
            if not m:
                continue
            article_no = m.group(1)
            url = f"{self.BASE_URL}{path}?mode=view&articleNo={article_no}"
            title = (a.get('title') or a.get_text(' ', strip=True)).strip()
            title = re.sub(r'\s*자세히\s*보기\s*$', '', title)
            title = re.sub(r'\s+', ' ', title)
            if not title or len(title) < 2:
                continue
            # 날짜 (26.07.03 형식 or YYYY-MM-DD)
            date = ''
            for td in tr.find_all('td'):
                t = td.get_text(' ', strip=True)
                m2 = re.search(r'(\d{2,4})[-./](\d{1,2})[-./](\d{1,2})', t)
                if m2:
                    y = m2.group(1)
                    if len(y) == 2:
                        y = '20' + y
                    date = f"{y}-{m2.group(2).zfill(2)}-{m2.group(3).zfill(2)}"
                    break
            results.append({
                'title': title, 'date': date, 'url': url,
                'organization': board_name, 'number': article_no,
            })
        return results

    def _crawl_board(self, board_tuple):
        path, board_name = board_tuple
        results = []
        seen = set()
        first_soup, first_html = self._fetch(path, 0)
        if not first_soup:
            return results
        total = self._get_total(first_html)
        if total < 1:
            # 총 표시 없어도 첫 페이지에 데이터 있을 수 있음
            first_rows = self._parse_rows(first_soup, board_name, path)
            for it in first_rows:
                if it['url'] not in seen:
                    seen.add(it['url'])
                    results.append(it)
            if not first_rows:
                return results
            # 페이지 모름 → 30 offset 순차 (300건 상한)
            empty = 0
            for offset in range(self.PAGE_SIZE, 30 * self.PAGE_SIZE, self.PAGE_SIZE):
                time.sleep(self.PAGE_DELAY)
                soup, _ = self._fetch(path, offset)
                rows = self._parse_rows(soup, board_name, path)
                new_cnt = 0
                for it in rows:
                    if it['url'] not in seen:
                        seen.add(it['url']); results.append(it); new_cnt += 1
                if not rows or new_cnt == 0:
                    empty += 1
                    if empty >= 2: break
                else:
                    empty = 0
            return results

        # total 있음 - 정확히 페이징
        for it in self._parse_rows(first_soup, board_name, path):
            if it['url'] not in seen:
                seen.add(it['url']); results.append(it)
        last_offset = ((total - 1) // self.PAGE_SIZE) * self.PAGE_SIZE
        for offset in range(self.PAGE_SIZE, last_offset + 1, self.PAGE_SIZE):
            time.sleep(self.PAGE_DELAY)
            soup, _ = self._fetch(path, offset)
            for it in self._parse_rows(soup, board_name, path):
                if it['url'] not in seen:
                    seen.add(it['url']); results.append(it)
        return results

    def search(self, keyword='', max_pages=999, start_date=None, end_date=None):
        all_results = {}
        for board in self.BOARDS:
            try:
                items = self._crawl_board(board)
                for r in items:
                    if r['url'] not in all_results:
                        all_results[r['url']] = r
                print(f"  [{board[1]}] {len(items)}건", flush=True)
            except Exception as e:
                print(f"  [{board[1]}] 에러: {str(e)[:60]}", flush=True)
            time.sleep(0.5)

        items = list(all_results.values())
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        items = [it for it in items
                 if not it['date'] or (start_date <= it['date'][:10] <= end_date)]
        items.sort(key=lambda x: x['date'] or '', reverse=True)
        print(f"[GH 경기주택도시공사] 완료: 총 {len(items)}건", flush=True)
        return items


def main():
    import urllib3
    urllib3.disable_warnings()
    c = GHCrawler()
    t0 = time.time()
    items = c.search(start_date='2000-01-01', end_date='2099-12-31')
    print(f'{len(items)}건 / {time.time()-t0:.0f}초')
    from collections import Counter
    for k, v in Counter(it['organization'] for it in items).most_common():
        print(f'  {k}: {v}')


if __name__ == "__main__":
    main()
