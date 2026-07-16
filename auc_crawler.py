# -*- coding: utf-8 -*-
"""
안양도시공사 (auc) - xlsx 51행
통합검색 페이지(base/search/view)를 직접 크롤.

- searchType=BOARD 로 게시판 통합검색만 조회 (메뉴/컨텐츠 결과 제외)
- searchWord='_' (SQL LIKE 와일드카드) 로 사실상 전체 게시글 조회
- boardManagementNo+boardNo 기준 dedup (동일 글이 여러 menu 경로로 노출됨)
"""
import re
import ssl
import time
import html as html_mod
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from urllib.parse import quote
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


class _TLSAdapter(HTTPAdapter):
    """auc 서버의 옛 SSL/cipher 호환 어댑터."""
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


class AUCCrawler:
    """안양도시공사 통합검색 크롤러."""

    BASE_URL = "https://www.auc.or.kr"
    SEARCH_PATH = "/base/search/view"
    KEYWORD = "_"          # SQL LIKE wildcard → 전체 게시글에 매칭
    WORKERS = 8
    MAX_RETRIES = 4
    PAGE_SIZE = 10         # 검색결과 페이지당 10건 (사이트 고정)

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/131.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9",
        })
        self.session.mount("https://", _TLSAdapter(pool_connections=self.WORKERS,
                                                    pool_maxsize=self.WORKERS * 2))
        self.session.verify = False

    # ---------- HTTP ----------
    def _url(self, page):
        return (f"{self.BASE_URL}{self.SEARCH_PATH}"
                f"?page={page}&searchType=BOARD&searchWord={quote(self.KEYWORD)}")

    def _fetch(self, page):
        url = self._url(page)
        for attempt in range(self.MAX_RETRIES):
            try:
                r = self.session.get(url, timeout=25)
                r.raise_for_status()
                r.encoding = 'utf-8'
                return r.text
            except Exception:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1.0 * (attempt + 1))
        return ""

    # ---------- Parse ----------
    def _extract_total_pages(self, html):
        """검색결과 최대 페이지 번호."""
        pages = [int(x) for x in re.findall(
            r'page=(\d+)&amp;searchType=BOARD', html)]
        return max(pages) if pages else 1

    def _parse_page(self, html):
        """검색결과 페이지에서 li 항목들을 파싱해 dict 리스트 반환."""
        results = []
        if not html:
            return results
        soup = BeautifulSoup(html, 'lxml')
        ul = soup.select_one('ul.sch_result_page_list.type2')
        if not ul:
            return results
        for li in ul.select('li'):
            a = li.select_one('p.tit a.tit_link')
            if not a:
                continue
            href = a.get('href', '') or ''
            href = html_mod.unescape(href)
            m_bm = re.search(r'boardManagementNo=(\d+)', href)
            m_bn = re.search(r'boardNo=(\d+)', href)
            if not (m_bm and m_bn):
                continue
            bm_no = m_bm.group(1)
            b_no = m_bn.group(1)
            # 정규화된 URL (menu 부분은 dedup 위해 제거)
            url = (f"{self.BASE_URL}/base/board/read"
                   f"?boardManagementNo={bm_no}&boardNo={b_no}")

            title = a.get_text(' ', strip=True)
            title = re.sub(r'\s+', ' ', title).strip()
            if not title or len(title) < 2:
                continue

            date = ''
            date_el = li.select_one('p.tit span.date')
            if date_el:
                m = re.search(r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})',
                              date_el.get_text())
                if m:
                    date = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"

            depth = li.select_one('p.depth')
            category = ''
            if depth:
                category = re.sub(r'\s+', ' ',
                                  depth.get_text(' ', strip=True)).strip()
                category = category.replace('> ', '>').replace(' >', '>')

            results.append({
                'title': title,
                'date': date,
                'url': url,
                'organization': category or '통합검색',
                'number': f"{bm_no}-{b_no}",
            })
        return results

    # ---------- Orchestration ----------
    def search(self, keyword='', max_pages=999, start_date=None, end_date=None):
        # 1) 첫 페이지에서 총 페이지 수 파악
        first_html = self._fetch(1)
        if not first_html:
            print("[안양도시공사] 첫 페이지 조회 실패", flush=True)
            return []
        total_pages = self._extract_total_pages(first_html)
        print(f"[안양도시공사] 총 {total_pages} 페이지 수집 시작", flush=True)

        # 2) 첫 페이지 항목 수집 + 나머지 병렬 수집
        page_html = {1: first_html}
        remaining = list(range(2, total_pages + 1))

        def fetch_page(p):
            return p, self._fetch(p)

        with ThreadPoolExecutor(max_workers=self.WORKERS) as ex:
            futures = [ex.submit(fetch_page, p) for p in remaining]
            done = 0
            for fut in as_completed(futures):
                p, txt = fut.result()
                page_html[p] = txt
                done += 1
                if done % 100 == 0:
                    print(f"  … {done}/{len(remaining)} 페이지 완료",
                          flush=True)

        # 3) 파싱 및 dedup (boardManagementNo+boardNo)
        seen = {}
        for p in sorted(page_html.keys()):
            for it in self._parse_page(page_html[p]):
                if it['url'] not in seen:
                    seen[it['url']] = it

        items = list(seen.values())

        # 4) 날짜 필터
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        items = [it for it in items
                 if not it['date'] or (start_date <= it['date'][:10] <= end_date)]
        items.sort(key=lambda x: x['date'] or '', reverse=True)
        print(f"[안양도시공사] 완료: 총 {len(items)}건", flush=True)
        return items


def main():
    import urllib3
    urllib3.disable_warnings()
    c = AUCCrawler()
    t0 = time.time()
    items = c.search(start_date='2000-01-01', end_date='2099-12-31')
    print(f'{len(items)}건 / {time.time()-t0:.0f}초')
    if items:
        print('샘플 3건:')
        for it in items[:3]:
            print(f"  [{it['date']}] {it['title'][:50]} ({it['organization']})")


if __name__ == "__main__":
    main()
