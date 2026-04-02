# -*- coding: utf-8 -*-
"""18개 크롤러 검증 스크립트 - _fetch_page로 total_count 직접 추출 + 사이트 독립 검증"""
import sys
import os
import time
import re
import math
import warnings
import importlib
import requests
from bs4 import BeautifulSoup

os.chdir("/Users/teramime/Documents/project_16")
sys.path.insert(0, "/Users/teramime/Documents/project_16")

warnings.filterwarnings("ignore")
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

CRAWLERS = [
    ("osan_gosi_crawler", "OsanGosiCrawler", "오산시", "고시공고"),
    ("yongin_committee_crawler", "YonginCommitteeCrawler", "용인시", "공법선정위"),
    ("yongin_bid_crawler", "YonginBidCrawler", "용인시", "입찰공고"),
    ("icheon_bid_crawler", "IcheonBidCrawler", "이천시", "입찰공고"),
    ("icheon_gosi_crawler", "IcheonGosiCrawler", "이천시", "고시공고"),
    ("uiwang_bid_crawler", "UiwangBidCrawler", "의왕시", "입찰정보"),
    ("uiwang_gosi_crawler", "UiwangGosiCrawler", "의왕시", "고시공고"),
    ("uijeongbu_gosi_crawler", "UijeongbuGosiCrawler", "의정부시", "고시공고"),
    ("uijeongbu_bid_crawler", "UijeongbuBidCrawler", "의정부시", "입찰공고"),
    ("paju_crawler", "PajuCrawler", "파주시", "고시공고"),
    ("pyeongtaek_gosi_crawler", "PyeongtaekGosiCrawler", "평택시", "고시공고"),
    ("pyeongtaek_bid_crawler", "PyeongtaekBidCrawler", "평택시", "입찰공고"),
    ("pocheon_bid_crawler", "PocheonBidCrawler", "포천시", "입찰공고"),
    ("pocheon_gosi_crawler", "PocheonGosiCrawler", "포천시", "고시공고"),
    ("hanam_gosi_crawler", "HanamGosiCrawler", "하남시", "고시공고"),
    ("hanam_bid_crawler", "HanamBidCrawler", "하남시", "입찰공고"),
    ("hwaseong_gosi_crawler", "HwaseongGosiCrawler", "화성시", "고시공고"),
    ("hwaseong_bid_crawler", "HwaseongBidCrawler", "화성시", "입찰공고"),
]

def new_session(verify=False):
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"})
    s.verify = verify
    return s

# ---- Site fetchers (independent from crawlers) ----

def site_osan_gosi(keyword):
    """POST, total from first row number"""
    s = new_session()
    data = {"page": "1", "seCode": "01", "recordCountPerPage": "10"}
    if keyword:
        data["searchType"] = "NOT_ANCMT_SJ"
        data["searchTxt"] = keyword
    r = s.post("https://www.osan.go.kr/portal/saeol/gosi/list.do?mId=0302010000", data=data, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")
    rows = soup.select("table.bod_list tbody tr")
    for row in rows:
        num_td = row.select_one("td.list_num")
        if num_td:
            n = num_td.get_text(strip=True)
            if n.isdigit():
                return int(n)
    return 0

def site_yongin_committee(keyword):
    s = new_session()
    params = {"q_bbsCode": "1156", "q_currPage": "1", "q_rowPerPage": "10"}
    if keyword:
        params["q_searchKeyType"] = "sj___1156"
        params["q_searchVal"] = keyword
    r = s.get("http://www.yongin.go.kr/user/bbs/BD_selectBbsList.do", params=params, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")
    m = re.search(r'총\s*(\d[\d,]*)\s*건', soup.get_text())
    if m:
        return int(m.group(1).replace(",", ""))
    rows = soup.select("table tbody tr")
    for row in rows:
        tds = row.find_all("td")
        if tds:
            n = tds[0].get_text(strip=True)
            if n.isdigit():
                return int(n)
    return 0

def site_yongin_bid(keyword):
    s = new_session()
    # Need to init session with JSP first
    try:
        s.get("https://eminwon.yongin.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp?not_ancmt_se_code=02&homepage_pbs_yn=Y&subCheck=Y&list_gubun=A", timeout=15)
    except:
        pass
    data = {
        "pageIndex": "1", "jndinm": "OfrNotAncmtEJB", "context": "NTIS",
        "method": "selectListOfrNotAncmt", "methodnm": "selectListOfrNotAncmtHomepage",
        "not_ancmt_se_code": "02", "homepage_pbs_yn": "Y", "subCheck": "Y",
        "ofr_pageSize": "10", "countYn": "Y", "not_ancmt_mgt_no": "",
        "list_gubun": "A",
    }
    if keyword:
        data["not_ancmt_sj"] = keyword
    r = s.post("https://eminwon.yongin.go.kr/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do", data=data, timeout=15)
    r.encoding = "utf-8"
    m = re.search(r'전체게시물\s*:\s*(\d[\d,]*)\s*개', r.text)
    return int(m.group(1).replace(",", "")) if m else 0

def site_icheon_bid(keyword):
    s = new_session()
    data = {"page": "1", "pageSize": "10", "seCode": "02"}
    if keyword:
        data["searchType"] = "NOT_ANCMT_SJ"
        data["searchTxt"] = keyword
    r = s.post("https://www.icheon.go.kr/portal/saeol/gosi/list.do?mid=0402040000", data=data, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")
    rows = soup.select("table.bod_list tbody tr")
    for row in rows:
        num_td = row.select_one("td.list_num")
        if num_td:
            n = num_td.get_text(strip=True)
            if n.isdigit():
                return int(n)
    return 0

def site_icheon_gosi(keyword):
    s = new_session()
    data = {"page": "1", "pageSize": "10", "seCode": "04"}
    if keyword:
        data["searchType"] = "NOT_ANCMT_SJ"
        data["searchTxt"] = keyword
    r = s.post("https://www.icheon.go.kr/portal/saeol/gosi/list.do?seCode=04&mid=0402020000", data=data, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")
    rows = soup.select("table.bod_list tbody tr")
    for row in rows:
        num_td = row.select_one("td.list_num")
        if num_td:
            n = num_td.get_text(strip=True)
            if n.isdigit():
                return int(n)
    return 0

def site_uiwang_bid(keyword):
    s = new_session()
    try:
        s.get("https://eminwon.uiwang.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp?not_ancmt_se_code=02&list_gubun=A&epcCheck=Y", timeout=15)
    except:
        pass
    data = {
        "pageIndex": "1", "jndinm": "OfrNotAncmtEJB", "context": "NTIS",
        "method": "selectListOfrNotAncmt", "methodnm": "selectListOfrNotAncmtHomepage",
        "not_ancmt_se_code": "02", "homepage_pbs_yn": "Y", "subCheck": "N",
        "ofr_pageSize": "10", "countYn": "Y", "list_gubun": "A", "epcCheck": "Y",
    }
    if keyword:
        data["not_ancmt_sj"] = keyword
    r = s.post("https://eminwon.uiwang.go.kr/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do", data=data, timeout=15)
    r.encoding = "utf-8"
    m = re.search(r'전체게시물\s*:\s*(\d[\d,]*)\s*개', r.text)
    return int(m.group(1).replace(",", "")) if m else 0

def site_uiwang_gosi(keyword):
    s = new_session()
    try:
        s.get("https://eminwon.uiwang.go.kr/emwp/jsp/ofr/OfrNotAncmtL.jsp?not_ancmt_se_code=01,04,06&homepage_pbs_yn=Y&subCheck=Y&list_gubun=A", timeout=15)
    except:
        pass
    data = {
        "pageIndex": "1", "jndinm": "OfrNotAncmtEJB", "context": "NTIS",
        "method": "selectListOfrNotAncmt", "methodnm": "selectListOfrNotAncmtHomepage",
        "not_ancmt_se_code": "01,04,06", "homepage_pbs_yn": "Y", "subCheck": "Y",
        "ofr_pageSize": "10", "countYn": "Y", "list_gubun": "A",
    }
    if keyword:
        data["not_ancmt_sj"] = keyword
    r = s.post("https://eminwon.uiwang.go.kr/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do", data=data, timeout=15)
    r.encoding = "utf-8"
    m = re.search(r'전체게시물\s*:\s*(\d[\d,]*)\s*개', r.text)
    return int(m.group(1).replace(",", "")) if m else 0

def site_uijeongbu_gosi(keyword):
    """GET based, total from goPage() max"""
    s = new_session()
    params = {"seCode": "01", "mId": "0301040000", "pageIndex": "1"}
    if keyword:
        params["searchType"] = "NOT_ANCMT_SJ"
        params["searchTxt"] = keyword
    r = s.get("https://www.ui4u.go.kr/portal/saeol/gosiList.do", params=params, timeout=15)
    r.encoding = "utf-8"
    pages = re.findall(r'goPage\((\d+)\)', r.text)
    if pages:
        return max(int(p) for p in pages) * 100  # PAGE_SIZE=100 in crawler
    return 0

def site_uijeongbu_bid(keyword):
    s = new_session()
    params = {"seCode": "02", "mId": "0301090000", "pageIndex": "1"}
    if keyword:
        params["searchType"] = "NOT_ANCMT_SJ"
        params["searchTxt"] = keyword
    r = s.get("https://www.ui4u.go.kr/portal/saeol/gosiList.do", params=params, timeout=15)
    r.encoding = "utf-8"
    pages = re.findall(r'goPage\((\d+)\)', r.text)
    if pages:
        return max(int(p) for p in pages) * 100
    return 0

def site_paju(keyword):
    s = new_session()
    params = {"bbsCd": "1022", "q_ctgCd": "4063", "q_currPage": "1", "q_rowPerPage": "10"}
    if keyword:
        params["q_searchKey"] = "sj"
        params["q_searchVal"] = keyword
    r = s.get("https://www.paju.go.kr/user/board/BD_board.list.do", params=params, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")
    m = re.search(r'총\s*(\d[\d,]*)\s*건', soup.get_text())
    if m:
        return int(m.group(1).replace(",", ""))
    rows = soup.select("table tbody tr")
    for row in rows:
        tds = row.find_all("td")
        if tds:
            n = tds[0].get_text(strip=True)
            if n.isdigit():
                return int(n)
    return 0

def site_pyeongtaek_gosi(keyword):
    """GET based, total from goPage() max"""
    s = new_session()
    params = {"mid": "0401020100", "seCode": "01", "pageIndex": "1"}
    if keyword:
        params["searchType"] = "NOT_ANCMT_SJ"
        params["searchTxt"] = keyword
    r = s.get("https://www.pyeongtaek.go.kr/pyeongtaek/saeol/gosi/list.do", params=params, timeout=15)
    r.encoding = "utf-8"
    pages = re.findall(r'goPage\((\d+)\)', r.text)
    if pages:
        return max(int(p) for p in pages) * 100
    return 0

def site_pyeongtaek_bid(keyword):
    s = new_session()
    params = {"mid": "0401030000", "seCode": "02", "pageIndex": "1"}
    if keyword:
        params["searchType"] = "NOT_ANCMT_SJ"
        params["searchTxt"] = keyword
    r = s.get("https://www.pyeongtaek.go.kr/pyeongtaek/saeol/gosi/list.do", params=params, timeout=15)
    r.encoding = "utf-8"
    pages = re.findall(r'goPage\((\d+)\)', r.text)
    if pages:
        return max(int(p) for p in pages) * 100
    return 0

def site_pocheon_bid(keyword):
    s = new_session()
    params = {"key": "12644", "notAncmtSeCode": "02", "pageIndex": "1"}
    if keyword:
        params["searchCnd"] = "notAncmtSj"
        params["searchKrwd"] = keyword
    r = s.get("https://www.pocheon.go.kr/www/selectEminwonList.do", params=params, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")
    m = re.search(r'총\s*(\d[\d,]*)\s*건', soup.get_text())
    if m:
        return int(m.group(1).replace(",", ""))
    rows = soup.select("table tbody tr")
    for row in rows:
        tds = row.find_all("td")
        if tds:
            n = tds[0].get_text(strip=True)
            if n.isdigit():
                return int(n)
    return 0

def site_pocheon_gosi(keyword):
    s = new_session()
    params = {"key": "12563", "notAncmtSeCode": "01", "pageIndex": "1"}
    if keyword:
        params["searchCnd"] = "notAncmtSj"
        params["searchKrwd"] = keyword
    r = s.get("https://www.pocheon.go.kr/www/selectEminwonList.do", params=params, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")
    m = re.search(r'총\s*(\d[\d,]*)\s*건', soup.get_text())
    if m:
        return int(m.group(1).replace(",", ""))
    rows = soup.select("table tbody tr")
    for row in rows:
        tds = row.find_all("td")
        if tds:
            n = tds[0].get_text(strip=True)
            if n.isdigit():
                return int(n)
    return 0

def site_hanam_gosi(keyword):
    s = new_session()
    params = {"key": "171", "not_ancmt_se_code": "01,04", "pageIndex": "1"}
    if keyword:
        params["searchCnd"] = "SJ"
        params["searchKrwd"] = keyword
    r = s.get("https://www.hanam.go.kr/www/selectGosiList.do", params=params, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")
    m = re.search(r'총\s*(\d[\d,]*)\s*건', soup.get_text())
    if m:
        return int(m.group(1).replace(",", ""))
    rows = soup.select("table tbody tr")
    for row in rows:
        tds = row.find_all("td")
        if tds:
            n = tds[0].get_text(strip=True)
            if n.isdigit():
                return int(n)
    return 0

def site_hanam_bid(keyword):
    s = new_session()
    params = {"key": "175", "not_ancmt_se_code": "02", "pageIndex": "1"}
    if keyword:
        params["searchCnd"] = "SJ"
        params["searchKrwd"] = keyword
    r = s.get("https://www.hanam.go.kr/www/selectGosiList.do", params=params, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")
    m = re.search(r'총\s*(\d[\d,]*)\s*건', soup.get_text())
    if m:
        return int(m.group(1).replace(",", ""))
    rows = soup.select("table tbody tr")
    for row in rows:
        tds = row.find_all("td")
        if tds:
            n = tds[0].get_text(strip=True)
            if n.isdigit():
                return int(n)
    return 0

def site_hwaseong_gosi(keyword):
    s = new_session()
    params = {"q_notAncmtSeCode": "04", "q_currPage": "1", "q_rowPerPage": "10"}
    if keyword:
        params["q_sv"] = keyword
    r = s.get("https://www.hscity.go.kr/www/gosi/BD_selectGosiList.do", params=params, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")
    m = re.search(r'총\s*(\d[\d,]*)\s*건', soup.get_text())
    if m:
        return int(m.group(1).replace(",", ""))
    rows = soup.select("table tbody tr")
    for row in rows:
        tds = row.find_all("td")
        if tds:
            n = tds[0].get_text(strip=True)
            if n.isdigit():
                return int(n)
    return 0

def site_hwaseong_bid(keyword):
    s = new_session()
    params = {"q_notAncmtSeCode": "02", "q_currPage": "1", "q_rowPerPage": "10"}
    if keyword:
        params["q_sv"] = keyword
    r = s.get("https://www.hscity.go.kr/www/gosi/BD_bidding.do", params=params, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "lxml")
    m = re.search(r'총\s*(\d[\d,]*)\s*건', soup.get_text())
    if m:
        return int(m.group(1).replace(",", ""))
    rows = soup.select("table tbody tr")
    for row in rows:
        tds = row.find_all("td")
        if tds:
            n = tds[0].get_text(strip=True)
            if n.isdigit():
                return int(n)
    return 0

SITE_FETCHERS = [
    site_osan_gosi,
    site_yongin_committee,
    site_yongin_bid,
    site_icheon_bid,
    site_icheon_gosi,
    site_uiwang_bid,
    site_uiwang_gosi,
    site_uijeongbu_gosi,
    site_uijeongbu_bid,
    site_paju,
    site_pyeongtaek_gosi,
    site_pyeongtaek_bid,
    site_pocheon_bid,
    site_pocheon_gosi,
    site_hanam_gosi,
    site_hanam_bid,
    site_hwaseong_gosi,
    site_hwaseong_bid,
]

def main():
    print(f"| {'#':>2} | {'기관':<8} | {'게시판':<10} | {'크롤러공고':>10} | {'사이트공고':>10} | {'일치':^4} | {'크롤러용역':>10} | {'사이트용역':>10} | {'일치':^4} | {'속도(공고)':>10} | {'날짜':<20} |")
    print("|" + "-"*4 + "|" + "-"*10 + "|" + "-"*12 + "|" + "-"*12 + "|" + "-"*12 + "|" + "-"*6 + "|" + "-"*12 + "|" + "-"*12 + "|" + "-"*6 + "|" + "-"*12 + "|" + "-"*22 + "|")

    for i, (mod_name, cls_name, org, board) in enumerate(CRAWLERS):
        idx = i + 1
        site_fetcher = SITE_FETCHERS[i]
        try:
            # Load crawler
            mod = importlib.import_module(mod_name)
            cls = getattr(mod, cls_name)
            crawler = cls()

            # 1) Crawler "공고" (keyword search, page 1)
            t0 = time.time()
            items_gongo, total_gongo = crawler._fetch_page("공고", 1)
            elapsed = time.time() - t0

            # Date check on first 3 items
            dates = [it.get("date", "") for it in items_gongo[:3]]
            date_ok = all(DATE_RE.match(d) for d in dates if d) and len([d for d in dates if d]) > 0
            date_str = "OK" if date_ok else f"FAIL{dates}"

            # 2) Crawler "용역" (keyword search, page 1)
            items_yongyeok, total_yongyeok = crawler._fetch_page("용역", 1)

            # 3) Independent site verification
            try:
                site_gongo = site_fetcher("공고")
            except Exception as e:
                site_gongo = f"ERR({e})"

            try:
                site_yongyeok = site_fetcher("용역")
            except Exception as e:
                site_yongyeok = f"ERR({e})"

            match_g = "O" if str(total_gongo) == str(site_gongo) else "X"
            match_y = "O" if str(total_yongyeok) == str(site_yongyeok) else "X"

            print(f"| {idx:>2} | {org:<8} | {board:<10} | {str(total_gongo):>10} | {str(site_gongo):>10} | {match_g:^4} | {str(total_yongyeok):>10} | {str(site_yongyeok):>10} | {match_y:^4} | {elapsed:>8.2f}s  | {date_str:<20} |")
            sys.stdout.flush()

        except Exception as e:
            import traceback
            print(f"| {idx:>2} | {org:<8} | {board:<10} | ERROR: {e}")
            traceback.print_exc()
            sys.stdout.flush()

    print("=" * 140)
    print("Done.")

if __name__ == "__main__":
    main()
