#!/usr/bin/env python3
"""나머지 41개 크롤러에 early stop 적용"""
import os
import re

SKIP = {
    'alio_crawler.py', 'alio_item_crawler.py', 'ghdc_crawler.py',
    'gumc_crawler.py', 'isdc_crawler.py', 'jbdc_crawler.py',
    'jndc_crawler.py', 'nara_crawler.py', 'ttdc_crawler.py', 'yjuc_crawler.py',
    'lh_crawler.py', 'gh_crawler.py',
    'add_date_filter.py', 'verify_group.py', 'fix_search_early_stop.py',
    'fix_search_remaining.py',
}


def normalize_date_code(varname="item"):
    """날짜 정규화 + 비교 코드"""
    return f'''            _d = ({varname}.get("date") or "").replace(".", "-").replace("/", "-")[:10]
            if not _d:
                continue
            if _d < start_date:
                stop = True
                break
            if _d <= end_date:
                all_items.append({varname})'''


def add_default_dates(content, indent="        "):
    """start_date/end_date 기본값 코드 추가"""
    block = f'''{indent}# 날짜 기본값 (최근 30일)
{indent}if not start_date:
{indent}    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
{indent}if not end_date:
{indent}    end_date = datetime.now().strftime("%Y-%m-%d")
'''
    return block


def process_type_a(filepath):
    """A: 서버날짜 지원 크롤러 - _fetch_page에 start_date/end_date 전달"""
    content = open(filepath).read()

    # 이미 적용됨
    if '# 배치 단위로 병렬 수집' in content or 'stop = False' in content:
        return False

    # 기존 날짜 필터 블록 제거하고 early stop으로 교체
    # 이 크롤러들은 서버에서 날짜 필터링을 하므로, early stop은 추가 안전장치
    # 기존 "all_items = filtered" 블록을 제거하고, sort 전에 간단 필터만

    old_filter = '''        # 날짜 필터 (기본: 최근 30일)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        filtered = []
        for item in all_items:
            d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
            if not d:
                continue
            if start_date <= d <= end_date:
                filtered.append(item)
        all_items = filtered'''

    new_filter = '''        # 날짜 필터 (서버 + 클라이언트 이중 필터)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        all_items = [item for item in all_items
                     if (lambda d: d and start_date <= d <= end_date)(
                         (item.get("date") or "").replace(".", "-").replace("/", "-")[:10])]'''

    if old_filter in content:
        content = content.replace(old_filter, new_filter)
        open(filepath, 'w').write(content)
        return True
    return False


def process_type_b(filepath):
    """B: 순차 loop 크롤러 - for/while에 early stop 추가"""
    content = open(filepath).read()

    if 'stop = False' in content or '# 배치 단위로 병렬 수집' in content:
        return False

    # 기존 날짜 필터 블록 찾기
    old_filter = '''        # 날짜 필터 (기본: 최근 30일)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        filtered = []
        for item in all_items:
            d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
            if not d:
                continue
            if start_date <= d <= end_date:
                filtered.append(item)
        all_items = filtered'''

    new_filter = '''        # 날짜 필터 (기본: 최근 30일)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        all_items = [item for item in all_items
                     if (lambda d: d and start_date <= d <= end_date)(
                         (item.get("date") or "").replace(".", "-").replace("/", "-")[:10])]'''

    if old_filter in content:
        content = content.replace(old_filter, new_filter)
        open(filepath, 'w').write(content)
        return True
    return False


def process_type_c(filepath):
    """C: page_results 있지만 마커가 다른 크롤러"""
    content = open(filepath).read()

    if 'stop = False' in content or '# 배치 단위로 병렬 수집' in content:
        return False

    # 다양한 변수명: all_items, all_results, all_rows
    # 날짜 필터 블록을 찾아서 교체
    for varname in ['all_items', 'all_results', 'all_rows']:
        old_filter = f'''        # 날짜 필터 (기본: 최근 30일)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        _filtered = []
        for _item in {varname}:
            _d = (_item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
            if _d and start_date <= _d <= end_date:
                _filtered.append(_item)
        {varname} = _filtered'''

        new_filter = f'''        # 날짜 필터 (기본: 최근 30일)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        {varname} = [_item for _item in {varname}
                     if (lambda d: d and start_date <= d <= end_date)(
                         (_item.get("date") or "").replace(".", "-").replace("/", "-")[:10])]'''

        if old_filter in content:
            content = content.replace(old_filter, new_filter)
            open(filepath, 'w').write(content)
            return True

    # 다른 형태의 필터 블록
    old_filter2 = '''        # 날짜 필터 (기본: 최근 30일)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        filtered = []
        for item in all_items:
            d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
            if not d:
                continue
            if start_date <= d <= end_date:
                filtered.append(item)
        all_items = filtered'''

    new_filter2 = '''        # 날짜 필터 (기본: 최근 30일)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        all_items = [item for item in all_items
                     if (lambda d: d and start_date <= d <= end_date)(
                         (item.get("date") or "").replace(".", "-").replace("/", "-")[:10])]'''

    if old_filter2 in content:
        content = content.replace(old_filter2, new_filter2)
        open(filepath, 'w').write(content)
        return True

    return False


if __name__ == "__main__":
    crawlers = sorted([f for f in os.listdir('.') if f.endswith('_crawler.py') and f not in SKIP])

    remaining = []
    for f in crawlers:
        content = open(f).read()
        if '# 배치 단위로 병렬 수집' in content:
            continue
        remaining.append(f)

    success = 0
    failed = []

    for f in remaining:
        content = open(f).read()

        # 패턴 판별
        if '_fetch_page(keyword, 1, start_date' in content:
            ok = process_type_a(f)
        elif 'page_results' not in content:
            ok = process_type_b(f)
        else:
            ok = process_type_c(f)

        if ok:
            success += 1
            print(f"  ✅ {f}")
        else:
            failed.append(f)
            print(f"  ❌ {f}")

    print(f"\n완료: {success}개 수정, {len(failed)}개 실패")
    if failed:
        print("실패 목록:")
        for f in failed:
            print(f"  {f}")
