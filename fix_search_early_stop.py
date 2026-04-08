#!/usr/bin/env python3
"""search() 메서드를 early stop 방식으로 일괄 교체"""
import os
import re

# 제외 파일
SKIP = {
    'alio_crawler.py', 'alio_item_crawler.py', 'ghdc_crawler.py',
    'gumc_crawler.py', 'isdc_crawler.py', 'jbdc_crawler.py',
    'jndc_crawler.py', 'nara_crawler.py', 'ttdc_crawler.py', 'yjuc_crawler.py',
    'lh_crawler.py', 'gh_crawler.py',
    'add_date_filter.py', 'verify_group.py', 'fix_search_early_stop.py',
}

# page_results 패턴이 있는 크롤러만 대상
# 이 패턴을 새 early stop 로직으로 교체

OLD_PATTERN = r'''        first_items, total_count = self\._fetch_page\(keyword, 1\)
        total_pages = max\(1, math\.ceil\(total_count / PAGE_SIZE\)\)
        actual_pages = min\(total_pages, max_pages\)
        print\(f"  \[Page 1/\{actual_pages\}\] \{len\(first_items\)\}건 수집 \(전체 \{total_count\}건\)"\)

        if actual_pages <= 1:
            all_items = first_items
        else:
            page_results = \{1: first_items\}
            with ThreadPoolExecutor\(max_workers=self\.WORKERS\) as executor:
                futures = \{
                    executor\.submit\(self\._fetch_page, keyword, p\): p
                    for p in range\(2, actual_pages \+ 1\)
                \}
                for future in as_completed\(futures\):
                    p = futures\[future\]
                    try:
                        items, _ = future\.result\(\)
                        if items:
                            page_results\[p\] = items
                    except Exception:
                        pass

            all_items = \[\]
            for p in sorted\(page_results\.keys\(\)\):
                all_items\.extend\(page_results\[p\]\)

        # 날짜 필터 \(기본: 최근 30일\)
        if not start_date:
            start_date = \(datetime\.now\(\) - timedelta\(days=30\)\)\.strftime\("%Y-%m-%d"\)
        if not end_date:
            end_date = datetime\.now\(\)\.strftime\("%Y-%m-%d"\)

        filtered = \[\]
        for item in all_items:
            d = \(item\.get\("date"\) or ""\)\.replace\("\.", "-"\)\.replace\("/", "-"\)\[:10\]
            if not d:
                continue
            if start_date <= d <= end_date:
                filtered\.append\(item\)
        all_items = filtered'''

NEW_CODE = '''        # 날짜 기본값 (최근 30일)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        first_items, total_count = self._fetch_page(keyword, 1)
        total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
        actual_pages = min(total_pages, max_pages)
        print(f"  [Page 1/{actual_pages}] {len(first_items)}건 수집 (전체 {total_count}건)")

        all_items = []
        stop = False

        # 첫 페이지 날짜 필터
        for item in first_items:
            d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
            if not d:
                continue
            if d < start_date:
                stop = True
                continue
            if d <= end_date:
                all_items.append(item)

        # 나머지 페이지 순차 수집 + early stop
        if not stop and actual_pages > 1:
            page = 2
            while page <= actual_pages and not stop:
                # 배치 단위로 병렬 수집
                batch_end = min(page + self.WORKERS, actual_pages + 1)
                with ThreadPoolExecutor(max_workers=self.WORKERS) as executor:
                    futures = {
                        executor.submit(self._fetch_page, keyword, p): p
                        for p in range(page, batch_end)
                    }
                    batch_results = {}
                    for future in as_completed(futures):
                        p = futures[future]
                        try:
                            items, _ = future.result()
                            if items:
                                batch_results[p] = items
                        except Exception:
                            pass

                # 페이지 순서대로 날짜 체크
                for p in sorted(batch_results.keys()):
                    for item in batch_results[p]:
                        d = (item.get("date") or "").replace(".", "-").replace("/", "-")[:10]
                        if not d:
                            continue
                        if d < start_date:
                            stop = True
                            break
                        if d <= end_date:
                            all_items.append(item)
                    if stop:
                        break

                page = batch_end'''


def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # page_results 패턴이 있는지 확인
    if 'page_results[p] = items' not in content:
        return False

    if '# 배치 단위로 병렬 수집' in content:
        return False  # 이미 적용됨

    # 기존 패턴 찾기 (정규식 대신 문자열 기반)
    # 핵심 마커: "first_items, total_count = self._fetch_page(keyword, 1)" 부터
    #           "all_items = filtered" 까지

    marker_start = "        first_items, total_count = self._fetch_page(keyword, 1)"
    marker_end = "        all_items = filtered"

    idx_start = content.find(marker_start)
    idx_end = content.find(marker_end)

    if idx_start < 0 or idx_end < 0:
        return False

    idx_end += len(marker_end)

    # 교체
    new_content = content[:idx_start] + NEW_CODE + content[idx_end:]

    with open(filepath, 'w') as f:
        f.write(new_content)
    return True


if __name__ == "__main__":
    crawlers = sorted([f for f in os.listdir('.') if f.endswith('_crawler.py') and f not in SKIP])

    success = 0
    skipped = 0
    failed = []

    for f in crawlers:
        try:
            if process_file(f):
                success += 1
            else:
                skipped += 1
        except Exception as e:
            failed.append((f, str(e)[:60]))

    print(f"완료: {success}개 수정, {skipped}개 스킵, {len(failed)}개 실패")
    if failed:
        for f, e in failed:
            print(f"  ❌ {f}: {e}")
