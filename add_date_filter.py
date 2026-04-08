#!/usr/bin/env python3
"""332개 _fetch_page 크롤러에 날짜 필터 일괄 적용 스크립트"""
import os
import re

# _fetch_page 없는 크롤러 (제외)
SKIP = {
    'alio_crawler.py', 'alio_item_crawler.py', 'ghdc_crawler.py',
    'gumc_crawler.py', 'isdc_crawler.py', 'jbdc_crawler.py',
    'jndc_crawler.py', 'nara_crawler.py', 'ttdc_crawler.py', 'yjuc_crawler.py',
    'lh_crawler.py',  # async 기반
    'add_date_filter.py', 'verify_group.py',  # 유틸
}

# 이미 start_date가 있는 크롤러 (시그니처만 이미 있음)
ALREADY_HAS = {
    'busan_gosi_crawler.py', 'busan_notice_crawler.py', 'chungnam_crawler.py',
    'daejeon_gosi_crawler.py', 'gangwon_crawler.py', 'gb_gosi_crawler.py',
    'gb_notice_crawler.py', 'gwangju_crawler.py', 'incheon_crawler.py',
    'jungnang_crawler.py', 'paju_crawler.py', 'seongbuk_crawler.py',
    'seoul_cis_crawler.py', 'sh_bid_crawler.py',
}

# 날짜 import 추가 텍스트
DATE_IMPORT = "from datetime import datetime, timedelta"

# search 메서드에 추가할 날짜 필터 코드
DATE_FILTER_CODE = '''
        # 날짜 필터 (기본: 최근 30일)
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
        all_items = filtered
'''

def process_file(filepath):
    """개별 크롤러 파일 처리"""
    with open(filepath, 'r') as f:
        content = f.read()

    filename = os.path.basename(filepath)
    modified = False

    # 1. datetime import 추가 (없으면)
    if 'from datetime import' not in content:
        # 기존 import 블록 뒤에 추가
        if 'import re' in content:
            content = content.replace('import re', f'import re\n{DATE_IMPORT}', 1)
        elif 'import math' in content:
            content = content.replace('import math', f'import math\n{DATE_IMPORT}', 1)
        elif 'from bs4' in content:
            content = content.replace('from bs4', f'{DATE_IMPORT}\nfrom bs4', 1)
        else:
            content = DATE_IMPORT + '\n' + content
        modified = True

    # 2. search() 시그니처에 start_date, end_date 추가
    if filename not in ALREADY_HAS:
        # 다양한 시그니처 패턴 매칭
        patterns = [
            (r'def search\(self, keyword="", max_pages=(\d+)\):',
             r'def search(self, keyword="", max_pages=\1, start_date=None, end_date=None):'),
            (r'def search\(self, keyword: str = "", max_pages: int = (\d+)\):',
             r'def search(self, keyword: str = "", max_pages: int = \1, start_date=None, end_date=None):'),
            (r'def search\(self, keyword: str = "", max_pages: int = (\d+)\) -> list\[dict\]:',
             r'def search(self, keyword: str = "", max_pages: int = \1, start_date=None, end_date=None) -> list[dict]:'),
            (r'def search\(self, keyword: str = "", max_pages: int = (\d+)\) -> List\[Dict\]:',
             r'def search(self, keyword: str = "", max_pages: int = \1, start_date=None, end_date=None) -> List[Dict]:'),
            (r'def search\(self, keyword: str = "", search_field: str = "(\w+)", max_pages: int = (\d+)\):',
             r'def search(self, keyword: str = "", search_field: str = "\1", max_pages: int = \2, start_date=None, end_date=None):'),
            (r'def search\(self, keyword: str = "", search_item: str = "", max_pages: int = (\d+)\):',
             r'def search(self, keyword: str = "", search_item: str = "", max_pages: int = \1, start_date=None, end_date=None):'),
        ]

        for old_pat, new_pat in patterns:
            if re.search(old_pat, content):
                content = re.sub(old_pat, new_pat, content, count=1)
                modified = True
                break

    # 3. 날짜 필터 코드 추가 (all_items.sort 바로 앞에)
    if '# 날짜 필터 (기본: 최근 30일)' not in content:
        # all_items.sort 패턴 찾기
        sort_pattern = r'(\n        all_items\.sort\(key=lambda x: x\["date"\], reverse=True\))'
        if re.search(sort_pattern, content):
            content = re.sub(sort_pattern, DATE_FILTER_CODE + r'\1', content, count=1)
            modified = True
        else:
            # 다른 sort 패턴
            sort_pattern2 = r'(\n        all_items\.sort\(key=lambda x: x\.get\("date"'
            if re.search(sort_pattern2, content):
                content = re.sub(sort_pattern2, DATE_FILTER_CODE + r'\1', content, count=1)
                modified = True

    if modified:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False


if __name__ == "__main__":
    crawlers = sorted([f for f in os.listdir('.') if f.endswith('_crawler.py') and f not in SKIP])

    success = 0
    failed = []
    skipped = []

    for f in crawlers:
        try:
            if process_file(f):
                success += 1
                print(f"  ✅ {f}")
            else:
                skipped.append(f)
                print(f"  ⏭️  {f} (변경 없음)")
        except Exception as e:
            failed.append((f, str(e)[:60]))
            print(f"  ❌ {f}: {e}")

    print(f"\n완료: {success}개 수정, {len(skipped)}개 스킵, {len(failed)}개 실패")
    if failed:
        print("실패 목록:")
        for f, e in failed:
            print(f"  {f}: {e}")
