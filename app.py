# -*- coding: utf-8 -*-
"""
공공기관 입찰공고 크롤러 대시보드
Flask 기반 웹 애플리케이션
"""
from flask import Flask, render_template, jsonify, request
import threading
import time
import asyncio
import re
import os


def _normalize_date(date_str: str) -> str:
    """다양한 날짜 형식을 YYYY-MM-DD로 통일"""
    if not date_str:
        return ""
    d = date_str.strip()
    # YYYY.MM.DD or YYYY/MM/DD or YYYY-MM-DD (4자리 연도)
    m = re.match(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", d)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    # YY-MM-DD or YY.MM.DD (2자리 연도)
    m = re.match(r"(\d{2})[./-](\d{1,2})[./-](\d{1,2})", d)
    if m:
        return f"20{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return d


# 크롤러 임포트
from nara_crawler import search_nara
from alio_crawler import AlioCrawler
from alio_item_crawler import AlioItemCrawler
from lh_crawler import LHCrawler
from gtdc_crawler import GTDCCrawler
from gdco_bid_crawler import GDCOBidCrawler
from gmdc_crawler import GMDCCrawler
from gndc_crawler import GNDCCrawler

from gbdc_crawler import GBDCCrawler
from ghdc_crawler import GhdcCrawler
from dudc_crawler import DUDCCrawler
from kr_crawler import KRCrawler
from ekr_crawler import EkrCrawler
from sdco_crawler import SDCOCrawler
from sh_crawler import SHCrawler
from sh_bid_crawler import SHBidCrawler
from isdc_crawler import ISDCCrawler
from isdc_notice_crawler import ISDCNoticeCrawler
from jndc_crawler import JNDCCrawler
from jbdc_crawler import JBDCCrawler
from jpdc_crawler import JPDCCrawler
from cbdc_crawler import CBDCCrawler
from cndc_crawler import CNDCCrawler
from ttdc_crawler import TTDCCrawler

app = Flask(__name__)


# 나라장터 래퍼 클래스
class NaraCrawlerWrapper:
    """나라장터 크롤러 래퍼"""
    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
        # 페이지네이션으로 모든 결과 조회 (용역 + 공사 검색)
        num_rows = max_pages * 1000  # 충분히 큰 값으로 설정
        return search_nara(keyword=keyword, num_rows=num_rows,
                          start_date_str=start_date, end_date_str=end_date,
                          search_all_types=True)  # 용역 + 공사 검색


# 비동기 크롤러 래퍼 클래스
class AsyncCrawlerWrapper:
    """비동기 크롤러 래퍼"""
    def __init__(self, crawler_class):
        self.crawler_class = crawler_class

    def search(self, keyword="", max_pages=10):
        crawler = self.crawler_class()
        # AlioCrawler.search()는 이미 동기 래퍼이므로 직접 호출
        return crawler.search(keyword, max_pages=max_pages)


# 크롤러 인스턴스
CRAWLERS = {
    "nara": {
        "name": "나라장터",
        "type": "입찰공고",
        "instance": NaraCrawlerWrapper(),
        "url": "https://www.g2b.go.kr"
    },
    "alio": {
        "name": "알리오",
        "type": "입찰공고",
        "instance": AsyncCrawlerWrapper(AlioCrawler),
        "url": "https://www.alio.go.kr"
    },
    "alio_item": {
        "name": "알리오",
        "type": "물자구매",
        "instance": AsyncCrawlerWrapper(AlioItemCrawler),
        "url": "https://www.alio.go.kr"
    },
    "lh": {
        "name": "LH 파트너몰",
        "type": "자재공법심의",
        "instance": AsyncCrawlerWrapper(LHCrawler),
        "url": "https://partner.lh.or.kr"
    },
    "gtdc": {
        "name": "강릉관광개발공사",
        "type": "입찰공고",
        "instance": GTDCCrawler(),
        "url": "https://gtdc.or.kr"
    },
    "gdco_bid": {
        "name": "강원개발공사",
        "type": "입찰공고",
        "instance": GDCOBidCrawler(),
        "url": "https://www.gdco.co.kr"
    },
    "gmdc": {
        "name": "거제해양관광개발공사",
        "type": "입찰공고",
        "instance": GMDCCrawler(),
        "url": "https://www.gmdc.co.kr"
    },
    "gndc": {
        "name": "경남개발공사",
        "type": "공고",
        "instance": GNDCCrawler(),
        "url": "https://www.gndc.co.kr"
    },
    "gbdc": {
        "name": "경상북도개발공사",
        "type": "게시판 검색",
        "instance": GBDCCrawler(),
        "url": "https://www.gbdc.co.kr"
    },
    "ghdc": {
        "name": "김해시도시개발공사",
        "type": "통합검색",
        "instance": GhdcCrawler(),
        "url": "https://ghdc.or.kr"
    },
    "dudc": {
        "name": "대구도시개발공사",
        "type": "공지사항",
        "instance": DUDCCrawler(),
        "url": "https://www.dudc.or.kr"
    },
    "kr": {
        "name": "국가철도공단",
        "type": "공지사항",
        "instance": KRCrawler(),
        "url": "https://www.kr.or.kr"
    },
    "ekr": {
        "name": "한국농어촌공사",
        "type": "공지사항",
        "instance": EkrCrawler(),
        "url": "https://www.ekr.or.kr"
    },
    "sdco": {
        "name": "새만금개발공사",
        "type": "고시/공고",
        "instance": SDCOCrawler(),
        "url": "https://www.sdco.or.kr"
    },
    "sh": {
        "name": "SH서울주택도시공사",
        "type": "공고 및 공지",
        "instance": SHCrawler(),
        "url": "https://www.i-sh.co.kr"
    },
    "sh_bid": {
        "name": "SH서울주택도시공사",
        "type": "입찰공고",
        "instance": SHBidCrawler(),
        "url": "https://www.i-sh.co.kr"
    },
    "isdc": {
        "name": "성남도시개발공사",
        "type": "통합검색",
        "instance": ISDCCrawler(),
        "url": "https://www.isdc.co.kr"
    },
    "isdc_notice": {
        "name": "성남도시개발공사",
        "type": "고시공고",
        "instance": ISDCNoticeCrawler(),
        "url": "https://www.isdc.co.kr"
    },
    "jndc": {
        "name": "전남개발공사",
        "type": "게시판",
        "instance": JNDCCrawler(),
        "url": "https://www.jndc.co.kr"
    },
    "jbdc": {
        "name": "전북개발공사",
        "type": "게시판",
        "instance": JBDCCrawler(),
        "url": "https://www.jbdc.co.kr"
    },
    "jpdc": {
        "name": "제주특별자치도개발공사",
        "type": "검색서비스",
        "instance": JPDCCrawler(),
        "url": "https://www.jpdc.co.kr"
    },
    "cbdc": {
        "name": "충북개발공사",
        "type": "공지사항",
        "instance": CBDCCrawler(),
        "url": "https://www.cbdc.co.kr"
    },
    "cndc": {
        "name": "충청남도개발공사",
        "type": "입찰공고",
        "instance": CNDCCrawler(),
        "url": "https://www.cndc.kr"
    },
    "ttdc": {
        "name": "통영관광개발공사",
        "type": "입찰정보",
        "instance": TTDCCrawler(),
        "url": "http://corp.ttdc.kr"
    },
}

# 캐시 저장소
cache = {}
cache_lock = threading.Lock()


@app.route("/")
def index():
    """메인 대시보드 페이지"""
    return render_template("dashboard.html", crawlers=CRAWLERS)


@app.route("/unified")
def unified():
    """통합 검색 페이지"""
    return render_template("unified.html", crawlers=CRAWLERS)


@app.route("/api/crawlers")
def get_crawlers():
    """크롤러 목록 조회"""
    crawler_list = []
    for key, info in CRAWLERS.items():
        crawler_list.append({
            "id": key,
            "name": info["name"],
            "type": info["type"],
            "url": info["url"]
        })
    return jsonify(crawler_list)


@app.route("/api/search/<crawler_id>")
def search(crawler_id):
    """크롤러 검색 실행"""
    if crawler_id not in CRAWLERS:
        return jsonify({"error": "크롤러를 찾을 수 없습니다"}), 404

    keyword = request.args.get("keyword", "")
    max_pages = int(request.args.get("max_pages", 1000))
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    # 캐시 키 (날짜도 포함)
    cache_key = f"{crawler_id}:{keyword}:{max_pages}:{start_date}:{end_date}"

    # 캐시 확인
    with cache_lock:
        if cache_key in cache:
            cached = cache[cache_key]
            if time.time() - cached["time"] < 300:  # 5분 캐시
                return jsonify({
                    "success": True,
                    "data": cached["data"],
                    "count": len(cached["data"]),
                    "cached": True
                })

    try:
        crawler = CRAWLERS[crawler_id]["instance"]
        # 날짜 파라미터를 직접 지원하는 크롤러
        if crawler_id in ("nara", "sh_bid") and start_date and end_date:
            results = crawler.search(keyword, max_pages=max_pages,
                                    start_date=start_date, end_date=end_date)
        else:
            results = crawler.search(keyword, max_pages=max_pages)

        # 다른 크롤러는 결과에서 날짜 필터링
        if crawler_id != "nara" and start_date and end_date:
            filtered = []
            for r in results:
                date = r.get("date", "")
                if date:
                    normalized = _normalize_date(date)
                    if normalized and start_date <= normalized <= end_date:
                        filtered.append(r)
            results = filtered

        # 캐시 저장
        with cache_lock:
            cache[cache_key] = {
                "data": results,
                "time": time.time()
            }

        return jsonify({
            "success": True,
            "data": results,
            "count": len(results),
            "cached": False
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/stats")
def get_stats():
    """전체 통계 조회"""
    stats = {
        "total_crawlers": len(CRAWLERS),
        "cached_searches": len(cache),
        "crawlers": []
    }

    for key, info in CRAWLERS.items():
        stats["crawlers"].append({
            "id": key,
            "name": f"{info['name']} ({info['type']})"
        })

    return jsonify(stats)


@app.route("/lh/detail/<int:idx>")
def lh_detail_redirect(idx):
    """LH 파트너몰 상세 페이지로 POST 리다이렉트"""
    return f'''
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><title>LH 상세페이지 이동중...</title></head>
    <body>
        <form id="lhForm" method="POST" action="https://partner.lh.or.kr/deliberate/deliberate_detail.asp">
            <input type="hidden" name="re_idx" value="{idx}">
        </form>
        <script>document.getElementById('lhForm').submit();</script>
        <noscript><p>JavaScript가 필요합니다. <a href="https://partner.lh.or.kr/deliberate/deliberate.asp">메인 페이지로 이동</a></p></noscript>
    </body>
    </html>
    '''


@app.route("/api/search_all")
def search_all():
    """모든 크롤러 통합 검색"""
    keyword = request.args.get("keyword", "")
    max_pages = int(request.args.get("max_pages", 1000))

    if not keyword:
        return jsonify({"error": "검색어를 입력해주세요"}), 400

    results = {}
    errors = {}

    def search_crawler(crawler_id, info):
        """개별 크롤러 검색 (스레드용)"""
        try:
            crawler = info["instance"]
            data = crawler.search(keyword, max_pages=max_pages)
            return crawler_id, data, None
        except Exception as e:
            return crawler_id, [], str(e)

    # 멀티스레드로 병렬 검색
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(CRAWLERS)) as executor:
        futures = {
            executor.submit(search_crawler, cid, info): cid
            for cid, info in CRAWLERS.items()
        }

        for future in concurrent.futures.as_completed(futures):
            crawler_id, data, error = future.result()
            if error:
                errors[crawler_id] = error
                results[crawler_id] = []
            else:
                results[crawler_id] = data

    # 결과 집계
    total_count = sum(len(v) for v in results.values())

    return jsonify({
        "success": True,
        "keyword": keyword,
        "results": results,
        "summary": {
            crawler_id: {
                "name": f"{CRAWLERS[crawler_id]['name']} ({CRAWLERS[crawler_id]['type']})",
                "count": len(data),
                "error": errors.get(crawler_id)
            }
            for crawler_id, data in results.items()
        },
        "total_count": total_count,
        "errors": errors
    })


def warmup_cookies():
    """서버 시작 시 알리오 쿠키 미리 획득"""
    import threading
    def _warmup():
        try:
            print("[웜업] 알리오 쿠키 획득 중...")
            crawler = AlioCrawler()
            crawler.search("", max_pages=1)  # 빈 검색으로 쿠키만 획득
            print("[웜업] 알리오 쿠키 획득 완료!")
        except Exception as e:
            print(f"[웜업] 실패: {e}")

    # 백그라운드에서 실행
    threading.Thread(target=_warmup, daemon=True).start()


if __name__ == "__main__":
    warmup_cookies()  # 서버 시작 시 쿠키 미리 획득
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
