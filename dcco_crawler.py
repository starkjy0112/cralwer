# -*- coding: utf-8 -*-
"""
대전도시공사 (dcco) - xlsx 45행
web/board/list.do 다게시판 합산.
"""
import re
import time
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


class DCCOCrawler:
    """대전도시공사 다게시판 통합 크롤러."""

    BASE_URL = "https://www.dcco.kr"
    LIST_URL = f"{BASE_URL}/web/board/list.do"
    VIEW_URL = f"{BASE_URL}/web/board/view.do"

    # (mId, 표시명)
    BOARDS = [
        (191, '입찰공고'),
    ]

    MAX_RETRIES = 5
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

    def _fetch(self, mid, page):
        url = f"{self.LIST_URL}?mId={mid}&page={page}"
        for attempt in range(self.MAX_RETRIES):
            try:
                r = self.session.get(url, timeout=30)
                r.raise_for_status()
                r.encoding = 'utf-8'
                return BeautifulSoup(r.text, 'lxml')
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1.5 * (attempt + 1))
        return None

    def _parse_rows(self, soup, board_name, mid):
        results = []
        if not soup:
            return results
        for tr in soup.select('tbody tr'):
            tds = tr.find_all('td')
            if len(tds) < 2:
                continue
            a = tr.select_one('td.subject a, a.fn_btn_view, a[href*="view.do"]')
            if not a:
                continue
            href = a.get('href', '') or ''
            m = re.search(r'brdIdx=(\d+)', href)
            if not m:
                continue
            brd_idx = m.group(1)
            url = f"{self.VIEW_URL}?mId={mid}&brdIdx={brd_idx}"
            title = a.get_text(' ', strip=True)
            title = re.sub(r'\s*새글\s*$', '', title)
            title = re.sub(r'\s+', ' ', title).strip()
            if not title or len(title) < 2:
                continue
            date = ''
            for td in tds:
                t = td.get_text(' ', strip=True)
                m2 = re.search(r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})', t)
                if m2:
                    date = f"{m2.group(1)}-{m2.group(2).zfill(2)}-{m2.group(3).zfill(2)}"
                    break
            results.append({
                'title': title, 'date': date, 'url': url,
                'organization': board_name, 'number': brd_idx,
            })
        return results

    def _crawl_board(self, board_tuple):
        mid, board_name = board_tuple
        results = []
        seen = set()
        empty_streak = 0
        for page in range(1, 500):
            time.sleep(self.PAGE_DELAY if page > 1 else 0)
            soup = self._fetch(mid, page)
            rows = self._parse_rows(soup, board_name, mid)
            new_cnt = 0
            for it in rows:
                if it['url'] not in seen:
                    seen.add(it['url'])
                    results.append(it)
                    new_cnt += 1
            if not rows or new_cnt == 0:
                empty_streak += 1
                if empty_streak >= 2:
                    break
            else:
                empty_streak = 0
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
            time.sleep(0.4)

        items = list(all_results.values())
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        items = [it for it in items
                 if not it['date'] or (start_date <= it['date'][:10] <= end_date)]
        items.sort(key=lambda x: x['date'] or '', reverse=True)
        print(f"[대전도시공사] 완료: 총 {len(items)}건", flush=True)
        return items


def main():
    import urllib3
    urllib3.disable_warnings()
    c = DCCOCrawler()
    t0 = time.time()
    items = c.search(start_date='2000-01-01', end_date='2099-12-31')
    print(f'{len(items)}건 / {time.time()-t0:.0f}초')
    from collections import Counter
    for k, v in Counter(it['organization'] for it in items).most_common():
        print(f'  {k}: {v}')


if __name__ == "__main__":
    main()
