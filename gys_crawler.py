# -*- coding: utf-8 -*-
"""
고양도시관리공사 (gys) - xlsx 40행
UTF-8 응답 (강제), 7개 게시판 합산.
"""
import re
import time
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


class GYSCrawler:
    """고양도시관리공사 다게시판 통합 크롤러."""

    BASE_URL = "https://www.gys.or.kr"

    # (subpage_id, board_key, 표시명)
    BOARDS = [
        (46, 'BID', '입찰공고고시'),
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

    def _fetch(self, url):
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

    def _get_last_page(self, soup):
        last = soup.select_one('.page_last a, .page_end a, a[title*="마지막"]')
        if last:
            m = re.search(r'/(\d+)/$', last.get('href', ''))
            if m:
                return int(m.group(1))
        # fallback: 최대 페이지 번호
        nums = []
        for a in soup.select('.pagination a[href*="/llist/"]'):
            m = re.search(r'/(\d+)/$', a.get('href', ''))
            if m:
                nums.append(int(m.group(1)))
        return max(nums) if nums else 1

    def _parse_rows(self, soup, board_name):
        results = []
        if not soup:
            return results
        for tr in soup.select('tbody tr'):
            tds = tr.find_all('td')
            if len(tds) < 3:
                continue
            a = tr.select_one('a[href*="/view/"], td.left a, a[title*="게시물"]')
            if not a:
                continue
            href = a.get('href', '') or ''
            if '/view/' not in href:
                continue
            url = href if href.startswith('http') else f"{self.BASE_URL}{href}"
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
                'organization': board_name, 'number': tds[0].get_text(strip=True),
            })
        return results

    def _crawl_board(self, board_tuple):
        sub_id, key, board_name = board_tuple
        results = []
        seen = set()
        first_url = f"{self.BASE_URL}/subpage/index/{sub_id}"
        first_soup, _ = self._fetch(first_url)
        if not first_soup:
            return results
        last_p = self._get_last_page(first_soup)
        # 페이지 URL 템플릿 자동 추출 (subpage id/L/F 문자 게시판마다 다름)
        page_tpl = None
        for a in first_soup.select('.pagination a[href*="/llist/"]'):
            href = a.get('href', '')
            m = re.search(r'(https?://[^/]+/subpage/index/\d+/llist/[^/]+/[LF]/[^/]+/\d+/\d+/-/\d+/)(\d+)/', href)
            if m:
                page_tpl = m.group(1) + '{page}/'
                break
        for it in self._parse_rows(first_soup, board_name):
            if it['url'] not in seen:
                seen.add(it['url'])
                results.append(it)
        empty = 0
        page = 2
        # last_p가 실제 마지막보다 작을 수 있음 - rows=0까지 계속
        while page < 500:  # 안전 상한
            time.sleep(self.PAGE_DELAY)
            if page_tpl:
                page_url = page_tpl.replace('{page}', str(page))
            else:
                page_url = f"{self.BASE_URL}/subpage/index/{sub_id}/llist/{key}/F/GYS/0/0/-/0/{page}/"
            soup, _ = self._fetch(page_url)
            rows = self._parse_rows(soup, board_name)
            new_cnt = 0
            for it in rows:
                if it['url'] not in seen:
                    seen.add(it['url'])
                    results.append(it)
                    new_cnt += 1
            if not rows:
                empty += 1
                if empty >= 3:
                    break
            elif page > last_p and new_cnt == 0:
                # last_p 이후에 페이지 있어도 신규 없으면 종료
                empty += 1
                if empty >= 3:
                    break
            else:
                empty = 0
            page += 1
        return results

    def search(self, keyword='', max_pages=999, start_date=None, end_date=None):
        all_results = {}
        for board in self.BOARDS:
            try:
                items = self._crawl_board(board)
                for r in items:
                    if r['url'] not in all_results:
                        all_results[r['url']] = r
                print(f"  [{board[2]}] {len(items)}건", flush=True)
            except Exception as e:
                print(f"  [{board[2]}] 에러: {str(e)[:60]}", flush=True)
            time.sleep(0.5)

        items = list(all_results.values())
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        items = [it for it in items
                 if not it['date'] or (start_date <= it['date'][:10] <= end_date)]
        items.sort(key=lambda x: x['date'] or '', reverse=True)
        print(f"[고양도시관리공사] 완료: 총 {len(items)}건", flush=True)
        return items


def main():
    import urllib3
    urllib3.disable_warnings()
    c = GYSCrawler()
    t0 = time.time()
    items = c.search(start_date='2000-01-01', end_date='2099-12-31')
    print(f'{len(items)}건 / {time.time()-t0:.0f}초')
    from collections import Counter
    for k, v in Counter(it['organization'] for it in items).most_common():
        print(f'  {k}: {v}')


if __name__ == "__main__":
    main()
