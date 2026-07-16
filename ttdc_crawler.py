# -*- coding: utf-8 -*-
"""
통영관광개발공사 (ttdc) - xlsx 36행
7개 게시판 합산. startIndex 페이징 (10단위).
"""
import re
import time
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


class TTDCCrawler:
    """통영관광개발공사 다게시판 통합 크롤러."""

    BASE_URL = "http://corp.ttdc.kr"
    LIST_URL = f"{BASE_URL}/board/board.aspx"
    PAGE_SIZE = 10

    BOARDS = [
        ('bidding', '입찰정보'),  # xlsx 36행 지정
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
        self.session.mount("http://", adapter)

    def _fetch(self, tbl, start_index):
        url = f"{self.LIST_URL}?tbl={tbl}&startIndex={start_index}"
        for attempt in range(self.MAX_RETRIES):
            try:
                r = self.session.get(url, timeout=30)
                r.raise_for_status()
                return BeautifulSoup(r.text, 'lxml')
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1.5 * (attempt + 1))
        return None

    def _get_first_num(self, soup):
        if not soup:
            return 0
        tr = soup.select_one('tbody tr')
        if not tr:
            return 0
        td = tr.find('td')
        try:
            return int(td.get_text(strip=True))
        except Exception:
            return 0

    def _parse_rows(self, soup, board_name, tbl):
        results = []
        if not soup:
            return results
        for tr in soup.select('tbody tr'):
            tds = tr.find_all('td')
            if len(tds) < 3:
                continue
            a = tr.select_one('td.title a, a[href*="mode=view"], a[href*="seq="]')
            if not a:
                continue
            href = a.get('href', '')
            m = re.search(r'seq=(\d+)', href)
            if not m:
                continue
            seq = m.group(1)
            url = f"{self.BASE_URL}{href}" if href.startswith('/') else (
                href if href.startswith('http') else f"{self.LIST_URL}?tbl={tbl}&mode=view&seq={seq}")
            url = re.sub(r'&startIndex=\d+', '', url)
            title = a.get_text(' ', strip=True)
            if not title or len(title) < 2:
                continue
            num = tds[0].get_text(strip=True)
            date = ''
            for td in tds:
                t = td.get_text(' ', strip=True)
                m2 = re.search(r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})', t)
                if m2:
                    date = f"{m2.group(1)}-{m2.group(2).zfill(2)}-{m2.group(3).zfill(2)}"
                    break
            results.append({
                'title': title, 'date': date, 'url': url,
                'organization': board_name, 'number': num,
            })
        return results

    def _crawl_board(self, board_tuple):
        tbl, board_name = board_tuple
        results = []
        seen = set()
        first = self._fetch(tbl, 0)
        if not first:
            return results
        for it in self._parse_rows(first, board_name, tbl):
            if it['url'] not in seen:
                seen.add(it['url'])
                results.append(it)
        # 끝까지 페이지네이션 - 새 항목 0이면 종료 (잘못된 startIndex는 첫 페이지로 reset됨)
        empty_streak = 0
        start = self.PAGE_SIZE
        while start < 20000:  # 안전 상한
            time.sleep(self.PAGE_DELAY)
            soup = self._fetch(tbl, start)
            rows = self._parse_rows(soup, board_name, tbl)
            new_cnt = 0
            for it in rows:
                if it['url'] not in seen:
                    seen.add(it['url'])
                    results.append(it)
                    new_cnt += 1
            if new_cnt == 0:
                empty_streak += 1
                if empty_streak >= 2:
                    break
            else:
                empty_streak = 0
            start += self.PAGE_SIZE
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
            time.sleep(0.8)

        items = list(all_results.values())
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        items = [it for it in items
                 if not it['date'] or (start_date <= it['date'][:10] <= end_date)]
        items.sort(key=lambda x: x['date'] or '', reverse=True)
        print(f"[통영관광개발공사] 완료: 총 {len(items)}건", flush=True)
        return items


def main():
    c = TTDCCrawler()
    t0 = time.time()
    items = c.search(start_date='2000-01-01', end_date='2099-12-31')
    print(f'{len(items)}건 / {time.time()-t0:.0f}초')
    from collections import Counter
    for k, v in Counter(it['organization'] for it in items).most_common():
        print(f'  {k}: {v}')


if __name__ == "__main__":
    main()
