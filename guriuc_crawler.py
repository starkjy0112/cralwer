# -*- coding: utf-8 -*-
"""
구리도시공사 (guriuc) - xlsx 41행
4개 게시판 합산. pageIndex 페이징.
"""
import re
import math
import time
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


class GURIUCCrawler:
    """구리도시공사 다게시판 통합 크롤러."""

    BASE_URL = "https://www.guriuc.or.kr"
    LIST_URL = f"{BASE_URL}/bbsArticle/list.do"
    VIEW_URL = f"{BASE_URL}/bbsArticle/view.do"

    BOARDS = [
        ('BID_INFO', '입찰정보'),
    ]

    MAX_RETRIES = 5
    PAGE_DELAY = 0.3
    PAGE_SIZE = 10

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

    def _fetch(self, bbs_id, page):
        url = f"{self.LIST_URL}?bbsId={bbs_id}&pageIndex={page}"
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
        m = re.search(r'전체\s*<[^>]*>\s*(\d+)', html)
        return int(m.group(1)) if m else 0

    def _parse_rows(self, soup, board_name, bbs_id):
        results = []
        if not soup:
            return results
        for tr in soup.select('tbody tr'):
            tds = tr.find_all('td')
            if len(tds) < 3:
                continue
            a = tr.select_one('a[onclick*="fn_view"], td.cont a')
            if not a:
                continue
            onclick = a.get('onclick', '') or ''
            m = re.search(r'fn_view\((\d+)\)', onclick)
            if not m:
                continue
            nttid = m.group(1)
            url = f"{self.VIEW_URL}?bbsId={bbs_id}&nttId={nttid}"
            title = a.get_text(' ', strip=True)
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
                'organization': board_name, 'number': nttid,
            })
        return results

    def _crawl_board(self, board_tuple):
        bbs_id, board_name = board_tuple
        results = []
        seen = set()
        first_soup, first_html = self._fetch(bbs_id, 1)
        if not first_soup:
            return results
        total = self._get_total(first_html)
        for it in self._parse_rows(first_soup, board_name, bbs_id):
            if it['url'] not in seen:
                seen.add(it['url'])
                results.append(it)
        last_p = max(1, math.ceil(total / self.PAGE_SIZE)) if total else 999
        empty = 0
        for page in range(2, last_p + 1):
            time.sleep(self.PAGE_DELAY)
            soup, _ = self._fetch(bbs_id, page)
            rows = self._parse_rows(soup, board_name, bbs_id)
            for it in rows:
                if it['url'] not in seen:
                    seen.add(it['url'])
                    results.append(it)
            if not rows:
                empty += 1
                if empty >= 3:
                    break
            else:
                empty = 0
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
        print(f"[구리도시공사] 완료: 총 {len(items)}건", flush=True)
        return items


def main():
    import urllib3
    urllib3.disable_warnings()
    c = GURIUCCrawler()
    t0 = time.time()
    items = c.search(start_date='2000-01-01', end_date='2099-12-31')
    print(f'{len(items)}건 / {time.time()-t0:.0f}초')
    from collections import Counter
    for k, v in Counter(it['organization'] for it in items).most_common():
        print(f'  {k}: {v}')


if __name__ == "__main__":
    main()
