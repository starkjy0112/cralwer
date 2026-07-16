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
from gmcc_crawler import GMCCCrawler
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
from gcuc_crawler import GCUCCrawler
from gh_crawler import GHCrawler
from gys_crawler import GYSCrawler
from guriuc_crawler import GURIUCCrawler
from gunpouc_crawler import GUNPOUCCrawler
from ncuc_crawler import NCUCCrawler
from djuc_crawler import DJUCCrawler
from dcco_crawler import DCCOCrawler
from bmc_crawler import BMCCrawler
from best_crawler import BESTCrawler
from suwonudc_crawler import SUWONUDCCrawler
from shsi_crawler import SHSICrawler
from ansanuc_crawler import ANSANUCCrawler
from auc_crawler import AUCCrawler
from yjuc_crawler import YJUCCrawler
from yuc_crawler import YUCCrawler
from uuc_crawler import UUCCrawler
from uiuc_crawler import UIUCCrawler
from umca_crawler import UMCACrawler
from ih_crawler import IHCrawler
from cuc_crawler import CUCCrawler
from puc_crawler import PUCCrawler
from pcuc_crawler import PCUCCrawler
from huic_crawler import HUICCrawler
from hu_crawler import HUCrawler
from cuc_bid_crawler import CUCBidCrawler
from hu_notice_crawler import HUNoticeCrawler
from seoul_bid_crawler import SeoulBidCrawler
from seoul_cis_crawler import SeoulCISCrawler
from seoul_contract_crawler import SeoulContractCrawler
from gwangju_crawler import GwangjuCrawler
from daegu_crawler import DaeguCrawler
from daejeon_gosi_crawler import DaejeonGosiCrawler
from daejeon_all_crawler import DaejeonAllCrawler
from busan_notice_crawler import BusanNoticeCrawler
from busan_gosi_crawler import BusanGosiCrawler
from ulsan_crawler import UlsanCrawler
from incheon_crawler import IncheonCrawler
from gangwon_crawler import GangwonCrawler
from sejong_bid_crawler import SejongBidCrawler
from sejong_general_crawler import SejongGeneralCrawler
from sejong_notice_crawler import SejongNoticeCrawler
from jeonbuk_crawler import JeonbukCrawler
from jeonbuk_other_crawler import JeonbukOtherCrawler
from jeju_crawler import JejuCrawler
from gg_crawler import GGCrawler
from gsnd_notice_crawler import GSNDNoticeCrawler
from gsnd_gosi_crawler import GSNDGosiCrawler
from gb_notice_crawler import GBNoticeCrawler
from gb_gosi_crawler import GBGosiCrawler
from jeonnam_crawler import JeonnamNotCrawler
from jeonnam_bid_crawler import JeonnamBidCrawler
from chungnam_crawler import ChungnamCrawler
from chungbuk_crawler import ChungbukCrawler

# 경기도 시군 크롤러 (79-132)
from gapyeong_notice_crawler import GapyeongNoticeCrawler
from gapyeong_gosi_crawler import GapyeongGosiCrawler
from gwacheon_bid_crawler import GwacheonBidCrawler
from gwacheon_gosi_crawler import GwacheonGosiCrawler
from gwangmyeong_bid_crawler import GwangmyeongBidCrawler
from gwangmyeong_gosi_crawler import GwangmyeongGosiCrawler
from gjcity_gosi_crawler import GjcityGosiCrawler
from gjcity_bid_crawler import GjcityBidCrawler
from guri_notice_crawler import GuriNoticeCrawler
from guri_bid_crawler import GuriBidCrawler
from gunpo_gosi_crawler import GunpoGosiCrawler
from gunpo_bid_crawler import GunpoBidCrawler
from goyang_bid_crawler import GoyangBidCrawler
from gimpo_gosi_crawler import GimpoGosiCrawler
from gimpo_bid_crawler import GimpoBidCrawler
from namyangju_crawler import NamyangjuCrawler
from dongducheon_gosi_crawler import DongducheonGosiCrawler
from dongducheon_bid_crawler import DongducheonBidCrawler
from bucheon_bid_crawler import BucheonBidCrawler
from seongnam_bid_crawler import SeongnamBidCrawler
from suwon_crawler import SuwonCrawler
from siheung_bid_crawler import SiheungBidCrawler
from siheung_gosi_crawler import SiheungGosiCrawler
from ansan_gosi_crawler import AnsanGosiCrawler
from ansan_bid_crawler import AnsanBidCrawler
from anseong_bid_crawler import AnseongBidCrawler
from anseong_gosi_crawler import AnseongGosiCrawler
from anyang_bid_crawler import AnyangBidCrawler
from anyang_gosi_crawler import AnyangGosiCrawler
from yangju_bid_crawler import YangjuBidCrawler
from yangju_notice_crawler import YangjuNoticeCrawler
from yangpyeong_crawler import YangpyeongCrawler
from yeoju_gosi_crawler import YeojuGosiCrawler
from yeoju_bid_crawler import YeojuBidCrawler
from yeoncheon_crawler import YeoncheonCrawler
from osan_bid_crawler import OsanBidCrawler
from osan_gosi_crawler import OsanGosiCrawler
from yongin_committee_crawler import YonginCommitteeCrawler
from yongin_bid_crawler import YonginBidCrawler
from icheon_bid_crawler import IcheonBidCrawler
from icheon_gosi_crawler import IcheonGosiCrawler
from uiwang_bid_crawler import UiwangBidCrawler
from uiwang_gosi_crawler import UiwangGosiCrawler
from uijeongbu_gosi_crawler import UijeongbuGosiCrawler
from uijeongbu_bid_crawler import UijeongbuBidCrawler
from paju_crawler import PajuCrawler
from pyeongtaek_gosi_crawler import PyeongtaekGosiCrawler
from pyeongtaek_bid_crawler import PyeongtaekBidCrawler
from pocheon_bid_crawler import PocheonBidCrawler
from pocheon_gosi_crawler import PocheonGosiCrawler
from hanam_gosi_crawler import HanamGosiCrawler
from hanam_bid_crawler import HanamBidCrawler
from hwaseong_gosi_crawler import HwaseongGosiCrawler
from hwaseong_bid_crawler import HwaseongBidCrawler

# 서울특별시 자치구 크롤러 (15개)
from mapo_crawler import MapoCrawler
from sdm_crawler import SdmCrawler
from seocho_crawler import SeochoCrawler
from seongdong_crawler import SeongdongCrawler
from seongbuk_crawler import SeongbukCrawler
from songpa_gosi_crawler import SongpaGosiCrawler
from songpa_bid_crawler import SongpaBidCrawler
from yangcheon_crawler import YangcheonCrawler
from ydp_crawler import YdpCrawler
from yongsan_crawler import YongsanCrawler
from eunpyeong_gosi_crawler import EunpyeongGosiCrawler
from eunpyeong_bid_crawler import EunpyeongBidCrawler
from jongno_crawler import JongnoCrawler
from junggu_crawler import JungguCrawler
from jungnang_crawler import JungnangCrawler

# 강원도 시군 크롤러 (133-148)
from gangneung_gosi_crawler import GangneungGosiCrawler
from gangneung_bid_crawler import GangneungBidCrawler
from goseong_gw_crawler import GoseongGwCrawler
from donghae_gosi_crawler import DonghaeGosiCrawler
from donghae_bid_crawler import DonghaeBidCrawler
from samcheok_gosi_crawler import SamcheokGosiCrawler
from samcheok_bid_crawler import SamcheokBidCrawler
from sokcho_gosi_crawler import SokchoGosiCrawler
from sokcho_notice_crawler import SokchoNoticeCrawler
from yanggu_crawler import YangguCrawler
from yangyang_bid_crawler import YangyangBidCrawler
from yangyang_gosi_crawler import YangyangGosiCrawler
from yeongwol_crawler import YeongwolCrawler
from wonju_gosi_crawler import WonjuGosiCrawler
from wonju_notice_crawler import WonjuNoticeCrawler
from inje_gosi_crawler import InjeGosiCrawler
from inje_bid_crawler import InjeBidCrawler
from jeongseon_gosi_crawler import JeongseonGosiCrawler
from jeongseon_bid_crawler import JeongseonBidCrawler
from cheorwon_gosi_crawler import CheorwonGosiCrawler
from cheorwon_bid_crawler import CheorwonBidCrawler
from chuncheon_gosi_crawler import ChuncheonGosiCrawler
from taebaek_gosi_crawler import TaebaekGosiCrawler
from taebaek_bid_crawler import TaebaekBidCrawler
from pyeongchang_crawler import PyeongchangCrawler
from hapcheon_crawler import HapcheonCrawler
from hwacheon_bid_crawler import HwacheonBidCrawler
from hwacheon_gosi_crawler import HwacheonGosiCrawler
from hongcheon_gosi_crawler import HongcheonGosiCrawler
from hongcheon_bid_crawler import HongcheonBidCrawler
from hoengseong_gosi_crawler import HoengseongGosiCrawler
from hoengseong_bid_crawler import HoengseongBidCrawler
from goesan_gosi_crawler import GoesanGosiCrawler
from goesan_bid_crawler import GoesanBidCrawler
from danyang_gosi_crawler import DanyangGosiCrawler
from danyang_bid_crawler import DanyangBidCrawler
from boeun_gosi_crawler import BoeunGosiCrawler
from boeun_bid_crawler import BoeunBidCrawler
from yeongdong_crawler import YeongdongCrawler
from okcheon_gosi_crawler import OkcheonGosiCrawler
from okcheon_notice_crawler import OkcheonNoticeCrawler
from eumseong_crawler import EumseongCrawler
from jecheon_gosi_crawler import JecheonGosiCrawler
from jecheon_bid_crawler import JecheonBidCrawler
from jeungpyeong_gosi_crawler import JeungpyeongGosiCrawler
from jeungpyeong_bid_crawler import JeungpyeongBidCrawler
from jincheon_bid_crawler import JincheonBidCrawler
from jincheon_gosi_crawler import JincheonGosiCrawler
from cheongju_crawler import CheongjuCrawler
from chungju_crawler import ChungjuCrawler

# 충청남도 시군 크롤러 (15개)
from yesan_bid_crawler import YesanBidCrawler
from cheonan_gosi_crawler import CheonanGosiCrawler
from cheonan_bid_crawler import CheonanBidCrawler
from cheongyang_crawler import CheongyangCrawler
from taean_bid_crawler import TaeanBidCrawler
from taean_gosi_crawler import TaeanGosiCrawler
from hongseong_crawler import HongseongCrawler
from gyeryong_crawler import GyeryongCrawler
from gongju_bid_crawler import GongjuBidCrawler
from gongju_gosi_crawler import GongjuGosiCrawler
from geumsan_crawler import GeumsanCrawler
from nonsan_crawler import NonsanCrawler
from dangjin_crawler import DangjinCrawler
from buyeo_gosi_crawler import BuyeoGosiCrawler
from buyeo_bid_crawler import BuyeoBidCrawler
from boryeong_crawler import BoryeongCrawler
from seosan_gosi_crawler import SeosanGosiCrawler
from seosan_bid_crawler import SeosanBidCrawler
from seocheon_bid_crawler import SeocheonBidCrawler
from seocheon_gosi_crawler import SeocheonGosiCrawler
from asan_bid_crawler import AsanBidCrawler
from asan_gosi_crawler import AsanGosiCrawler
from yesan_gosi_crawler import YesanGosiCrawler

# 경상남도 시군 크롤러 (21개)
from geoje_crawler import GeojeCrawler
from geochang_crawler import GeochangCrawler
from goseong_gn_crawler import GoseongGnCrawler
from gimhae_crawler import GimhaeCrawler
from namhae_crawler import NamhaeCrawler
from miryang_crawler import MiryangCrawler
from sacheon_crawler import SacheonCrawler
from sancheong_crawler import SancheongCrawler
from yangsan_gosi_crawler import YangsanGosiCrawler
from yangsan_bid_crawler import YangsanBidCrawler
from uiryeong_gosi_crawler import UiryeongGosiCrawler
from uiryeong_bid_crawler import UiryeongBidCrawler
from jinju_crawler import JinjuCrawler
from changnyeong_gosi_crawler import ChangnyeongGosiCrawler
from changnyeong_bid_crawler import ChangnyeongBidCrawler
from changwon_gosi_crawler import ChangwonGosiCrawler
from changwon_bid_crawler import ChangwonBidCrawler
from tongyeong_crawler import TongyeongCrawler
from hadong_crawler import HadongCrawler
from haman_crawler import HamanCrawler
from hamyang_crawler import HamyangCrawler

# 경상북도 시군 크롤러 (40개)
from gyeongsan_gosi_crawler import GyeongsanGosiCrawler
from gyeongsan_bid_crawler import GyeongsanBidCrawler
from gyeongju_gosi_crawler import GyeongjuGosiCrawler
from gyeongju_bid_crawler import GyeongjuBidCrawler
from goryeong_crawler import GoryeongCrawler
from gumi_gosi_crawler import GumiGosiCrawler
from gumi_bid_crawler import GumiBidCrawler
from gunwi_gosi_crawler import GunwiGosiCrawler
from gunwi_bid_crawler import GunwiBidCrawler
from gimcheon_gosi_crawler import GimcheonGosiCrawler
from gimcheon_bid_crawler import GimcheonBidCrawler
from mungyeong_gosi_crawler import MungyeongGosiCrawler
from mungyeong_bid_crawler import MungyeongBidCrawler
from bonghwa_gosi_crawler import BonghwaGosiCrawler
from bonghwa_bid_crawler import BonghwaBidCrawler
from sangju_crawler import SangjuCrawler
from seongju_crawler import SeongjuCrawler
from andong_gosi_crawler import AndongGosiCrawler
from andong_bid_crawler import AndongBidCrawler
from yeongdeok_gosi_crawler import YeongdeokGosiCrawler
from yeongdeok_bid_crawler import YeongdeokBidCrawler
from yeongyang_crawler import YeongyangCrawler
from yeongju_gosi_crawler import YeongjuGosiCrawler
from yeongju_bid_crawler import YeongjuBidCrawler
from yeongcheon_gosi_crawler import YeongcheonGosiCrawler
from yeongcheon_bid_crawler import YeongcheonBidCrawler
from yecheon_gosi_crawler import YecheonGosiCrawler
from yecheon_bid_crawler import YecheonBidCrawler
from ulleung_gosi_crawler import UlleungGosiCrawler
from ulleung_bid_crawler import UlleungBidCrawler
from uljin_crawler import UljinCrawler
from uiseong_bid_crawler import UiseongBidCrawler
from uiseong_gosi_crawler import UiseongGosiCrawler
from cheongdo_gosi_crawler import CheongdoGosiCrawler
from cheongdo_bid_crawler import CheongdoBidCrawler
from cheongsong_gosi_crawler import CheongsongGosiCrawler
from cheongsong_bid_crawler import CheongsongBidCrawler
from chilgok_crawler import ChilgokCrawler
from pohang_gosi_crawler import PohangGosiCrawler
from pohang_bid_crawler import PohangBidCrawler

# 전라북도 시군 크롤러 (14개)
from gochang_crawler import GochangCrawler
from gunsan_crawler import GunsanCrawler
from gimje_crawler import GimjeCrawler
from namwon_crawler import NamwonCrawler
from muju_crawler import MujuCrawler
from buan_crawler import BuanCrawler
from sunchang_crawler import SunchangCrawler
from wanju_crawler import WanjuCrawler
from iksan_crawler import IksanCrawler
from imsil_crawler import ImsilCrawler
from jangsu_crawler import JangsuCrawler
from jeonju_crawler import JeonjuCrawler
from jeongeup_crawler import JeongeupCrawler
from jinan_crawler import JinanCrawler

# 전라남도 시군 크롤러 (24개)
from gangjin_crawler import GangjinCrawler
from gwangyang_crawler import GwangyangCrawler
from goheung_crawler import GoheungCrawler
from gokseong_crawler import GokseongCrawler
from gurye_crawler import GuryeCrawler
from naju_crawler import NajuCrawler
from damyang_crawler import DamyangCrawler
from mokpo_crawler import MokpoCrawler
from muan_crawler import MuanCrawler
from boseong_crawler import BoseongCrawler
from suncheon_crawler import SuncheonCrawler
from shinan_crawler import ShinanCrawler
from yeosu_crawler import YeosuCrawler
from yeonggwang_crawler import YeonggwangCrawler
from yeongam_crawler import YeongamCrawler
from wando_crawler import WandoCrawler
from jangseong_crawler import JangseongCrawler
from jangheung_crawler import JangheungCrawler
from jindo_gosi_crawler import JindoGosiCrawler
from jindo_bid_crawler import JindoBidCrawler
from hampyeong_gosi_crawler import HampyeongGosiCrawler
from hampyeong_notice_crawler import HampyeongNoticeCrawler
from haenam_gosi_crawler import HaenamGosiCrawler
from haenam_notice_crawler import HaenamNoticeCrawler

# 서울특별시 자치구 크롤러 + 전남 화순
from hwasun_crawler import HwasunCrawler
from gangnam_crawler import GangnamCrawler
from gangdong_crawler import GangdongCrawler
from gangbuk_crawler import GangbukCrawler
from gangseo_gosi_crawler import GangseoGosiCrawler
from gangseo_bid_crawler import GangseoBidCrawler
from gwanak_gosi_crawler import GwanakGosiCrawler
from gwanak_bid_crawler import GwanakBidCrawler
from gwangjin_crawler import GwangjinCrawler
from guro_crawler import GuroCrawler
from geumcheon_gosi_crawler import GeumcheonGosiCrawler
from geumcheon_bid_crawler import GeumcheonBidCrawler
from nowon_crawler import NowonCrawler
from dobong_crawler import DobongCrawler
from ddm_gosi_crawler import DdmGosiCrawler
from ddm_bid_crawler import DdmBidCrawler
from dongjak_crawler import DongjakCrawler

app = Flask(__name__)


# ============================================================================
# 관리자 인증 (환경변수 ADMIN_TOKEN 기반)
# 환경변수 미설정 시 자동 임의 토큰 생성 (개발 편의)
# ============================================================================
import secrets
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")
if not ADMIN_TOKEN:
    ADMIN_TOKEN = secrets.token_urlsafe(24)
    print(f"[auth] ADMIN_TOKEN 미설정, 임의 생성: {ADMIN_TOKEN}")
    print(f"[auth] 관리자 URL: http://localhost:5001/admin?token={ADMIN_TOKEN}")


def require_admin_token(f):
    """관리자 라우트 보호 데코레이터. ?token= 또는 X-Admin-Token 헤더."""
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        provided = (request.args.get("token")
                    or request.headers.get("X-Admin-Token")
                    or request.cookies.get("admin_token"))
        if provided != ADMIN_TOKEN:
            # HTML 요청이면 인증 페이지, API면 401 JSON
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized",
                                "hint": "?token=... or X-Admin-Token header"}), 401
            return f"""
                <html><body style="font-family:sans-serif;padding:2rem;">
                <h2>🔒 관리자 인증 필요</h2>
                <p>ADMIN_TOKEN 환경변수 또는 URL <code>?token=&lt;토큰&gt;</code>으로 접근하세요.</p>
                <p>서버 로그에서 임의 생성된 토큰 확인 가능합니다.</p>
                </body></html>
            """, 401
        # 인증 성공 시 쿠키 저장 (편의)
        resp = f(*args, **kwargs)
        try:
            from flask import make_response
            resp = make_response(resp)
            resp.set_cookie("admin_token", ADMIN_TOKEN, max_age=86400, httponly=True, samesite="Lax")
        except Exception:
            pass
        return resp
    return wrapper


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

    def search(self, keyword="", max_pages=10, start_date=None, end_date=None):
        crawler = self.crawler_class()
        return crawler.search(keyword, max_pages=max_pages, start_date=start_date, end_date=end_date)


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
    # alio_item: 기관별 입찰공고 (xlsx 13행 /item/itemOrganList.do 매칭)
    # alio (/occasional/)는 수시공시만, alio_item (/item/)은 기관별 전체 입찰공고로 별도 데이터셋.
    # 인천항만공사(C0107) 검증: 사이트 478건 = 우리 API 478건 일치
    "alio_item": {
        "name": "알리오",
        "type": "기관별 입찰공고",
        "instance": AsyncCrawlerWrapper(AlioItemCrawler),
        "url": "https://alio.go.kr/item/itemOrganList.do?reportFormRootNo=B1030"
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
    "gmcc": {
        "name": "광주광역시도시공사",
        "type": "통합검색",
        "instance": GMCCCrawler(),
        "url": "https://www.gmcc.co.kr"
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
    "gcuc": {
        "name": "과천도시공사",
        "type": "개발사업",
        "instance": GCUCCrawler(),
        "url": "https://www.gcuc.or.kr"
    },
    "gh": {
        "name": "경기주택도시공사",
        "type": "통합검색",
        "instance": GHCrawler(),
        "url": "https://www.gh.or.kr"
    },
    "gys": {
        "name": "고양도시관리공사",
        "type": "입찰공고",
        "instance": GYSCrawler(),
        "url": "https://www.gys.or.kr"
    },
    "guriuc": {
        "name": "구리도시공사",
        "type": "입찰정보",
        "instance": GURIUCCrawler(),
        "url": "https://www.guriuc.or.kr"
    },
    "gunpouc": {
        "name": "군포도시공사",
        "type": "입찰공고",
        "instance": GUNPOUCCrawler(),
        "url": "https://www.gunpouc.or.kr"
    },
    "ncuc": {
        "name": "남양주도시공사",
        "type": "공유재산입찰",
        "instance": NCUCCrawler(),
        "url": "https://www.ncuc.or.kr"
    },
    "djuc": {
        "name": "당진도시공사",
        "type": "입찰공고",
        "instance": DJUCCrawler(),
        "url": "https://www.djuc.or.kr"
    },
    "dcco": {
        "name": "대전도시공사",
        "type": "입찰공고",
        "instance": DCCOCrawler(),
        "url": "https://www.dcco.kr"
    },
    "bmc": {
        "name": "부산도시공사",
        "type": "공지사항",
        "instance": BMCCrawler(),
        "url": "https://www.bmc.busan.kr"
    },
    "best": {
        "name": "부천도시공사",
        "type": "공지사항",
        "instance": BESTCrawler(),
        "url": "https://www.best.or.kr"
    },
    "suwonudc": {
        "name": "수원도시공사",
        "type": "계약/입찰공고",
        "instance": SUWONUDCCrawler(),
        "url": "https://www.suwonudc.co.kr"
    },
    "shsi": {
        "name": "시흥도시공사",
        "type": "고시/공고",
        "instance": SHSICrawler(),
        "url": "https://www.shsi.or.kr"
    },
    "ansanuc": {
        "name": "안산도시공사",
        "type": "입찰공고",
        "instance": ANSANUCCrawler(),
        "url": "https://www.ansanuc.net"
    },
    "auc": {
        "name": "안양도시공사",
        "type": "통합검색",
        "instance": AUCCrawler(),
        "url": "https://www.auc.or.kr"
    },
    "yjuc": {
        "name": "양주도시공사",
        "type": "게시판검색",
        "instance": YJUCCrawler(),
        "url": "https://www.yjuc.or.kr"
    },
    "yuc": {
        "name": "용인도시공사",
        "type": "입찰공고",
        "instance": YUCCrawler(),
        "url": "https://www.yuc.co.kr"
    },
    "uuc": {
        "name": "의왕도시공사",
        "type": "통합검색",
        "instance": UUCCrawler(),
        "url": "https://www.uuc.or.kr"
    },
    "uiuc": {
        "name": "의정부도시공사",
        "type": "입찰공고/고시",
        "instance": UIUCCrawler(),
        "url": "https://www.uiuc.or.kr"
    },
    "umca": {
        "name": "울산도시공사",
        "type": "통합검색",
        "instance": UMCACrawler(),
        "url": "https://www.umca.co.kr"
    },
    "ih": {
        "name": "인천도시공사",
        "type": "통합검색",
        "instance": IHCrawler(),
        "url": "https://www.ih.co.kr"
    },
    "cuc": {
        "name": "춘천도시공사",
        "type": "공지사항",
        "instance": CUCCrawler(),
        "url": "https://www.cuc.or.kr"
    },
    "puc": {
        "name": "평택도시공사",
        "type": "통합검색",
        "instance": PUCCrawler(),
        "url": "https://www.puc.or.kr"
    },
    "pcuc": {
        "name": "포천도시공사",
        "type": "게시판검색",
        "instance": PCUCCrawler(),
        "url": "https://www.pcuc.kr"
    },
    "huic": {
        "name": "하남도시공사",
        "type": "공지사항",
        "instance": HUICCrawler(),
        "url": "https://www.huic.co.kr"
    },
    "hu": {
        "name": "화성도시공사",
        "type": "입찰공고",
        "instance": HUCrawler(),
        "url": "https://www.hu.or.kr"
    },
    "cuc_bid": {
        "name": "춘천도시공사",
        "type": "입찰정보",
        "instance": CUCBidCrawler(),
        "url": "https://www.cuc.or.kr"
    },
    "hu_notice": {
        "name": "화성도시공사",
        "type": "공지사항",
        "instance": HUNoticeCrawler(),
        "url": "https://www.hu.or.kr"
    },
    "seoul_bid": {
        "name": "서울특별시청",
        "type": "입찰공고",
        "instance": SeoulBidCrawler(),
        "url": "https://www.seoul.go.kr"
    },
    "seoul_cis": {
        "name": "서울특별시청",
        "type": "공지사항",
        "instance": SeoulCISCrawler(),
        "url": "https://cis.seoul.go.kr"
    },
    "seoul_contract": {
        "name": "서울계약마당",
        "type": "입찰공고",
        "instance": SeoulContractCrawler(),
        "url": "https://contract.seoul.go.kr"
    },
    "gwangju": {
        "name": "광주광역시청",
        "type": "고시공고",
        "instance": GwangjuCrawler(),
        "url": "https://www.gwangju.go.kr"
    },
    "daegu": {
        "name": "대구광역시청",
        "type": "고시공고",
        "instance": DaeguCrawler(),
        "url": "https://www.daegu.go.kr"
    },
    "daejeon_gosi": {
        "name": "대전광역시청",
        "type": "공고",
        "instance": DaejeonGosiCrawler(),
        "url": "https://www.daejeon.go.kr"
    },
    "daejeon_all": {
        "name": "대전광역시청",
        "type": "소식모아보기",
        "instance": DaejeonAllCrawler(),
        "url": "https://www.daejeon.go.kr"
    },
    "busan_notice": {
        "name": "부산광역시청",
        "type": "통합공지사항",
        "instance": BusanNoticeCrawler(),
        "url": "https://www.busan.go.kr"
    },
    "busan_gosi": {
        "name": "부산광역시청",
        "type": "고시공고",
        "instance": BusanGosiCrawler(),
        "url": "https://www.busan.go.kr"
    },
    "ulsan_city": {
        "name": "울산광역시청",
        "type": "고시공고",
        "instance": UlsanCrawler(),
        "url": "https://www.ulsan.go.kr"
    },
    "incheon": {
        "name": "인천광역시청",
        "type": "고시공고",
        "instance": IncheonCrawler(),
        "url": "http://announce.incheon.go.kr"
    },
    "gangwon": {
        "name": "강원특별자치도청",
        "type": "공고/고시",
        "instance": GangwonCrawler(),
        "url": "https://state.gwd.go.kr"
    },
    "sejong_bid": {
        "name": "세종특별자치시청",
        "type": "입찰공고",
        "instance": SejongBidCrawler(),
        "url": "https://www.sejong.go.kr"
    },
    "sejong_general": {
        "name": "세종특별자치시청",
        "type": "일반공고",
        "instance": SejongGeneralCrawler(),
        "url": "https://www.sejong.go.kr"
    },
    "sejong_notice": {
        "name": "세종특별자치시청",
        "type": "공지사항",
        "instance": SejongNoticeCrawler(),
        "url": "https://www.sejong.go.kr"
    },
    "jeonbuk": {
        "name": "전북특별자치도청",
        "type": "전북공고",
        "instance": JeonbukCrawler(),
        "url": "https://www.jeonbuk.go.kr"
    },
    "jeonbuk_other": {
        "name": "전북특별자치도청",
        "type": "타기관공고",
        "instance": JeonbukOtherCrawler(),
        "url": "https://www.jeonbuk.go.kr"
    },
    "jeju": {
        "name": "제주특별자치도청",
        "type": "입법고시공고",
        "instance": JejuCrawler(),
        "url": "https://www.jeju.go.kr"
    },
    "gg": {
        "name": "경기도청",
        "type": "고시공고",
        "instance": GGCrawler(),
        "url": "https://www.gg.go.kr"
    },
    "gsnd_notice": {
        "name": "경상남도청",
        "type": "공지사항",
        "instance": GSNDNoticeCrawler(),
        "url": "https://www.gyeongnam.go.kr"
    },
    "gsnd_gosi": {
        "name": "경상남도청",
        "type": "고시공고",
        "instance": GSNDGosiCrawler(),
        "url": "https://www.gyeongnam.go.kr"
    },
    "gb_notice": {
        "name": "경상북도청",
        "type": "알림마당",
        "instance": GBNoticeCrawler(),
        "url": "https://www.gb.go.kr"
    },
    "gb_gosi": {
        "name": "경상북도청",
        "type": "고시공고",
        "instance": GBGosiCrawler(),
        "url": "https://www.gb.go.kr"
    },
    "jeonnam_notice": {
        "name": "전라남도청",
        "type": "고시/공고",
        "instance": JeonnamNotCrawler(),
        "url": "https://www.jeonnam.go.kr"
    },
    "jeonnam_bid": {
        "name": "전라남도청",
        "type": "입찰공고",
        "instance": JeonnamBidCrawler(),
        "url": "https://gyeyak.jeonnam.go.kr"
    },
    "chungnam": {
        "name": "충청남도청",
        "type": "공고고시",
        "instance": ChungnamCrawler(),
        "url": "https://www.chungnam.go.kr"
    },
    "chungbuk": {
        "name": "충청북도청",
        "type": "고시/공고",
        "instance": ChungbukCrawler(),
        "url": "https://www.chungbuk.go.kr"
    },
    # 경기도 시군 (79-132)
    "gapyeong_notice": {
        "name": "가평군청",
        "type": "공지사항",
        "instance": GapyeongNoticeCrawler(),
        "url": "http://www.gp.go.kr"
    },
    "gapyeong_gosi": {
        "name": "가평군청",
        "type": "고시공고",
        "instance": GapyeongGosiCrawler(),
        "url": "http://www.gp.go.kr"
    },
    "gwacheon_bid": {
        "name": "과천시청",
        "type": "입찰공고",
        "instance": GwacheonBidCrawler(),
        "url": "https://www.gccity.go.kr"
    },
    "gwacheon_gosi": {
        "name": "과천시청",
        "type": "고시/공고",
        "instance": GwacheonGosiCrawler(),
        "url": "https://www.gccity.go.kr"
    },
    "gwangmyeong_bid": {
        "name": "광명시청",
        "type": "입찰공고",
        "instance": GwangmyeongBidCrawler(),
        "url": "https://www.gm.go.kr"
    },
    "gwangmyeong_gosi": {
        "name": "광명시청",
        "type": "고시공고",
        "instance": GwangmyeongGosiCrawler(),
        "url": "https://www.gm.go.kr"
    },
    "gjcity_gosi": {
        "name": "광주시청",
        "type": "고시공고",
        "instance": GjcityGosiCrawler(),
        "url": "https://www.gjcity.go.kr"
    },
    "gjcity_bid": {
        "name": "광주시청",
        "type": "입찰공고",
        "instance": GjcityBidCrawler(),
        "url": "https://www.gjcity.go.kr"
    },
    "guri_notice": {
        "name": "구리시청",
        "type": "공지사항",
        "instance": GuriNoticeCrawler(),
        "url": "https://www.guri.go.kr"
    },
    "guri_bid": {
        "name": "구리시청",
        "type": "입찰공고",
        "instance": GuriBidCrawler(),
        "url": "https://www.guri.go.kr"
    },
    "gunpo_gosi": {
        "name": "군포시청",
        "type": "고시공고",
        "instance": GunpoGosiCrawler(),
        "url": "https://www.gunpo.go.kr"
    },
    "gunpo_bid": {
        "name": "군포시청",
        "type": "입찰공고",
        "instance": GunpoBidCrawler(),
        "url": "https://www.gunpo.go.kr"
    },
    "goyang_bid": {
        "name": "고양특례시청",
        "type": "입찰공고",
        "instance": GoyangBidCrawler(),
        "url": "https://www.goyang.go.kr"
    },
    "gimpo_gosi": {
        "name": "김포시청",
        "type": "고시공고",
        "instance": GimpoGosiCrawler(),
        "url": "https://www.gimpo.go.kr"
    },
    "gimpo_bid": {
        "name": "김포시청",
        "type": "입찰공고",
        "instance": GimpoBidCrawler(),
        "url": "https://www.gimpo.go.kr"
    },
    "namyangju": {
        "name": "남양주시청",
        "type": "고시공고",
        "instance": NamyangjuCrawler(),
        "url": "https://www.nyj.go.kr"
    },
    "dongducheon_gosi": {
        "name": "동두천시청",
        "type": "일반공고",
        "instance": DongducheonGosiCrawler(),
        "url": "https://www.ddc.go.kr"
    },
    "dongducheon_bid": {
        "name": "동두천시청",
        "type": "입찰공고",
        "instance": DongducheonBidCrawler(),
        "url": "https://www.ddc.go.kr"
    },
    "bucheon_bid": {
        "name": "부천시청",
        "type": "입찰공고",
        "instance": BucheonBidCrawler(),
        "url": "http://www.bucheon.go.kr"
    },
    "seongnam_bid": {
        "name": "성남시청",
        "type": "입찰공고",
        "instance": SeongnamBidCrawler(),
        "url": "https://www.seongnam.go.kr"
    },
    "suwon": {
        "name": "수원특례시청",
        "type": "공고/고시",
        "instance": SuwonCrawler(),
        "url": "https://www.suwon.go.kr"
    },
    "siheung_bid": {
        "name": "시흥시청",
        "type": "입찰정보",
        "instance": SiheungBidCrawler(),
        "url": "https://www.siheung.go.kr"
    },
    "siheung_gosi": {
        "name": "시흥시청",
        "type": "고시/공고",
        "instance": SiheungGosiCrawler(),
        "url": "https://www.siheung.go.kr"
    },
    "ansan_gosi": {
        "name": "안산시청",
        "type": "고시/공고",
        "instance": AnsanGosiCrawler(),
        "url": "https://www.ansan.go.kr"
    },
    "ansan_bid": {
        "name": "안산시청",
        "type": "입찰공고",
        "instance": AnsanBidCrawler(),
        "url": "https://www.ansan.go.kr"
    },
    "anseong_bid": {
        "name": "안성시청",
        "type": "입찰공고",
        "instance": AnseongBidCrawler(),
        "url": "https://www.anseong.go.kr"
    },
    "anseong_gosi": {
        "name": "안성시청",
        "type": "고시/공고",
        "instance": AnseongGosiCrawler(),
        "url": "https://www.anseong.go.kr"
    },
    "anyang_bid": {
        "name": "안양시청",
        "type": "입찰공고",
        "instance": AnyangBidCrawler(),
        "url": "https://www.anyang.go.kr"
    },
    "anyang_gosi": {
        "name": "안양시청",
        "type": "고시공고",
        "instance": AnyangGosiCrawler(),
        "url": "https://www.anyang.go.kr"
    },
    "yangju_bid": {
        "name": "양주시청",
        "type": "입찰공고",
        "instance": YangjuBidCrawler(),
        "url": "https://www.yangju.go.kr"
    },
    "yangju_notice": {
        "name": "양주시청",
        "type": "양주소식",
        "instance": YangjuNoticeCrawler(),
        "url": "https://www.yangju.go.kr"
    },
    "yangpyeong": {
        "name": "양평군청",
        "type": "고시/공고",
        "instance": YangpyeongCrawler(),
        "url": "https://www.yp21.go.kr"
    },
    "yeoju_gosi": {
        "name": "여주시청",
        "type": "고시/공고",
        "instance": YeojuGosiCrawler(),
        "url": "https://www.yeoju.go.kr"
    },
    "yeoju_bid": {
        "name": "여주시청",
        "type": "입찰정보",
        "instance": YeojuBidCrawler(),
        "url": "https://www.yeoju.go.kr"
    },
    "yeoncheon": {
        "name": "연천군청",
        "type": "고시/공고",
        "instance": YeoncheonCrawler(),
        "url": "https://www.yeoncheon.go.kr"
    },
    "osan_bid": {
        "name": "오산시청",
        "type": "입찰공고",
        "instance": OsanBidCrawler(),
        "url": "https://www.osan.go.kr"
    },
    "osan_gosi": {
        "name": "오산시청",
        "type": "고시/공고",
        "instance": OsanGosiCrawler(),
        "url": "https://www.osan.go.kr"
    },
    "yongin_committee": {
        "name": "용인특례시청",
        "type": "공법선정위원회",
        "instance": YonginCommitteeCrawler(),
        "url": "http://www.yongin.go.kr"
    },
    "yongin_bid": {
        "name": "용인특례시청",
        "type": "입찰공고",
        "instance": YonginBidCrawler(),
        "url": "http://www.yongin.go.kr"
    },
    "icheon_bid": {
        "name": "이천시청",
        "type": "입찰공고",
        "instance": IcheonBidCrawler(),
        "url": "https://www.icheon.go.kr"
    },
    "icheon_gosi": {
        "name": "이천시청",
        "type": "일반공고",
        "instance": IcheonGosiCrawler(),
        "url": "https://www.icheon.go.kr"
    },
    "uiwang_bid": {
        "name": "의왕시청",
        "type": "입찰정보",
        "instance": UiwangBidCrawler(),
        "url": "https://www.uiwang.go.kr"
    },
    "uiwang_gosi": {
        "name": "의왕시청",
        "type": "고시공고",
        "instance": UiwangGosiCrawler(),
        "url": "https://www.uiwang.go.kr"
    },
    "uijeongbu_gosi": {
        "name": "의정부시청",
        "type": "고시/공고",
        "instance": UijeongbuGosiCrawler(),
        "url": "https://www.ui4u.go.kr"
    },
    "uijeongbu_bid": {
        "name": "의정부시청",
        "type": "입찰정보",
        "instance": UijeongbuBidCrawler(),
        "url": "https://www.ui4u.go.kr"
    },
    "paju": {
        "name": "파주시청",
        "type": "고시공고",
        "instance": PajuCrawler(),
        "url": "https://www.paju.go.kr"
    },
    "pyeongtaek_gosi": {
        "name": "평택시청",
        "type": "고시공고",
        "instance": PyeongtaekGosiCrawler(),
        "url": "https://www.pyeongtaek.go.kr"
    },
    "pyeongtaek_bid": {
        "name": "평택시청",
        "type": "입찰공고",
        "instance": PyeongtaekBidCrawler(),
        "url": "https://www.pyeongtaek.go.kr"
    },
    "pocheon_bid": {
        "name": "포천시청",
        "type": "입찰공고",
        "instance": PocheonBidCrawler(),
        "url": "https://www.pocheon.go.kr"
    },
    "pocheon_gosi": {
        "name": "포천시청",
        "type": "고시공고",
        "instance": PocheonGosiCrawler(),
        "url": "https://www.pocheon.go.kr"
    },
    "hanam_gosi": {
        "name": "하남시청",
        "type": "고시공고",
        "instance": HanamGosiCrawler(),
        "url": "https://www.hanam.go.kr"
    },
    "hanam_bid": {
        "name": "하남시청",
        "type": "입찰공고",
        "instance": HanamBidCrawler(),
        "url": "https://www.hanam.go.kr"
    },
    "hwaseong_gosi": {
        "name": "화성특례시청",
        "type": "일반공고",
        "instance": HwaseongGosiCrawler(),
        "url": "https://www.hscity.go.kr"
    },
    "hwaseong_bid": {
        "name": "화성특례시청",
        "type": "입찰공고",
        "instance": HwaseongBidCrawler(),
        "url": "https://www.hscity.go.kr"
    },
    # 강원도 시군 크롤러
    "gangneung_gosi": {
        "name": "강릉시청",
        "type": "일반공고",
        "instance": GangneungGosiCrawler(),
        "url": "https://www.gn.go.kr"
    },
    "gangneung_bid": {
        "name": "강릉시청",
        "type": "입찰공고",
        "instance": GangneungBidCrawler(),
        "url": "https://www.gn.go.kr"
    },
    "goseong_gw": {
        "name": "고성군청(강원)",
        "type": "고시공고",
        "instance": GoseongGwCrawler(),
        "url": "https://www.goseong.go.kr"
    },
    "donghae_gosi": {
        "name": "동해시청",
        "type": "고시공고",
        "instance": DonghaeGosiCrawler(),
        "url": "https://www.dh.go.kr"
    },
    "donghae_bid": {
        "name": "동해시청",
        "type": "입찰공고",
        "instance": DonghaeBidCrawler(),
        "url": "https://www.dh.go.kr"
    },
    "samcheok_gosi": {
        "name": "삼척시청",
        "type": "입법/공고/고시",
        "instance": SamcheokGosiCrawler(),
        "url": "https://www.samcheok.go.kr"
    },
    "samcheok_bid": {
        "name": "삼척시청",
        "type": "입찰공고",
        "instance": SamcheokBidCrawler(),
        "url": "https://gyeyak.samcheok.go.kr"
    },
    "sokcho_gosi": {
        "name": "속초시청",
        "type": "고시공고",
        "instance": SokchoGosiCrawler(),
        "url": "https://www.sokcho.go.kr"
    },
    "sokcho_notice": {
        "name": "속초시청",
        "type": "공지사항",
        "instance": SokchoNoticeCrawler(),
        "url": "https://www.sokcho.go.kr"
    },
    "yanggu": {
        "name": "양구군청",
        "type": "고시/공고",
        "instance": YangguCrawler(),
        "url": "https://www.yanggu.go.kr"
    },
    "yangyang_bid": {
        "name": "양양군청",
        "type": "입찰정보",
        "instance": YangyangBidCrawler(),
        "url": "https://www.yangyang.go.kr"
    },
    "yangyang_gosi": {
        "name": "양양군청",
        "type": "공고/고시",
        "instance": YangyangGosiCrawler(),
        "url": "https://www.yangyang.go.kr"
    },
    "yeongwol": {
        "name": "영월군청",
        "type": "고시/공고",
        "instance": YeongwolCrawler(),
        "url": "https://www.yw.go.kr"
    },
    "wonju_gosi": {
        "name": "원주시청",
        "type": "원주시 공고",
        "instance": WonjuGosiCrawler(),
        "url": "https://www.wonju.go.kr"
    },
    "wonju_notice": {
        "name": "원주시청",
        "type": "새소식",
        "instance": WonjuNoticeCrawler(),
        "url": "https://www.wonju.go.kr"
    },
    "inje_gosi": {
        "name": "인제군청",
        "type": "일반고시공고",
        "instance": InjeGosiCrawler(),
        "url": "https://www.inje.go.kr"
    },
    "inje_bid": {
        "name": "인제군청",
        "type": "입찰정보",
        "instance": InjeBidCrawler(),
        "url": "https://www.inje.go.kr"
    },
    "jeongseon_gosi": {
        "name": "정선군청",
        "type": "공고/고시",
        "instance": JeongseonGosiCrawler(),
        "url": "https://www.jeongseon.go.kr"
    },
    "jeongseon_bid": {
        "name": "정선군청",
        "type": "입찰정보",
        "instance": JeongseonBidCrawler(),
        "url": "https://www.jeongseon.go.kr"
    },
    "cheorwon_gosi": {
        "name": "철원군청",
        "type": "고시/공고",
        "instance": CheorwonGosiCrawler(),
        "url": "https://www.cwg.go.kr"
    },
    "cheorwon_bid": {
        "name": "철원군청",
        "type": "입찰공고",
        "instance": CheorwonBidCrawler(),
        "url": "https://www.cwg.go.kr"
    },
    "chuncheon_gosi": {
        "name": "춘천시청",
        "type": "고시/공고",
        "instance": ChuncheonGosiCrawler(),
        "url": "https://www.chuncheon.go.kr"
    },
    "taebaek_gosi": {
        "name": "태백시청",
        "type": "공고/고시",
        "instance": TaebaekGosiCrawler(),
        "url": "https://www.taebaek.go.kr"
    },
    "taebaek_bid": {
        "name": "태백시청",
        "type": "입찰공고",
        "instance": TaebaekBidCrawler(),
        "url": "http://ehojo.taebaek.go.kr"
    },
    "pyeongchang": {
        "name": "평창군청",
        "type": "일반공고",
        "instance": PyeongchangCrawler(),
        "url": "https://www.pc.go.kr"
    },
    "hapcheon": {
        "name": "합천군청",
        "type": "고시공고",
        "instance": HapcheonCrawler(),
        "url": "https://www.hc.go.kr"
    },
    "hwacheon_bid": {
        "name": "화천군청",
        "type": "입찰공고",
        "instance": HwacheonBidCrawler(),
        "url": "http://www.ihc.go.kr"
    },
    "hwacheon_gosi": {
        "name": "화천군청",
        "type": "고시공고",
        "instance": HwacheonGosiCrawler(),
        "url": "http://www.ihc.go.kr"
    },
    "hongcheon_gosi": {
        "name": "홍천군청",
        "type": "고시공고",
        "instance": HongcheonGosiCrawler(),
        "url": "https://www.hongcheon.go.kr"
    },
    "hongcheon_bid": {
        "name": "홍천군청",
        "type": "입찰공고",
        "instance": HongcheonBidCrawler(),
        "url": "https://www.hongcheon.go.kr"
    },
    "hoengseong_gosi": {
        "name": "횡성군청",
        "type": "고시공고",
        "instance": HoengseongGosiCrawler(),
        "url": "https://www.hsg.go.kr"
    },
    "hoengseong_bid": {
        "name": "횡성군청",
        "type": "입찰공고",
        "instance": HoengseongBidCrawler(),
        "url": "https://gyeyak.hsg.go.kr"
    },
    # 충청북도 시군 크롤러
    "goesan_gosi": {
        "name": "괴산군청",
        "type": "고시/공고",
        "instance": GoesanGosiCrawler(),
        "url": "https://www.goesan.go.kr"
    },
    "goesan_bid": {
        "name": "괴산군청",
        "type": "입찰공고",
        "instance": GoesanBidCrawler(),
        "url": "https://www.goesan.go.kr"
    },
    "danyang_gosi": {
        "name": "단양군청",
        "type": "고시공고",
        "instance": DanyangGosiCrawler(),
        "url": "https://www.danyang.go.kr"
    },
    "danyang_bid": {
        "name": "단양군청",
        "type": "입찰공고",
        "instance": DanyangBidCrawler(),
        "url": "https://www.danyang.go.kr"
    },
    "boeun_gosi": {
        "name": "보은군청",
        "type": "고시/공고",
        "instance": BoeunGosiCrawler(),
        "url": "https://www.boeun.go.kr"
    },
    "boeun_bid": {
        "name": "보은군청",
        "type": "입찰정보",
        "instance": BoeunBidCrawler(),
        "url": "https://www.boeun.go.kr"
    },
    "yeongdong": {
        "name": "영동군청",
        "type": "고시공고",
        "instance": YeongdongCrawler(),
        "url": "https://www.yd21.go.kr"
    },
    "okcheon_gosi": {
        "name": "옥천군청",
        "type": "고시/공고",
        "instance": OkcheonGosiCrawler(),
        "url": "https://www.oc.go.kr"
    },
    "okcheon_notice": {
        "name": "옥천군청",
        "type": "공지사항",
        "instance": OkcheonNoticeCrawler(),
        "url": "https://www.oc.go.kr"
    },
    "eumseong": {
        "name": "음성군청",
        "type": "고시/공고",
        "instance": EumseongCrawler(),
        "url": "https://www.eumseong.go.kr"
    },
    "jecheon_gosi": {
        "name": "제천시청",
        "type": "고시공고",
        "instance": JecheonGosiCrawler(),
        "url": "https://www.jecheon.go.kr"
    },
    "jecheon_bid": {
        "name": "제천시청",
        "type": "입찰공고",
        "instance": JecheonBidCrawler(),
        "url": "https://www.jecheon.go.kr"
    },
    "jeungpyeong_gosi": {
        "name": "증평군청",
        "type": "고시공고",
        "instance": JeungpyeongGosiCrawler(),
        "url": "http://www.jp.go.kr"
    },
    "jeungpyeong_bid": {
        "name": "증평군청",
        "type": "입찰공고",
        "instance": JeungpyeongBidCrawler(),
        "url": "http://www.jp.go.kr"
    },
    "jincheon_bid": {
        "name": "진천군청",
        "type": "입찰공고",
        "instance": JincheonBidCrawler(),
        "url": "https://www.jincheon.go.kr"
    },
    "jincheon_gosi": {
        "name": "진천군청",
        "type": "일반공고",
        "instance": JincheonGosiCrawler(),
        "url": "https://www.jincheon.go.kr"
    },
    "cheongju": {
        "name": "청주시청",
        "type": "고시공고",
        "instance": CheongjuCrawler(),
        "url": "https://www.cheongju.go.kr"
    },
    "chungju": {
        "name": "충주시청",
        "type": "공고/고시/입찰",
        "instance": ChungjuCrawler(),
        "url": "https://www.chungju.go.kr"
    },
    # 충청남도 시군 크롤러 (15개)
    "yesan_bid": {
        "name": "예산군청",
        "type": "입찰",
        "instance": YesanBidCrawler(),
        "url": "https://www.yesan.go.kr"
    },
    "cheonan_gosi": {
        "name": "천안시청",
        "type": "행정공고",
        "instance": CheonanGosiCrawler(),
        "url": "https://www.cheonan.go.kr"
    },
    "cheonan_bid": {
        "name": "천안시청",
        "type": "입찰",
        "instance": CheonanBidCrawler(),
        "url": "https://www.cheonan.go.kr"
    },
    "cheongyang": {
        "name": "청양군청",
        "type": "고시공고",
        "instance": CheongyangCrawler(),
        "url": "https://www.cheongyang.go.kr"
    },
    "taean_bid": {
        "name": "태안군청",
        "type": "입찰",
        "instance": TaeanBidCrawler(),
        "url": "https://www.taean.go.kr"
    },
    "taean_gosi": {
        "name": "태안군청",
        "type": "일반공고",
        "instance": TaeanGosiCrawler(),
        "url": "https://www.taean.go.kr"
    },
    "hongseong": {
        "name": "홍성군청",
        "type": "고시공고",
        "instance": HongseongCrawler(),
        "url": "https://www.hongseong.go.kr"
    },
    "gyeryong": {
        "name": "계룡시청",
        "type": "고시/공고",
        "instance": GyeryongCrawler(),
        "url": "https://gyeryong.go.kr"
    },
    "gongju_bid": {
        "name": "공주시청",
        "type": "입찰공고",
        "instance": GongjuBidCrawler(),
        "url": "https://www.gongju.go.kr"
    },
    "gongju_gosi": {
        "name": "공주시청",
        "type": "일반공고",
        "instance": GongjuGosiCrawler(),
        "url": "https://www.gongju.go.kr"
    },
    "geumsan": {
        "name": "금산군청",
        "type": "고시/공고",
        "instance": GeumsanCrawler(),
        "url": "https://www.geumsan.go.kr"
    },
    "nonsan": {
        "name": "논산시청",
        "type": "공고",
        "instance": NonsanCrawler(),
        "url": "https://nonsan.go.kr"
    },
    "dangjin": {
        "name": "당진시청",
        "type": "고시/공고",
        "instance": DangjinCrawler(),
        "url": "https://www.dangjin.go.kr"
    },
    "buyeo_gosi": {
        "name": "부여군청",
        "type": "고시공고",
        "instance": BuyeoGosiCrawler(),
        "url": "https://www.buyeo.go.kr"
    },
    "buyeo_bid": {
        "name": "부여군청",
        "type": "입찰공고",
        "instance": BuyeoBidCrawler(),
        "url": "https://www.buyeo.go.kr"
    },
    "boryeong": {
        "name": "보령시청",
        "type": "고시공고",
        "instance": BoryeongCrawler(),
        "url": "https://www.brcn.go.kr"
    },
    "seosan_gosi": {
        "name": "서산시청",
        "type": "공고/고시",
        "instance": SeosanGosiCrawler(),
        "url": "https://www.seosan.go.kr"
    },
    "seosan_bid": {
        "name": "서산시청",
        "type": "입찰공고",
        "instance": SeosanBidCrawler(),
        "url": "https://www.seosan.go.kr"
    },
    "seocheon_bid": {
        "name": "서천군청",
        "type": "입찰공고",
        "instance": SeocheonBidCrawler(),
        "url": "https://www.seocheon.go.kr"
    },
    "seocheon_gosi": {
        "name": "서천군청",
        "type": "일반공고",
        "instance": SeocheonGosiCrawler(),
        "url": "https://www.seocheon.go.kr"
    },
    "asan_bid": {
        "name": "아산시청",
        "type": "입찰공고",
        "instance": AsanBidCrawler(),
        "url": "https://www.asan.go.kr"
    },
    "asan_gosi": {
        "name": "아산시청",
        "type": "고시공고",
        "instance": AsanGosiCrawler(),
        "url": "https://www.asan.go.kr"
    },
    "yesan_gosi": {
        "name": "예산군청",
        "type": "고시공고",
        "instance": YesanGosiCrawler(),
        "url": "https://www.yesan.go.kr"
    },
    # 경상남도 시군 크롤러 (21개)
    "geoje": {
        "name": "거제시청",
        "type": "고시공고",
        "instance": GeojeCrawler(),
        "url": "https://www.geoje.go.kr"
    },
    "geochang": {
        "name": "거창군청",
        "type": "고시공고",
        "instance": GeochangCrawler(),
        "url": "https://www.geochang.go.kr"
    },
    "goseong_gn": {
        "name": "고성군청(경남)",
        "type": "고시공고",
        "instance": GoseongGnCrawler(),
        "url": "https://www.goseong.go.kr"
    },
    "gimhae": {
        "name": "김해시청",
        "type": "고시공고",
        "instance": GimhaeCrawler(),
        "url": "https://www.gimhae.go.kr"
    },
    "namhae": {
        "name": "남해군청",
        "type": "고시공고",
        "instance": NamhaeCrawler(),
        "url": "https://www.namhae.go.kr"
    },
    "miryang": {
        "name": "밀양시청",
        "type": "고시공고",
        "instance": MiryangCrawler(),
        "url": "https://www.miryang.go.kr"
    },
    "sacheon": {
        "name": "사천시청",
        "type": "고시공고",
        "instance": SacheonCrawler(),
        "url": "https://www.sacheon.go.kr"
    },
    "sancheong": {
        "name": "산청군청",
        "type": "고시공고",
        "instance": SancheongCrawler(),
        "url": "https://www.sancheong.go.kr"
    },
    "yangsan_gosi": {
        "name": "양산시청",
        "type": "고시",
        "instance": YangsanGosiCrawler(),
        "url": "https://www.yangsan.go.kr"
    },
    "yangsan_bid": {
        "name": "양산시청",
        "type": "입찰",
        "instance": YangsanBidCrawler(),
        "url": "https://www.yangsan.go.kr"
    },
    "uiryeong_gosi": {
        "name": "의령군청",
        "type": "고시",
        "instance": UiryeongGosiCrawler(),
        "url": "https://www.uiryeong.go.kr"
    },
    "uiryeong_bid": {
        "name": "의령군청",
        "type": "입찰",
        "instance": UiryeongBidCrawler(),
        "url": "https://www.uiryeong.go.kr"
    },
    "jinju": {
        "name": "진주시청",
        "type": "고시공고",
        "instance": JinjuCrawler(),
        "url": "https://www.jinju.go.kr"
    },
    "changnyeong_gosi": {
        "name": "창녕군청",
        "type": "고시공고",
        "instance": ChangnyeongGosiCrawler(),
        "url": "https://www.cng.go.kr"
    },
    "changnyeong_bid": {
        "name": "창녕군청",
        "type": "입찰공고",
        "instance": ChangnyeongBidCrawler(),
        "url": "https://www.cng.go.kr"
    },
    "changwon_gosi": {
        "name": "창원특례시청",
        "type": "고시공고",
        "instance": ChangwonGosiCrawler(),
        "url": "https://www.changwon.go.kr"
    },
    "changwon_bid": {
        "name": "창원특례시청",
        "type": "입찰공고",
        "instance": ChangwonBidCrawler(),
        "url": "https://www.changwon.go.kr"
    },
    "tongyeong": {
        "name": "통영시청",
        "type": "고시공고",
        "instance": TongyeongCrawler(),
        "url": "https://www.tongyeong.go.kr"
    },
    "hadong": {
        "name": "하동군청",
        "type": "공고고시",
        "instance": HadongCrawler(),
        "url": "https://www.hadong.go.kr"
    },
    "haman": {
        "name": "함안군청",
        "type": "고시공고",
        "instance": HamanCrawler(),
        "url": "https://www.haman.go.kr"
    },
    "hamyang": {
        "name": "함양군청",
        "type": "고시공고",
        "instance": HamyangCrawler(),
        "url": "https://www.hygn.go.kr"
    },
    # 경상북도 시군 크롤러
    "gyeongsan_gosi": {
        "name": "경산시청",
        "type": "고시공고",
        "instance": GyeongsanGosiCrawler(),
        "url": "https://www.gbgs.go.kr"
    },
    "gyeongsan_bid": {
        "name": "경산시청",
        "type": "입찰공고",
        "instance": GyeongsanBidCrawler(),
        "url": "https://www.gbgs.go.kr"
    },
    "gyeongju_gosi": {
        "name": "경주시청",
        "type": "고시공고",
        "instance": GyeongjuGosiCrawler(),
        "url": "https://www.gyeongju.go.kr"
    },
    "gyeongju_bid": {
        "name": "경주시청",
        "type": "입찰공고",
        "instance": GyeongjuBidCrawler(),
        "url": "https://www.gyeongju.go.kr"
    },
    "goryeong": {
        "name": "고령군청",
        "type": "고시/공고",
        "instance": GoryeongCrawler(),
        "url": "https://www.goryeong.go.kr"
    },
    "gumi_gosi": {
        "name": "구미시청",
        "type": "고시공고",
        "instance": GumiGosiCrawler(),
        "url": "https://www.gumi.go.kr"
    },
    "gumi_bid": {
        "name": "구미시청",
        "type": "입찰공고",
        "instance": GumiBidCrawler(),
        "url": "https://www.gumi.go.kr"
    },
    "gunwi_gosi": {
        "name": "군위군청",
        "type": "고시공고",
        "instance": GunwiGosiCrawler(),
        "url": "https://www.gunwi.go.kr"
    },
    "gunwi_bid": {
        "name": "군위군청",
        "type": "입찰정보",
        "instance": GunwiBidCrawler(),
        "url": "https://www.gunwi.go.kr"
    },
    "gimcheon_gosi": {
        "name": "김천시청",
        "type": "고시공고",
        "instance": GimcheonGosiCrawler(),
        "url": "https://www.gc.go.kr"
    },
    "gimcheon_bid": {
        "name": "김천시청",
        "type": "입찰정보",
        "instance": GimcheonBidCrawler(),
        "url": "https://www.gc.go.kr"
    },
    "mungyeong_gosi": {
        "name": "문경시청",
        "type": "고시공고",
        "instance": MungyeongGosiCrawler(),
        "url": "https://www.gbmg.go.kr"
    },
    "mungyeong_bid": {
        "name": "문경시청",
        "type": "입찰공고",
        "instance": MungyeongBidCrawler(),
        "url": "https://www.gbmg.go.kr"
    },
    "bonghwa_gosi": {
        "name": "봉화군청",
        "type": "고시공고",
        "instance": BonghwaGosiCrawler(),
        "url": "https://www.bonghwa.go.kr"
    },
    "bonghwa_bid": {
        "name": "봉화군청",
        "type": "입찰공고",
        "instance": BonghwaBidCrawler(),
        "url": "https://www.bonghwa.go.kr"
    },
    "sangju": {
        "name": "상주시청",
        "type": "고시/공고",
        "instance": SangjuCrawler(),
        "url": "https://www.sangju.go.kr"
    },
    "seongju": {
        "name": "성주군청",
        "type": "고시/공고",
        "instance": SeongjuCrawler(),
        "url": "https://www.sj.go.kr"
    },
    "andong_gosi": {
        "name": "안동시청",
        "type": "고시/공고",
        "instance": AndongGosiCrawler(),
        "url": "https://www.andong.go.kr"
    },
    "andong_bid": {
        "name": "안동시청",
        "type": "입찰정보",
        "instance": AndongBidCrawler(),
        "url": "https://www.andong.go.kr"
    },
    "yeongdeok_gosi": {
        "name": "영덕군청",
        "type": "고시/공고",
        "instance": YeongdeokGosiCrawler(),
        "url": "https://www.yd.go.kr"
    },
    "yeongdeok_bid": {
        "name": "영덕군청",
        "type": "입찰정보",
        "instance": YeongdeokBidCrawler(),
        "url": "https://www.yd.go.kr"
    },
    "yeongyang": {
        "name": "영양군청",
        "type": "고시/공고",
        "instance": YeongyangCrawler(),
        "url": "https://www.yyg.go.kr"
    },
    "yeongju_gosi": {
        "name": "영주시청",
        "type": "고시/공고",
        "instance": YeongjuGosiCrawler(),
        "url": "https://www.yeongju.go.kr"
    },
    "yeongju_bid": {
        "name": "영주시청",
        "type": "입찰공고",
        "instance": YeongjuBidCrawler(),
        "url": "https://www.yeongju.go.kr"
    },
    "yeongcheon_gosi": {
        "name": "영천시청",
        "type": "고시/공고",
        "instance": YeongcheonGosiCrawler(),
        "url": "https://www.yc.go.kr"
    },
    "yeongcheon_bid": {
        "name": "영천시청",
        "type": "입찰공고",
        "instance": YeongcheonBidCrawler(),
        "url": "https://www.yc.go.kr"
    },
    "yecheon_gosi": {
        "name": "예천군청",
        "type": "공고/고시",
        "instance": YecheonGosiCrawler(),
        "url": "https://www.ycg.kr"
    },
    "yecheon_bid": {
        "name": "예천군청",
        "type": "입찰정보",
        "instance": YecheonBidCrawler(),
        "url": "https://www.ycg.kr"
    },
    "ulleung_gosi": {
        "name": "울릉군청",
        "type": "고시공고",
        "instance": UlleungGosiCrawler(),
        "url": "https://www.ulleung.go.kr"
    },
    "ulleung_bid": {
        "name": "울릉군청",
        "type": "입찰정보",
        "instance": UlleungBidCrawler(),
        "url": "https://www.ulleung.go.kr"
    },
    "uljin": {
        "name": "울진군청",
        "type": "고시/공고",
        "instance": UljinCrawler(),
        "url": "https://www.uljin.go.kr"
    },
    "uiseong_gosi": {
        "name": "의성군청",
        "type": "고시/공고",
        "instance": UiseongGosiCrawler(),
        "url": "https://www.usc.go.kr"
    },
    "uiseong_bid": {
        "name": "의성군청",
        "type": "입찰정보",
        "instance": UiseongBidCrawler(),
        "url": "https://www.usc.go.kr"
    },
    "cheongdo_gosi": {
        "name": "청도군청",
        "type": "고시공고",
        "instance": CheongdoGosiCrawler(),
        "url": "https://www.cheongdo.go.kr"
    },
    "cheongdo_bid": {
        "name": "청도군청",
        "type": "입찰정보",
        "instance": CheongdoBidCrawler(),
        "url": "https://www.cheongdo.go.kr"
    },
    "cheongsong_gosi": {
        "name": "청송군청",
        "type": "고시공고",
        "instance": CheongsongGosiCrawler(),
        "url": "https://www.cs.go.kr"
    },
    "cheongsong_bid": {
        "name": "청송군청",
        "type": "입찰공고",
        "instance": CheongsongBidCrawler(),
        "url": "https://www.cs.go.kr"
    },
    "chilgok": {
        "name": "칠곡군",
        "type": "공고/고시",
        "instance": ChilgokCrawler(),
        "url": "https://www.chilgok.go.kr"
    },
    "pohang_gosi": {
        "name": "포항시청",
        "type": "고시공고",
        "instance": PohangGosiCrawler(),
        "url": "https://www.pohang.go.kr"
    },
    "pohang_bid": {
        "name": "포항시청",
        "type": "입찰공고",
        "instance": PohangBidCrawler(),
        "url": "https://www.pohang.go.kr"
    },
    # 전라북도 시군 크롤러
    "gochang": {
        "name": "고창군청",
        "type": "고시공고",
        "instance": GochangCrawler(),
        "url": "https://www.gochang.go.kr"
    },
    "gunsan": {
        "name": "군산시청",
        "type": "고시공고",
        "instance": GunsanCrawler(),
        "url": "https://eminwon.gunsan.go.kr"
    },
    "gimje": {
        "name": "김제시청",
        "type": "고시공고",
        "instance": GimjeCrawler(),
        "url": "https://www.gimje.go.kr"
    },
    "namwon": {
        "name": "남원시청",
        "type": "고시공고",
        "instance": NamwonCrawler(),
        "url": "https://www.namwon.go.kr"
    },
    "muju": {
        "name": "무주군청",
        "type": "고시공고",
        "instance": MujuCrawler(),
        "url": "https://www.muju.go.kr"
    },
    "buan": {
        "name": "부안군청",
        "type": "고시공고",
        "instance": BuanCrawler(),
        "url": "https://www.buan.go.kr"
    },
    "sunchang": {
        "name": "순창군청",
        "type": "고시공고",
        "instance": SunchangCrawler(),
        "url": "http://eminwon.sunchang.go.kr"
    },
    "wanju": {
        "name": "완주군청",
        "type": "고시공고",
        "instance": WanjuCrawler(),
        "url": "https://www.wanju.go.kr"
    },
    "iksan": {
        "name": "익산시청",
        "type": "고시공고",
        "instance": IksanCrawler(),
        "url": "https://eminwon.iksan.go.kr"
    },
    "imsil": {
        "name": "임실군청",
        "type": "고시공고",
        "instance": ImsilCrawler(),
        "url": "https://www.imsil.go.kr"
    },
    "jangsu": {
        "name": "장수군청",
        "type": "고시공고",
        "instance": JangsuCrawler(),
        "url": "https://www.jangsu.go.kr"
    },
    "jeonju": {
        "name": "전주시청",
        "type": "고시공고",
        "instance": JeonjuCrawler(),
        "url": "https://www.jeonju.go.kr"
    },
    "jeongeup": {
        "name": "정읍시청",
        "type": "고시공고",
        "instance": JeongeupCrawler(),
        "url": "http://eminwon.jeongeup.go.kr"
    },
    "jinan": {
        "name": "진안군청",
        "type": "고시공고",
        "instance": JinanCrawler(),
        "url": "https://www.jinan.go.kr"
    },
    # 전라남도 시군 크롤러 (24개)
    "gangjin": {
        "name": "강진군청",
        "type": "고시/공고",
        "instance": GangjinCrawler(),
        "url": "https://www.gangjin.go.kr"
    },
    "gwangyang": {
        "name": "광양시청",
        "type": "고시/공고",
        "instance": GwangyangCrawler(),
        "url": "https://gwangyang.go.kr"
    },
    "goheung": {
        "name": "고흥군청",
        "type": "고시/공고",
        "instance": GoheungCrawler(),
        "url": "https://www.goheung.go.kr"
    },
    "gokseong": {
        "name": "곡성군청",
        "type": "고시/공고",
        "instance": GokseongCrawler(),
        "url": "https://www.gokseong.go.kr"
    },
    "gurye": {
        "name": "구례군청",
        "type": "고시/공고",
        "instance": GuryeCrawler(),
        "url": "https://www.gurye.go.kr"
    },
    "naju": {
        "name": "나주시청",
        "type": "고시/공고",
        "instance": NajuCrawler(),
        "url": "https://www.naju.go.kr"
    },
    "damyang": {
        "name": "담양군청",
        "type": "고시/공고",
        "instance": DamyangCrawler(),
        "url": "https://www.damyang.go.kr"
    },
    "mokpo": {
        "name": "목포시청",
        "type": "공고",
        "instance": MokpoCrawler(),
        "url": "https://www.mokpo.go.kr"
    },
    "muan": {
        "name": "무안군청",
        "type": "공고",
        "instance": MuanCrawler(),
        "url": "https://www.muan.go.kr"
    },
    "boseong": {
        "name": "보성군청",
        "type": "공고",
        "instance": BoseongCrawler(),
        "url": "https://www.boseong.go.kr"
    },
    "suncheon": {
        "name": "순천시청",
        "type": "고시/공고",
        "instance": SuncheonCrawler(),
        "url": "http://www.suncheon.go.kr"
    },
    "shinan": {
        "name": "신안군청",
        "type": "공고",
        "instance": ShinanCrawler(),
        "url": "https://www.shinan.go.kr"
    },
    "yeosu": {
        "name": "여수시청",
        "type": "통합검색",
        "instance": YeosuCrawler(),
        "url": "https://www.yeosu.go.kr"
    },
    "yeonggwang": {
        "name": "영광군청",
        "type": "고시공고",
        "instance": YeonggwangCrawler(),
        "url": "https://www.yeonggwang.go.kr"
    },
    "yeongam": {
        "name": "영암군청",
        "type": "공고",
        "instance": YeongamCrawler(),
        "url": "https://www.yeongam.go.kr"
    },
    "wando": {
        "name": "완도군청",
        "type": "고시/공고",
        "instance": WandoCrawler(),
        "url": "https://www.wando.go.kr"
    },
    "jangseong": {
        "name": "장성군청",
        "type": "공고",
        "instance": JangseongCrawler(),
        "url": "https://www.jangseong.go.kr"
    },
    "jangheung": {
        "name": "장흥군청",
        "type": "통합검색",
        "instance": JangheungCrawler(),
        "url": "https://www.jangheung.go.kr"
    },
    "jindo_gosi": {
        "name": "진도군청",
        "type": "고시/공고",
        "instance": JindoGosiCrawler(),
        "url": "https://www.jindo.go.kr"
    },
    "jindo_bid": {
        "name": "진도군청",
        "type": "입찰공고",
        "instance": JindoBidCrawler(),
        "url": "https://www.jindo.go.kr"
    },
    "hampyeong_gosi": {
        "name": "함평군청",
        "type": "고시공고",
        "instance": HampyeongGosiCrawler(),
        "url": "https://www.hampyeong.go.kr"
    },
    "hampyeong_notice": {
        "name": "함평군청",
        "type": "공지사항",
        "instance": HampyeongNoticeCrawler(),
        "url": "https://www.hampyeong.go.kr"
    },
    "haenam_gosi": {
        "name": "해남군청",
        "type": "고시공고",
        "instance": HaenamGosiCrawler(),
        "url": "https://www.haenam.go.kr"
    },
    "haenam_notice": {
        "name": "해남군청",
        "type": "고시공고(게시판)",
        "instance": HaenamNoticeCrawler(),
        "url": "https://www.haenam.go.kr"
    },
    # 서울특별시 자치구 크롤러
    "mapo": {
        "name": "마포구청",
        "type": "고시공고",
        "instance": MapoCrawler(),
        "url": "https://www.mapo.go.kr"
    },
    "sdm": {
        "name": "서대문구청",
        "type": "공지사항",
        "instance": SdmCrawler(),
        "url": "https://www.sdm.go.kr"
    },
    "seocho": {
        "name": "서초구청",
        "type": "고시공고",
        "instance": SeochoCrawler(),
        "url": "https://www.seocho.go.kr"
    },
    "seongdong": {
        "name": "성동구청",
        "type": "고시공고",
        "instance": SeongdongCrawler(),
        "url": "https://www.sd.go.kr"
    },
    "seongbuk": {
        "name": "성북구청",
        "type": "고시공고",
        "instance": SeongbukCrawler(),
        "url": "https://www.sb.go.kr"
    },
    "songpa_gosi": {
        "name": "송파구청",
        "type": "고시공고",
        "instance": SongpaGosiCrawler(),
        "url": "https://www.songpa.go.kr"
    },
    "songpa_bid": {
        "name": "송파구청",
        "type": "입찰공고",
        "instance": SongpaBidCrawler(),
        "url": "http://bid.songpa.go.kr"
    },
    "yangcheon": {
        "name": "양천구청",
        "type": "고시/공고",
        "instance": YangcheonCrawler(),
        "url": "https://www.yangcheon.go.kr"
    },
    "ydp": {
        "name": "영등포구청",
        "type": "고시공고",
        "instance": YdpCrawler(),
        "url": "https://www.ydp.go.kr"
    },
    "yongsan": {
        "name": "용산구청",
        "type": "고시공고",
        "instance": YongsanCrawler(),
        "url": "https://www.yongsan.go.kr"
    },
    "eunpyeong_gosi": {
        "name": "은평구청",
        "type": "고시/공고",
        "instance": EunpyeongGosiCrawler(),
        "url": "https://www.ep.go.kr"
    },
    "eunpyeong_bid": {
        "name": "은평구청",
        "type": "입찰공고",
        "instance": EunpyeongBidCrawler(),
        "url": "https://www.ep.go.kr"
    },
    "jongno": {
        "name": "종로구청",
        "type": "고시공고",
        "instance": JongnoCrawler(),
        "url": "https://www.jongno.go.kr"
    },
    "junggu": {
        "name": "중구청",
        "type": "고시공고",
        "instance": JungguCrawler(),
        "url": "https://www.junggu.seoul.kr"
    },
    "jungnang": {
        "name": "중랑구청",
        "type": "고시공고",
        "instance": JungnangCrawler(),
        "url": "https://www.jungnang.go.kr"
    },
    # 서울 자치구 + 전남 화순 추가 (17개)
    "hwasun": {
        "name": "화순군청",
        "type": "공지사항",
        "instance": HwasunCrawler(),
        "url": "https://www.hwasun.go.kr"
    },
    "gangnam": {
        "name": "강남구청",
        "type": "고시/공고",
        "instance": GangnamCrawler(),
        "url": "https://www.gangnam.go.kr"
    },
    "gangdong": {
        "name": "강동구청",
        "type": "고시/공고",
        "instance": GangdongCrawler(),
        "url": "https://www.gangdong.go.kr"
    },
    "gangbuk": {
        "name": "강북구청",
        "type": "고시/공고",
        "instance": GangbukCrawler(),
        "url": "https://www.gangbuk.go.kr"
    },
    "gangseo_gosi": {
        "name": "강서구청",
        "type": "고시공고",
        "instance": GangseoGosiCrawler(),
        "url": "https://www.gangseo.seoul.kr"
    },
    "gangseo_bid": {
        "name": "강서구청",
        "type": "입찰공고",
        "instance": GangseoBidCrawler(),
        "url": "https://www.gangseo.seoul.kr"
    },
    "gwanak_gosi": {
        "name": "관악구청",
        "type": "고시공고",
        "instance": GwanakGosiCrawler(),
        "url": "https://www.gwanak.go.kr"
    },
    "gwanak_bid": {
        "name": "관악구청",
        "type": "입찰공고",
        "instance": GwanakBidCrawler(),
        "url": "https://www.gwanak.go.kr"
    },
    "gwangjin": {
        "name": "광진구청",
        "type": "고시공고",
        "instance": GwangjinCrawler(),
        "url": "https://www.gwangjin.go.kr"
    },
    "guro": {
        "name": "구로구청",
        "type": "고시공고",
        "instance": GuroCrawler(),
        "url": "https://www.guro.go.kr"
    },
    "geumcheon_gosi": {
        "name": "금천구청",
        "type": "고시공고",
        "instance": GeumcheonGosiCrawler(),
        "url": "https://www.geumcheon.go.kr"
    },
    "geumcheon_bid": {
        "name": "금천구청",
        "type": "입찰공고",
        "instance": GeumcheonBidCrawler(),
        "url": "https://www.geumcheon.go.kr"
    },
    "nowon": {
        "name": "노원구청",
        "type": "고시공고",
        "instance": NowonCrawler(),
        "url": "https://www.nowon.kr"
    },
    "dobong": {
        "name": "도봉구청",
        "type": "고시공고",
        "instance": DobongCrawler(),
        "url": "https://www.dobong.go.kr"
    },
    "ddm_gosi": {
        "name": "동대문구청",
        "type": "고시공고",
        "instance": DdmGosiCrawler(),
        "url": "https://www.ddm.go.kr"
    },
    "ddm_bid": {
        "name": "동대문구청",
        "type": "입찰공고",
        "instance": DdmBidCrawler(),
        "url": "https://www.ddm.go.kr"
    },
    "dongjak": {
        "name": "동작구청",
        "type": "고시공고",
        "instance": DongjakCrawler(),
        "url": "https://www.dongjak.go.kr"
    },
}

# 캐시 저장소
cache = {}
cache_lock = threading.Lock()


## ── 지역별 크롤러 그룹 ──

_CITY_TO_REGION = {
    # 서울
    '강남': '서울', '강동': '서울', '강북': '서울', '강서': '서울', '관악': '서울', '광진': '서울',
    '구로': '서울', '금천': '서울', '노원': '서울', '도봉': '서울', '동대문': '서울', '동작': '서울',
    '마포': '서울', '서대문': '서울', '서초': '서울', '성동': '서울', '성북': '서울', '송파': '서울',
    '양천': '서울', '영등포': '서울', '용산': '서울', '은평': '서울', '종로': '서울', '중구': '서울',
    '중랑': '서울', '서울': '서울',
    # 경기
    '수원': '경기', '성남': '경기', '용인': '경기', '안양': '경기', '안산': '경기', '고양': '경기',
    '과천': '경기', '광명': '경기', '구리': '경기', '군포': '경기', '김포': '경기',
    '남양주': '경기', '동두천': '경기', '부천': '경기', '시흥': '경기', '안성': '경기', '양주': '경기',
    '양평': '경기', '여주': '경기', '오산': '경기', '의왕': '경기', '의정부': '경기', '이천': '경기',
    '파주': '경기', '평택': '경기', '포천': '경기', '하남': '경기', '화성': '경기', '가평': '경기',
    '연천': '경기', '경기': '경기',
    # 인천
    '인천': '인천',
    # 부산
    '부산': '부산',
    # 대구
    '대구': '대구',
    # 광주
    '광주': '광주',
    # 대전
    '대전': '대전',
    # 울산
    '울산': '울산',
    # 세종
    '세종': '세종',
    # 강원
    '강릉': '강원', '동해': '강원', '삼척': '강원', '속초': '강원', '원주': '강원', '춘천': '강원',
    '태백': '강원', '홍천': '강원', '횡성': '강원', '영월': '강원', '평창': '강원', '정선': '강원',
    '철원': '강원', '화천': '강원', '양구': '강원', '인제': '강원', '고성': '강원', '양양': '강원',
    '강원': '강원',
    # 충북
    '청주': '충북', '충주': '충북', '제천': '충북', '보은': '충북', '옥천': '충북', '영동': '충북',
    '증평': '충북', '진천': '충북', '괴산': '충북', '음성': '충북', '단양': '충북', '충북': '충북',
    # 충남
    '천안': '충남', '공주': '충남', '보령': '충남', '아산': '충남', '서산': '충남', '논산': '충남',
    '계룡': '충남', '당진': '충남', '금산': '충남', '부여': '충남', '서천': '충남', '청양': '충남',
    '홍성': '충남', '예산': '충남', '태안': '충남', '충남': '충남',
    # 전북
    '전주': '전북', '군산': '전북', '익산': '전북', '정읍': '전북', '남원': '전북', '김제': '전북',
    '완주': '전북', '진안': '전북', '무주': '전북', '장수': '전북', '임실': '전북', '순창': '전북',
    '고창': '전북', '부안': '전북', '전북': '전북',
    # 전남
    '목포': '전남', '여수': '전남', '순천': '전남', '나주': '전남', '광양': '전남', '담양': '전남',
    '곡성': '전남', '구례': '전남', '고흥': '전남', '보성': '전남', '화순': '전남', '장흥': '전남',
    '강진': '전남', '해남': '전남', '영암': '전남', '무안': '전남', '함평': '전남', '영광': '전남',
    '장성': '전남', '완도': '전남', '진도': '전남', '신안': '전남', '전남': '전남',
    # 경북
    '포항': '경북', '경주': '경북', '김천': '경북', '안동': '경북', '구미': '경북', '영주': '경북',
    '영천': '경북', '상주': '경북', '문경': '경북', '경산': '경북', '군위': '경북', '의성': '경북',
    '청송': '경북', '영양': '경북', '영덕': '경북', '청도': '경북', '고령': '경북', '성주': '경북',
    '칠곡': '경북', '예천': '경북', '봉화': '경북', '울진': '경북', '울릉': '경북', '경북': '경북',
    # 경남
    '창원': '경남', '진주': '경남', '통영': '경남', '사천': '경남', '김해': '경남', '밀양': '경남',
    '거제': '경남', '양산': '경남', '의령': '경남', '함안': '경남', '창녕': '경남',
    '남해': '경남', '하동': '경남', '산청': '경남', '함양': '경남', '거창': '경남', '합천': '경남',
    '경남': '경남',
    # 제주
    '제주': '제주',
}

_PUBLIC_KEYWORDS = ['나라장터', '알리오', 'LH', '국가철도', '도로공사']
_DOCHUNG_KEYWORDS = ['경상북도청', '경상남도청', '전라남도청', '충청남도청', '충청북도청',
                     '경상북도개발', '충청남도개발', '새만금', '한국농어촌']

def _build_crawler_groups():
    """크롤러를 지역별로 자동 분류"""
    groups = {}
    for cid, info in CRAWLERS.items():
        name = info["name"]
        # 공공기관
        if any(k in name for k in _PUBLIC_KEYWORDS):
            groups.setdefault("공공기관", []).append(cid)
            continue
        # 광역도청/개발공사
        if any(k in name for k in _DOCHUNG_KEYWORDS):
            groups.setdefault("광역도청", []).append(cid)
            continue
        # 지역 매칭
        matched = False
        for city, region in _CITY_TO_REGION.items():
            if city in name:
                groups.setdefault(region, []).append(cid)
                matched = True
                break
        if not matched:
            groups.setdefault("기타", []).append(cid)
    return groups

CRAWLER_GROUPS = _build_crawler_groups()

# 그룹 순서 정의
GROUP_ORDER = [
    "공공기관", "서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종",
    "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주", "광역도청", "기타"
]


@app.route("/")
def index():
    """메인 대시보드 페이지 - crawler_urls DB에 등록된 검증 크롤러만 기본 표시."""
    import db
    verified_ids = set(db.get_verified_crawler_ids())
    return render_template("dashboard.html",
                           crawlers=CRAWLERS,
                           verified_ids=list(verified_ids))


@app.route("/unified")
def unified():
    """통합 검색 페이지"""
    import db
    verified_ids = set(db.get_verified_crawler_ids())
    ordered_groups = {g: CRAWLER_GROUPS.get(g, []) for g in GROUP_ORDER if g in CRAWLER_GROUPS}
    return render_template("unified.html",
                           crawlers=CRAWLERS,
                           crawler_groups=ordered_groups,
                           verified_ids=list(verified_ids))


@app.route("/api/crawler_groups")
def get_crawler_groups():
    """크롤러 그룹 목록 조회.
    ?verified_only=1 이면 crawler_urls에 등록된 검증완료 크롤러만."""
    import db
    verified_only = request.args.get("verified_only") == "1"
    verified = set(db.get_verified_crawler_ids()) if verified_only else None

    result = {}
    for g in GROUP_ORDER:
        if g not in CRAWLER_GROUPS:
            continue
        group_items = []
        for cid in CRAWLER_GROUPS[g]:
            if verified is not None and cid not in verified:
                continue
            group_items.append({
                "id": cid,
                "name": CRAWLERS[cid]["name"],
                "type": CRAWLERS[cid]["type"],
                "verified": (verified is None or cid in verified),
            })
        if group_items:  # 빈 그룹 제외
            result[g] = group_items
    return jsonify(result)


@app.route("/api/crawlers")
def get_crawlers():
    """크롤러 목록 조회.
    ?verified_only=1 이면 crawler_urls에 등록된 검증완료 크롤러만."""
    import db
    verified_only = request.args.get("verified_only") == "1"
    verified = set(db.get_verified_crawler_ids()) if verified_only else None

    crawler_list = []
    for key, info in CRAWLERS.items():
        is_verified = (key in verified) if verified is not None else False
        if verified_only and key not in verified:
            continue
        crawler_list.append({
            "id": key,
            "name": info["name"],
            "type": info["type"],
            "url": info["url"],
            "verified": is_verified,
        })
    return jsonify(crawler_list)


@app.route("/api/verified_crawlers")
def api_verified_crawlers():
    """검증된 크롤러 ID 리스트."""
    import db
    return jsonify({
        "verified_ids": db.get_verified_crawler_ids(),
        "total_registered": len(CRAWLERS),
    })


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
            if time.time() - cached["time"] < 1800:  # 30분 캐시
                return jsonify({
                    "success": True,
                    "data": cached["data"],
                    "count": len(cached["data"]),
                    "cached": True
                })

    try:
        crawler = CRAWLERS[crawler_id]["instance"]
        # 날짜 파라미터를 직접 지원하는 크롤러
        DATE_SUPPORTED = (
            "nara", "sh_bid",
            "busan_gosi", "busan_notice", "daejeon_gosi", "gangwon",
            "chungnam", "gb_notice", "gb_gosi",
            "gwangju", "incheon", "seoul_cis",
            "paju",
        )
        if crawler_id in DATE_SUPPORTED and start_date and end_date:
            results = crawler.search(keyword, max_pages=max_pages,
                                    start_date=start_date, end_date=end_date)
        else:
            results = crawler.search(keyword, max_pages=max_pages)

        # 다른 크롤러는 결과에서 날짜 필터링
        if crawler_id not in DATE_SUPPORTED and start_date and end_date:
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


@app.route("/lh/download")
def lh_download_proxy():
    """LH 파일 다운로드 프록시 - 서버가 세션 만들어 다운받아 사용자에게 스트림"""
    import requests
    from flask import Response, request as flask_request
    type_p = flask_request.args.get('type', 'REVIEW')
    pidx = flask_request.args.get('pidx', '')
    idx = flask_request.args.get('idx', '')
    if not (pidx and idx):
        return "pidx, idx 필요", 400
    try:
        s = requests.Session()
        s.headers['User-Agent'] = 'Mozilla/5.0'
        s.get('https://partner.lh.or.kr/deliberate/deliberate.asp', timeout=10)
        dl_url = f'https://partner.lh.or.kr/common/download.asp?type={type_p}&pidx={pidx}&idx={idx}'
        r = s.get(dl_url, timeout=60, stream=True)
        # 파일명, 헤더 그대로 전달
        headers = {}
        for k in ['Content-Type', 'Content-Disposition', 'Content-Length']:
            if k in r.headers:
                headers[k] = r.headers[k]
        return Response(r.iter_content(chunk_size=8192), status=r.status_code, headers=headers)
    except Exception as e:
        return f"다운로드 실패: {e}", 500


@app.route("/lh/detail/<int:idx>")
def lh_detail_redirect(idx):
    """LH 파트너몰 상세 페이지로 POST 리다이렉트 (다운로드 링크 절대화 + goHref 정의)"""
    import requests, re
    try:
        # 세션 확보
        s = requests.Session()
        s.headers['User-Agent'] = 'Mozilla/5.0'
        s.get('https://partner.lh.or.kr/deliberate/deliberate.asp', timeout=10)
        # POST로 상세 HTML 획득
        r = s.post('https://partner.lh.or.kr/deliberate/deliberate_detail.asp',
                   data={'re_idx': str(idx)}, timeout=15)
        r.encoding = 'utf-8'
        html = r.text
        # 상대 URL을 절대 URL로 변환 (/common/download.asp?... → https://partner.lh.or.kr/...)
        html = re.sub(r"goHref\('(/[^']+)'", r"goHref('https://partner.lh.or.kr\1'", html)
        # goHref 함수 정의 주입
        script = '''
<script>
function goHref(url, target){
    if(!url){ alert("오픈 준비중입니다."); return; }
    if(!target){ location.href = url; }
    else { window.open(url, target); }
}
</script>
'''
        return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>LH 자재·공법 심의 상세</title>
<link rel="stylesheet" href="https://partner.lh.or.kr/css/common.css">
{script}
</head><body>{html}</body></html>'''
    except Exception as e:
        # 폴백: 브라우저에서 fetch로 POST + goHref 주입
        return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>LH 자재·공법 심의 상세</title>
<link rel="stylesheet" href="https://partner.lh.or.kr/css/common.css">
<script>
function goHref(url, target){{
    if(!url){{ alert("오픈 준비중입니다."); return; }}
    if(!target){{ location.href = url; }}
    else {{ window.open(url, target); }}
}}
window.addEventListener('DOMContentLoaded', async () => {{
    try {{
        const formData = new URLSearchParams();
        formData.append('re_idx', '{idx}');
        const res = await fetch('https://partner.lh.or.kr/deliberate/deliberate_detail.asp', {{
            method: 'POST', body: formData, credentials: 'include',
            headers: {{'Content-Type': 'application/x-www-form-urlencoded'}}
        }});
        let html = await res.text();
        // 다운로드 링크를 우리 서버 프록시로 변환 (세션 문제 우회)
        html = html.replace(
            /<a[^>]*onclick="goHref\\('\\/common\\/download\\.asp\\?([^']+)'[^"]*"[^>]*>/g,
            function(m, params){{ return '<a href="/lh/download?' + params.replace(/&amp;/g, '&') + '" target="_blank">'; }}
        );
        // 그 외 상대 링크는 절대화
        html = html.replace(/goHref\\('\\/([^']+)'/g, "goHref('https://partner.lh.or.kr/$1'");
        document.getElementById('lh_content').innerHTML = html;
    }} catch (e) {{
        document.getElementById('lh_content').innerHTML = '<p>로드 실패. <a href="https://partner.lh.or.kr/deliberate/deliberate.asp">LH 목록으로</a></p>';
    }}
}});
</script>
</head><body><div id="lh_content"><p>로딩 중...</p></div></body></html>'''


@app.route("/api/search_all")
def search_all():
    """DB에서 통합 검색 (SQLite 기반)"""
    import db

    keyword = request.args.get("keyword", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    crawler_ids_param = request.args.get("crawler_ids", "")

    if not keyword:
        return jsonify({"error": "검색어를 입력해주세요"}), 400

    crawler_ids = crawler_ids_param.split(",") if crawler_ids_param else None

    # DB 검색 (밀리초 단위)
    rows = db.search(
        keyword=keyword,
        start_date=start_date or None,
        end_date=end_date or None,
        crawler_ids=crawler_ids,
        limit=10000,
    )

    # 크롤러별로 결과 그룹화 (기존 응답 형식 호환)
    results = {}
    for row in rows:
        cid = row["crawler_id"]
        if cid not in results:
            results[cid] = []
        results[cid].append({
            "title": row["title"],
            "date": row["date"],
            "url": row["url"],
            "organization": row["organization"],
            "number": row["number"],
            "deadline": row["deadline"],
        })

    summary = {}
    for cid, items in results.items():
        crawler = CRAWLERS.get(cid, {})
        summary[cid] = {
            "name": f"{crawler.get('name', cid)} ({crawler.get('type', '')})",
            "count": len(items),
            "error": None,
        }

    return jsonify({
        "success": True,
        "keyword": keyword,
        "results": results,
        "summary": summary,
        "total_count": len(rows),
        "errors": {},
        "from_db": True,  # DB에서 가져온 결과임을 표시
    })


def warmup_cookies():
    """서버 시작 시 알리오 쿠키 미리 획득"""
    def _warmup():
        try:
            print("[웜업] 알리오 쿠키 획득 중...")
            crawler = AlioCrawler()
            crawler.search("", max_pages=1)
            print("[웜업] 알리오 쿠키 획득 완료!")
        except Exception as e:
            print(f"[웜업] 실패: {e}")

    threading.Thread(target=_warmup, daemon=True).start()


# 느린 크롤러 백그라운드 프리패치
SLOW_CRAWLERS = [
    "gjcity_gosi", "gjcity_bid", "pyeongtaek_gosi", "pyeongtaek_bid",
    "gwangmyeong_gosi", "gwangmyeong_bid", "ansan_gosi", "ansan_bid",
    "uijeongbu_gosi", "uijeongbu_bid", "siheung_gosi", "siheung_bid",
    "dongducheon_gosi", "dongducheon_bid", "gimpo_gosi", "gimpo_bid",
    "yangpyeong", "yeoju_bid", "anseong_gosi", "uiwang_gosi",
    "icheon_gosi", "icheon_bid", "pocheon_gosi", "pocheon_bid",
]
PREFETCH_KEYWORDS = ["공고", "용역"]
PREFETCH_INTERVAL = 1800  # 30분마다 갱신


def prefetch_slow_crawlers():
    """느린 크롤러를 백그라운드에서 주기적으로 프리패치"""
    def _prefetch():
        while True:
            for crawler_id in SLOW_CRAWLERS:
                if crawler_id not in CRAWLERS:
                    continue
                crawler = CRAWLERS[crawler_id]["instance"]
                for keyword in PREFETCH_KEYWORDS:
                    cache_key = f"{crawler_id}:{keyword}:1000::"
                    try:
                        results = crawler.search(keyword, max_pages=1000)
                        with cache_lock:
                            cache[cache_key] = {
                                "data": results,
                                "time": time.time()
                            }
                        print(f"[프리패치] {crawler_id} '{keyword}': {len(results)}건")
                    except Exception as e:
                        print(f"[프리패치] {crawler_id} '{keyword}' 실패: {e}")
            print(f"[프리패치] 완료. {PREFETCH_INTERVAL}초 후 재실행")
            time.sleep(PREFETCH_INTERVAL)

    threading.Thread(target=_prefetch, daemon=True).start()


def setup_scheduler():
    """APScheduler 설정:
    - 1시간마다 전체 크롤러 수집
    - 30분마다 알리오 입찰만 추가 수집 (시간 차이로 인한 누락 방지)
    """
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    import db, collector

    db.init_db()

    def scheduled_collect_all():
        try:
            print(f"[Scheduler] 전체 자동 수집 시작...")
            result = collector.collect_all(CRAWLERS, days=30, max_workers=10, verbose=False)
            print(f"[Scheduler] 완료: 성공 {result['success']}, 에러 {result['error']}, 신규 {result['new']}건")
        except Exception as e:
            print(f"[Scheduler] 에러: {e}")

    def scheduled_collect_alio():
        """알리오 입찰만 30분 주기로 수집 (변동 빈도 높음)"""
        try:
            if "alio" not in CRAWLERS:
                return
            print(f"[Scheduler] 알리오 추가 수집 시작...")
            cid, name, count, new, err = collector.collect_one("alio", CRAWLERS["alio"], days=30)
            print(f"[Scheduler] 알리오 완료: 수집 {count}건, 신규 {new}건" + (f", 에러: {err[:50]}" if err else ""))
        except Exception as e:
            print(f"[Scheduler] 알리오 에러: {e}")

    scheduler = BackgroundScheduler(daemon=True)

    # 전체 1시간 주기
    scheduler.add_job(
        scheduled_collect_all,
        trigger=IntervalTrigger(hours=1),
        id="auto_collect_all",
        name="전체 크롤러 자동 수집",
        max_instances=1,
        coalesce=True,
    )

    # 알리오만 30분 주기 (전체 수집과 겹치지 않도록 minute=30 시작)
    scheduler.add_job(
        scheduled_collect_alio,
        trigger=IntervalTrigger(minutes=30),
        id="auto_collect_alio",
        name="알리오 입찰 추가 수집",
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    print("[Scheduler] 등록: 전체 1시간 + 알리오 30분 주기")
    return scheduler


@app.route("/api/db_stats")
def api_db_stats():
    """DB 통계 조회"""
    import db
    return jsonify(db.get_stats())


@app.route("/health")
def health_check():
    """헬스체크 - Fly.io/Render/K8s 등 로드밸런서용."""
    import db
    try:
        with db.get_conn() as conn:
            conn.cursor().execute("SELECT 1").fetchone()
        return {"status": "ok", "db": "connected", "version": "a02d7a7"}, 200
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}, 503


@app.route("/api/admin/seed", methods=["POST"])
@require_admin_token
def api_admin_seed():
    """crawler_urls seed 수동 트리거. 재배포마다 DB 초기화되는 무료플랜용."""
    try:
        import seed_crawler_urls
        seed_crawler_urls.seed()
        import db
        urls = db.get_crawler_urls()
        return jsonify({"ok": True, "urls_count": len(urls)})
    except Exception as e:
        import traceback
        return jsonify({"ok": False, "error": str(e)[:200], "trace": traceback.format_exc()[:500]}), 500


@app.route("/api/manual_collect", methods=["POST"])
@require_admin_token
def api_manual_collect():
    """수동 수집 트리거"""
    import collector, threading
    days = int(request.args.get("days", 30))

    def run():
        collector.collect_all(CRAWLERS, days=days, max_workers=10, verbose=False)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"started": True, "days": days})


# ========================================================================
# xlsx 요구 기능: 관리자 페이지 + API (5개 기능)
# ========================================================================

@app.route("/admin")
@require_admin_token
def admin_page():
    """관리자 페이지 - xlsx 5개 요구기능 통합 UI."""
    return render_template("admin.html")


# ---------- ① 검색어 관리 ----------

@app.route("/api/keywords", methods=["GET"])
def api_keywords_list():
    """검색어 전체 조회. xlsx 기본 25개 + 사용자 커스텀."""
    import db
    return jsonify(db.get_keywords())


@app.route("/api/keywords", methods=["POST"])
@require_admin_token
def api_keywords_add():
    """검색어 추가 (사용자 커스텀)."""
    import db
    kw = (request.json or {}).get("keyword", "").strip()
    if not kw:
        return jsonify({"ok": False, "error": "keyword required"}), 400
    if db.add_keyword(kw):
        return jsonify({"ok": True, "keyword": kw})
    return jsonify({"ok": False, "error": "duplicate or invalid"}), 409


@app.route("/api/keywords/<int:kw_id>", methods=["DELETE"])
@require_admin_token
def api_keywords_delete(kw_id):
    """검색어 삭제 (기본 xlsx 25개는 삭제 불가)."""
    import db
    if db.delete_keyword(kw_id):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "cannot delete (default or not found)"}), 400


# ---------- ② 게시판 링크 관리 ----------

@app.route("/api/urls", methods=["GET"])
def api_urls_list():
    """크롤러 URL 조회 + 실패 알림 정보 병합."""
    import db
    cid = request.args.get("crawler_id")
    active = request.args.get("active_only") == "1"
    urls = db.get_crawler_urls(crawler_id=cid, active_only=active)

    # 각 URL에 실패 정보 추가
    failure_info = db.get_crawler_failure_info()
    for u in urls:
        info = failure_info.get(u['crawler_id'], {})
        u['warn'] = info.get('warn', False)
        u['last_error'] = info.get('last_error')
        u['last_run_at'] = info.get('last_run_at')
        u['hours_since_run'] = info.get('hours_since_run')
        u['last_count'] = info.get('last_count')

    return jsonify(urls)


@app.route("/api/urls", methods=["POST"])
@require_admin_token
def api_urls_upsert():
    """URL 추가/수정."""
    import db
    d = request.json or {}
    crawler_id = d.get("crawler_id", "").strip()
    board_key = d.get("board_key", "").strip() or "default"
    url = d.get("url", "").strip()
    if not (crawler_id and url):
        return jsonify({"ok": False, "error": "crawler_id and url required"}), 400
    db.upsert_crawler_url(
        crawler_id=crawler_id,
        crawler_name=d.get("crawler_name") or crawler_id,
        board_key=board_key,
        board_name=d.get("board_name") or "",
        url=url,
        fallback_url=d.get("fallback_url"),
        is_active=int(d.get("is_active", 1)),
        priority=int(d.get("priority", 0)),
        notes=d.get("notes"),
    )
    return jsonify({"ok": True})


@app.route("/api/urls/<int:url_id>", methods=["DELETE"])
@require_admin_token
def api_urls_delete(url_id):
    """URL 삭제."""
    import db
    if db.delete_crawler_url(url_id):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "not found"}), 404


# ---------- ③ 링크 검증 (잘못된 링크 감지) ----------

@app.route("/api/urls/validate", methods=["POST"])
@require_admin_token
def api_urls_validate():
    """URL 유효성 검증. 크롤러 세션(특수 헤더/TLS/쿠키) 재사용해 실제 크롤과 동일한 방식으로 검증.
    개별 URL 또는 전체 크롤러."""
    import db, threading
    d = request.json or {}
    crawler_id = d.get("crawler_id")

    def do_check(target_urls):
        for u_row in target_urls:
            cid = u_row["crawler_id"]
            # 크롤러 세션 재사용 (특수 헤더/어댑터/쿠키 포함)
            session = None
            if cid in CRAWLERS:
                inst = CRAWLERS[cid].get("instance")
                if inst is not None and hasattr(inst, "session"):
                    session = inst.session
            status, err = db.check_url_alive(u_row["url"], crawler_session=session)
            db.record_link_status(
                crawler_id=cid,
                url=u_row["url"],
                is_valid=(status == 200 and err is None),
                http_status=status,
                error_msg=err,
            )

    urls = db.get_crawler_urls(crawler_id=crawler_id, active_only=True)
    if not urls:
        return jsonify({"ok": False, "error": "no urls"}), 404
    # 백그라운드 실행
    threading.Thread(target=do_check, args=(urls,), daemon=True).start()
    return jsonify({"ok": True, "queued": len(urls), "method": "crawler_session"})


@app.route("/api/urls/status", methods=["GET"])
def api_urls_status():
    """URL 검증 결과 조회. invalid_only=1이면 실패한 것만."""
    import db
    cid = request.args.get("crawler_id")
    invalid = request.args.get("invalid_only") == "1"
    return jsonify(db.get_link_status(crawler_id=cid, invalid_only=invalid))


# ---------- ④ 통합검색 폴백 ----------

@app.route("/api/search_with_fallback/<crawler_id>", methods=["GET"])
def api_search_with_fallback(crawler_id):
    """지정 게시판 실패 시 폴백 URL 자동 사용."""
    import db
    if crawler_id not in CRAWLERS:
        return jsonify({"error": "unknown crawler"}), 404
    kw = request.args.get("keyword", "").strip()

    # 1) DB 검색 우선 (빠름)
    items = db.search(keyword=kw, crawler_ids=[crawler_id], limit=1000)
    if items:
        return jsonify({
            "source": "db",
            "crawler_id": crawler_id,
            "count": len(items),
            "items": items,
        })

    # 2) 실패 시 크롤러 URL 체크 → 폴백 확인
    urls = db.get_crawler_urls(crawler_id=crawler_id, active_only=True)
    for u in urls:
        st = db.get_link_status(crawler_id=crawler_id)
        # 이 URL의 상태
        bad = [s for s in st if s["url"] == u["url"] and s["is_valid"] == 0]
        if bad and u.get("fallback_url"):
            # 폴백 URL 반환 (사용자가 클릭)
            return jsonify({
                "source": "fallback",
                "crawler_id": crawler_id,
                "fallback_url": u["fallback_url"],
                "message": f"지정 URL 실패({bad[0]['error_msg']}) - 폴백 URL 제공",
                "items": [],
            })

    return jsonify({
        "source": "db_empty",
        "crawler_id": crawler_id,
        "count": 0,
        "items": [],
    })


# ---------- ⑤ 결과 내 추가검색 (title 필터) ----------

@app.route("/api/search_filter", methods=["POST"])
def api_search_filter():
    """이미 크롤한 DB 결과에서 title 다중 필터로 재검색.
    body: { keywords: [...], crawler_ids: [...], mode: 'and'|'or' }
    """
    import db
    d = request.json or {}
    keywords = d.get("keywords") or []
    crawler_ids = d.get("crawler_ids") or None
    mode = d.get("mode", "or").lower()

    if not keywords:
        # 그냥 전체
        items = db.search(crawler_ids=crawler_ids, limit=10000)
    else:
        # 여러 키워드 각각 조회 후 병합
        all_items = {}
        for kw in keywords:
            for it in db.search(keyword=kw, crawler_ids=crawler_ids, limit=10000):
                key = (it["crawler_id"], it["url"])
                if mode == "or":
                    all_items[key] = it
                else:  # and: 모든 키워드가 title에 있어야
                    all_items.setdefault(key, {"item": it, "hits": set()})
                    if isinstance(all_items[key], dict) and "hits" in all_items[key]:
                        all_items[key]["hits"].add(kw)

        if mode == "and":
            required = set(keywords)
            items = [v["item"] for v in all_items.values()
                     if isinstance(v, dict) and v.get("hits") == required]
        else:
            items = list(all_items.values())

    return jsonify({
        "keywords": keywords,
        "mode": mode,
        "count": len(items),
        "items": items,
    })


# ============================================================================
# 모듈 로드 시 항상 초기화 (gunicorn/uwsgi 등 프로덕션 WSGI 서버 호환)
# 이전엔 if __name__ 안에만 있어서 gunicorn 실행 시 스케줄러 미동작 버그
# ============================================================================
_SCHEDULER_INITIALIZED = False


def _init_app_on_load():
    """모듈 import 시 1회 실행. gunicorn/flask run 모두에서 스케줄러 활성."""
    global _SCHEDULER_INITIALIZED
    if _SCHEDULER_INITIALIZED:
        return
    _SCHEDULER_INITIALIZED = True
    try:
        import db
        db.init_db()
        # 검증된 크롤러 URL seed (crawler_urls 비어있으면)
        if not db.get_verified_crawler_ids():
            try:
                import seed_crawler_urls
                seed_crawler_urls.seed()
            except Exception as e:
                print(f"[init] seed 실패: {e}")
        # 알리오 쿠키 웜업 + 스케줄러 등록
        try:
            warmup_cookies()
        except Exception as e:
            print(f"[init] warmup 실패: {e}")
        try:
            setup_scheduler()
        except Exception as e:
            print(f"[init] scheduler 실패: {e}")
        # 느린 크롤러 프리페치는 개발서버 무거워서 skip (원하면 활성화)
        # prefetch_slow_crawlers()
    except Exception as e:
        print(f"[init] 초기화 오류: {e}")


# 모듈 로드 즉시 실행 (gunicorn worker 프로세스 각각)
_init_app_on_load()


if __name__ == "__main__":
    # 개발 서버 (직접 실행 시)
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5001)),
            threaded=True, use_reloader=False)
