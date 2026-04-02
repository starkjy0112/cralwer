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
    with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
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
