# -*- coding: utf-8 -*-
"""
나라장터(G2B) 입찰공고 크롤러
공공데이터포털 Open API 사용
"""
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# API 설정
API_KEY = "dda419df735cfb226cff2561e3fd9eca16b0eda9730135bdbbca9a30510aa1d8"
BASE_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"


def search_nara(keyword: str = None, bid_type: str = "용역", days: int = 30, num_rows: int = 100,
                start_date_str: str = None, end_date_str: str = None, search_all_types: bool = False):
    """
    나라장터 입찰공고 검색 (Open API)

    Args:
        keyword: 검색 키워드 (공고명에 포함된 텍스트)
        bid_type: 입찰 유형 ("용역", "공사", "물품", "외자")
        days: 최근 며칠간의 공고 조회 (기본 30일, start/end_date_str이 없을 때 사용)
        num_rows: 조회할 결과 수 (기본 100건)
        start_date_str: 시작일 (YYYY-MM-DD 형식, 선택)
        end_date_str: 종료일 (YYYY-MM-DD 형식, 선택)
        search_all_types: True면 용역/공사/물품 모두 검색

    Returns:
        검색 결과 리스트
    """
    # 모든 유형 검색 (용역 + 공사 병렬 처리)
    if search_all_types:
        all_results = []
        bid_types = ["용역", "공사"]  # 물품 제외

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(
                    search_nara, keyword, btype, days, num_rows,
                    start_date_str, end_date_str, False
                ): btype for btype in bid_types
            }
            for future in as_completed(futures):
                all_results.extend(future.result())

        return all_results

    # 업무 유형별 API 엔드포인트
    endpoints = {
        "용역": "/getBidPblancListInfoServcPPSSrch",
        "공사": "/getBidPblancListInfoCnstwkPPSSrch",
        "물품": "/getBidPblancListInfoThngPPSSrch",
        "외자": "/getBidPblancListInfoFrgcptPPSSrch",
    }

    endpoint = endpoints.get(bid_type, endpoints["용역"])
    url = BASE_URL + endpoint

    # 날짜 범위 설정
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    else:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

    # API 최대 조회 기간 28일 제한 → 28일 단위로 분할 병렬 조회
    total_days = (end_date - start_date).days
    if total_days > 28:
        print(f"[조회] {bid_type} 입찰공고 ({start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}) → {total_days}일, 28일 단위 분할")
        chunks = []
        chunk_start = start_date
        while chunk_start < end_date:
            chunk_end = min(chunk_start + timedelta(days=27), end_date)
            chunks.append((chunk_start.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
            chunk_start = chunk_end + timedelta(days=1)

        all_chunk_results = []
        with ThreadPoolExecutor(max_workers=min(len(chunks), 4)) as executor:
            futures = {
                executor.submit(
                    search_nara, keyword, bid_type, days, num_rows,
                    cs, ce, False
                ): (cs, ce) for cs, ce in chunks
            }
            for future in as_completed(futures):
                all_chunk_results.extend(future.result())

        # 중복 제거
        deduplicated = {}
        for item in all_chunk_results:
            b_no = item["bid_no"]
            b_order = item["bid_order"]
            if b_no not in deduplicated or b_order > deduplicated[b_no]["bid_order"]:
                deduplicated[b_no] = item
        results = list(deduplicated.values())
        results.sort(key=lambda x: x.get("date", ""), reverse=True)
        print(f"[완료] {bid_type} {len(results)}건 (분할조회)")
        return results

    print(f"[조회] {bid_type} 입찰공고 ({start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')})")

    results = []
    page_no = 1
    rows_per_page = 999  # API 최대값

    try:
        while True:
            params = {
                "serviceKey": API_KEY,
                "numOfRows": str(rows_per_page),
                "pageNo": str(page_no),
                "inqryDiv": "1",
                "inqryBgnDt": start_date.strftime("%Y%m%d") + "0000",
                "inqryEndDt": end_date.strftime("%Y%m%d") + "2359",
                "type": "json",
            }

            # 키워드가 있으면 API에서 직접 필터링
            if keyword:
                params["bidNtceNm"] = keyword

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "response" not in data:
                print(f"[오류] 응답 형식 오류")
                break

            header = data["response"].get("header", {})
            if header.get("resultCode") != "00":
                print(f"[오류] {header.get('resultMsg', '알 수 없는 오류')}")
                break

            body = data["response"].get("body", {})
            total_count = body.get("totalCount", 0)
            items = body.get("items", [])

            if not items:
                break

            if isinstance(items, dict):
                items = [items]

            for item in items:
                title = item.get("bidNtceNm", "")

                # 키워드 필터링
                if keyword and keyword not in title:
                    continue

                bid_no = item.get("bidNtceNo", "")
                bid_order = item.get("bidNtceOrd", "")

                # API에서 제공하는 공고 상세 URL 사용
                link = item.get("bidNtceDtlUrl", "") or item.get("bidNtceUrl", "")

                results.append({
                    "bid_no": bid_no,
                    "bid_order": bid_order,
                    "title": title,
                    "organization": item.get("dminsttNm", ""),
                    "announce_org": item.get("ntceInsttNm", ""),
                    "date": item.get("bidNtceDt", ""),
                    "deadline": item.get("bidClseDt", ""),
                    "open_date": item.get("opengDt", ""),
                    "method": item.get("bidMethdNm", ""),
                    "contract": item.get("cntrctCnclsMthdNm", ""),
                    "manager": item.get("ntceInsttOfclNm", ""),
                    "phone": item.get("ntceInsttOfclTelNo", ""),
                    "type": bid_type,
                    "url": link,
                })

            # 모든 페이지 조회 완료 확인
            fetched = page_no * rows_per_page
            if fetched >= total_count:
                break
            # num_rows 제한은 키워드 필터링 후 결과에 적용
            if len(results) >= num_rows:
                break

            page_no += 1
            if page_no > 100:  # 안전장치: 최대 100페이지
                break

        # 중복 제거: 같은 공고번호는 최신 버전만 유지
        deduplicated = {}
        for item in results:
            b_no = item["bid_no"]
            b_order = item["bid_order"]
            if b_no not in deduplicated or b_order > deduplicated[b_no]["bid_order"]:
                deduplicated[b_no] = item

        results = list(deduplicated.values())
        # 날짜순 정렬 (최신순)
        results.sort(key=lambda x: x.get("date", ""), reverse=True)

        print(f"[완료] {bid_type} {len(results)}건 검색됨")
        return results

    except requests.exceptions.RequestException as e:
        print(f"[오류] API 요청 실패: {e}")
        return results
    except Exception as e:
        print(f"[오류] {e}")
        return results


def search_all_types(keyword: str = None, days: int = 30, start_date_str: str = None, end_date_str: str = None):
    """모든 유형(용역, 공사, 물품) 검색"""
    return search_nara(keyword, days=days, start_date_str=start_date_str,
                       end_date_str=end_date_str, search_all_types=True)


def main():
    """테스트 실행"""
    import sys

    # 커맨드라인 인자 또는 입력
    if len(sys.argv) > 1:
        keyword = sys.argv[1]
    else:
        keyword = input("검색 키워드 (Enter=전체): ").strip() or None

    print(f"\n{'='*60}")
    print(f" 나라장터 입찰공고 검색 (Open API)")
    print(f" 키워드: {keyword or '전체'}")
    print(f"{'='*60}\n")

    # 용역 입찰공고 검색
    results = search_nara(keyword, bid_type="용역", days=30)

    print(f"\n{'='*60}")
    print(f" 검색 결과: {len(results)}건")
    print(f"{'='*60}\n")

    for i, r in enumerate(results[:10], 1):  # 상위 10건만 출력
        print(f"{i}. {r['title']}")
        print(f"   공고번호: {r['bid_no']}-{r['bid_order']}")
        print(f"   수요기관: {r['organization']}")
        print(f"   공고일: {r['date']}")
        print(f"   마감일: {r['deadline']}")
        print(f"   계약방법: {r['contract']}")
        print()

    if len(results) > 10:
        print(f"... 외 {len(results) - 10}건")


if __name__ == "__main__":
    main()
