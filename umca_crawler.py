# -*- coding: utf-8 -*-
"""
울산도시공사 (umca) - xlsx 56행
xlsx 통합검색: https://www.umca.co.kr/search/front/Search.jsp

전략: 단일 통합검색 엔드포인트를 다중 키워드(빈 검색 불가)로 조회 → dedup.
menu='게시판' 으로 게시판 결과만 대상. nh=100 (페이지당 100건), st=페이지번호.
"""
import re
import time
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


class UMCACrawler:
    """울산도시공사 통합검색 크롤러."""

    BASE_URL = "https://www.umca.co.kr"
    SEARCH_URL = "https://www.umca.co.kr/search/front/Search.jsp"

    # 빈 검색 불가 → 커버리지 최대화 키워드 조합 (실측: ~1740건 unique)
    KEYWORDS = [
        '울산', '도시', '공고', '공사', '사업', '채용', '주택',
        '결과', '안내', '임대', '계획', '지원', '관리', '분양',
        '아파트', '보상', '용역',
    ]

    PAGE_SIZE = 100
    MAX_PAGES = 15         # 1500건까지 (실측 12페이지면 최대치)
    MAX_RETRIES = 3
    PAGE_DELAY = 0.15

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

    def _post(self, keyword, page):
        data = {
            'qt': keyword,
            'menu': '게시판',
            'section': '',
            'nh': str(self.PAGE_SIZE),
            'st': str(page),
            'adv': '0',
            'sw': '0',
            'searchType': '0',
        }
        for attempt in range(self.MAX_RETRIES):
            try:
                r = self.session.post(self.SEARCH_URL, data=data, timeout=30)
                r.raise_for_status()
                r.encoding = 'utf-8'
                return r.text
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1.2 * (attempt + 1))
        return None

    _URL_RE = re.compile(
        r'view\.do\?bbsId=(BBS_\d+)&mId=(\d+)&dataId=(\d+)'
    )
    _DATE_RE = re.compile(r'(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})')

    # 게시판 경로별 표시명 (브레드크럼: "울산도시공사 > 공지/공고 > 채용공고")
    def _parse_page(self, html):
        results = []
        if not html:
            return results
        soup = BeautifulSoup(html, 'lxml')

        # 각 결과 아이템: <dl class="C_Cts"> 안에 링크/제목/날짜/브레드크럼
        for dl in soup.select('dl.C_Cts'):
            a = dl.find('a', href=self._URL_RE)
            if not a:
                continue
            href = a.get('href', '')
            m = self._URL_RE.search(href)
            if not m:
                continue
            bbs_id, m_id, data_id = m.group(1), m.group(2), m.group(3)
            url = f"{self.BASE_URL}/umca/bbs/view.do?bbsId={bbs_id}&mId={m_id}&dataId={data_id}"

            title = a.get_text(' ', strip=True)
            title = re.sub(r'\s+', ' ', title).strip()
            if not title or len(title) < 2:
                continue

            # 브레드크럼(게시판 이름) 찾기
            board_name = '통합검색'
            for span in dl.find_all(['dd', 'p', 'span', 'em']):
                t = span.get_text(' ', strip=True)
                if '울산도시공사 >' in t or '울산광역시도시공사 >' in t:
                    # 마지막 세그먼트가 게시판 이름
                    segs = [s.strip() for s in t.split('>')]
                    if len(segs) >= 2:
                        board_name = segs[-1]
                    break

            # 날짜 파싱 (dl 텍스트 전체에서 첫 날짜)
            dl_text = dl.get_text(' ', strip=True)
            date = ''
            dm = self._DATE_RE.search(dl_text)
            if dm:
                date = f"{dm.group(1)}-{dm.group(2).zfill(2)}-{dm.group(3).zfill(2)}"

            results.append({
                'title': title,
                'date': date,
                'url': url,
                'organization': board_name,
                'number': data_id,
            })

        # 폴백: C_Cts가 아닌 요소로도 URL 수집 (제목 없이 넘어가지 않도록)
        if not results:
            for a in soup.find_all('a', href=self._URL_RE):
                href = a.get('href', '')
                m = self._URL_RE.search(href)
                if not m:
                    continue
                bbs_id, m_id, data_id = m.group(1), m.group(2), m.group(3)
                url = f"{self.BASE_URL}/umca/bbs/view.do?bbsId={bbs_id}&mId={m_id}&dataId={data_id}"
                title = a.get_text(' ', strip=True)
                if not title:
                    continue
                results.append({
                    'title': title, 'date': '', 'url': url,
                    'organization': '통합검색', 'number': data_id,
                })

        return results

    def _collect_for_keyword(self, keyword):
        collected = {}
        for page in range(1, self.MAX_PAGES + 1):
            if page > 1:
                time.sleep(self.PAGE_DELAY)
            html = self._post(keyword, page)
            items = self._parse_page(html)
            if not items:
                break
            new_cnt = 0
            for it in items:
                if it['url'] not in collected:
                    collected[it['url']] = it
                    new_cnt += 1
            if new_cnt == 0:
                break
        return collected

    def search(self, keyword='', max_pages=999, start_date=None, end_date=None):
        all_results = {}
        for kw in self.KEYWORDS:
            try:
                items = self._collect_for_keyword(kw)
                before = len(all_results)
                for u, it in items.items():
                    if u not in all_results:
                        all_results[u] = it
                added = len(all_results) - before
                print(f"  [{kw}] {len(items)}건 → +{added} (누적 {len(all_results)})",
                      flush=True)
            except Exception as e:
                print(f"  [{kw}] 에러: {str(e)[:80]}", flush=True)
            time.sleep(0.3)

        items = list(all_results.values())

        # 날짜 필터 (없는 항목은 통과)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        items = [it for it in items
                 if not it['date'] or (start_date <= it['date'][:10] <= end_date)]
        items.sort(key=lambda x: x['date'] or '', reverse=True)
        print(f"[울산도시공사] 완료: 총 {len(items)}건", flush=True)
        return items


def main():
    import urllib3
    urllib3.disable_warnings()
    c = UMCACrawler()
    t0 = time.time()
    items = c.search(start_date='2000-01-01', end_date='2099-12-31')
    print(f'{len(items)}건 / {time.time()-t0:.0f}초')
    from collections import Counter
    for k, v in Counter(it['organization'] for it in items).most_common(10):
        print(f'  {k}: {v}')


if __name__ == "__main__":
    main()
