# -*- coding: utf-8 -*-
"""
강원개발공사 (gdco) - xlsx 20행
자체 게시판이 없고 나라장터(nara)로 연동됨.
따라서 nara DB에서 '강원개발공사' 조직으로 필터링해서 미러링.
"""
from datetime import datetime, timedelta


class GDCOCrawler:
    """강원개발공사 크롤러 - nara에서 조직명 필터 미러링."""

    ORG_KEYWORD = '강원개발공사'

    def search(self, keyword='', max_pages=9999, start_date=None, end_date=None):
        import db
        # 날짜 기본값
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        results = []
        with db.get_conn() as conn:
            rows = conn.execute(
                """SELECT title, date, url, organization, number, deadline
                   FROM crawl_data
                   WHERE crawler_id='nara' AND organization LIKE ?
                     AND date >= ? AND date <= ?""",
                (f'%{self.ORG_KEYWORD}%', start_date, end_date + ' 23:59:59')
            ).fetchall()
            for r in rows:
                results.append({
                    'title': r[0], 'date': r[1], 'url': r[2],
                    'organization': self.ORG_KEYWORD,
                    'number': r[4], 'deadline': r[5],
                })
        print(f'[강원개발공사] nara 필터: {len(results)}건', flush=True)
        return results


def main():
    c = GDCOCrawler()
    items = c.search(start_date='2000-01-01', end_date='2099-12-31')
    print(f'{len(items)}건')
    for it in items[:5]:
        print(f"  {it['date']} | {it['title'][:60]}")


if __name__ == "__main__":
    main()
