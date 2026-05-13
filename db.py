# -*- coding: utf-8 -*-
"""
SQLite DB 모듈
- crawl_data: 크롤러 수집 결과 저장
- crawler_status: 크롤러별 마지막 수집 시점 추적
"""
import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crawlers.db")


@contextmanager
def get_conn():
    """DB 연결 컨텍스트 매니저"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """DB 초기화: 테이블 생성"""
    with get_conn() as conn:
        c = conn.cursor()

        # 1. 크롤러 수집 결과 테이블
        c.execute("""
            CREATE TABLE IF NOT EXISTS crawl_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crawler_id TEXT NOT NULL,
                crawler_name TEXT NOT NULL,
                crawler_type TEXT,
                title TEXT NOT NULL,
                date TEXT,
                url TEXT,
                organization TEXT,
                number TEXT,
                deadline TEXT,
                content_hash TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(crawler_id, content_hash)
            )
        """)

        # 인덱스 (검색 속도 향상)
        c.execute("CREATE INDEX IF NOT EXISTS idx_title ON crawl_data(title)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_date ON crawl_data(date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_crawler ON crawl_data(crawler_id)")

        # 2. 크롤러별 수집 상태
        c.execute("""
            CREATE TABLE IF NOT EXISTS crawler_status (
                crawler_id TEXT PRIMARY KEY,
                crawler_name TEXT,
                last_run_at TEXT,
                last_count INTEGER DEFAULT 0,
                last_error TEXT,
                total_collected INTEGER DEFAULT 0
            )
        """)

        # 3. 수집 로그 (이력 추적용)
        c.execute("""
            CREATE TABLE IF NOT EXISTS crawl_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT,
                ended_at TEXT,
                total_crawlers INTEGER,
                success_count INTEGER,
                error_count INTEGER,
                new_items INTEGER
            )
        """)


def normalize_date(date):
    """날짜 정규화 (다양한 형식 → YYYY-MM-DD)"""
    if not date:
        return ""
    return str(date).replace(".", "-").replace("/", "-").strip()[:10]


def make_content_hash(crawler_id, title, date, url=None):
    """중복 방지용 해시 (제목+정규화 날짜) - URL 제외"""
    import hashlib
    nd = normalize_date(date)
    raw = f"{crawler_id}|{(title or '').strip()}|{nd}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def save_items(crawler_id, crawler_name, crawler_type, items):
    """크롤러 결과를 DB에 저장 (중복 무시)"""
    if not items:
        return 0

    new_count = 0
    with get_conn() as conn:
        c = conn.cursor()
        for item in items:
            title = item.get("title", "").strip()
            if not title:
                continue
            date = item.get("date", "")
            url = item.get("url") or item.get("link", "")
            organization = item.get("organization", "")
            number = item.get("number", "")
            deadline = item.get("deadline", "")
            content_hash = make_content_hash(crawler_id, title, date, url)

            try:
                c.execute("""
                    INSERT OR IGNORE INTO crawl_data
                    (crawler_id, crawler_name, crawler_type, title, date, url,
                     organization, number, deadline, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (crawler_id, crawler_name, crawler_type, title, date, url,
                      organization, number, deadline, content_hash))
                if c.rowcount > 0:
                    new_count += 1
            except Exception:
                pass
    return new_count


def update_crawler_status(crawler_id, crawler_name, count, error=None):
    """크롤러 수집 상태 업데이트"""
    with get_conn() as conn:
        c = conn.cursor()
        now = datetime.now().isoformat(timespec="seconds")
        c.execute("""
            INSERT INTO crawler_status (crawler_id, crawler_name, last_run_at, last_count, last_error, total_collected)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(crawler_id) DO UPDATE SET
                crawler_name = excluded.crawler_name,
                last_run_at = excluded.last_run_at,
                last_count = excluded.last_count,
                last_error = excluded.last_error,
                total_collected = total_collected + excluded.last_count
        """, (crawler_id, crawler_name, now, count, error, count))


def search(keyword="", start_date=None, end_date=None, crawler_ids=None, limit=10000):
    """DB에서 검색"""
    where = []
    params = []

    if keyword:
        where.append("title LIKE ?")
        params.append(f"%{keyword}%")

    if start_date:
        where.append("date >= ?")
        params.append(start_date)

    if end_date:
        where.append("date <= ?")
        params.append(end_date + " 99:99:99")  # 시간까지 포함된 날짜 비교

    if crawler_ids:
        placeholders = ",".join("?" * len(crawler_ids))
        where.append(f"crawler_id IN ({placeholders})")
        params.extend(crawler_ids)

    where_clause = "WHERE " + " AND ".join(where) if where else ""
    params.append(limit)

    sql = f"""
        SELECT crawler_id, crawler_name, crawler_type, title, date, url,
               organization, number, deadline
        FROM crawl_data
        {where_clause}
        ORDER BY date DESC
        LIMIT ?
    """

    with get_conn() as conn:
        c = conn.cursor()
        rows = c.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_stats():
    """DB 통계"""
    with get_conn() as conn:
        c = conn.cursor()
        total = c.execute("SELECT COUNT(*) FROM crawl_data").fetchone()[0]
        crawler_counts = c.execute("""
            SELECT crawler_id, crawler_name, COUNT(*) as cnt
            FROM crawl_data
            GROUP BY crawler_id
            ORDER BY cnt DESC
        """).fetchall()
        last_log = c.execute("""
            SELECT * FROM crawl_log ORDER BY id DESC LIMIT 1
        """).fetchone()
        return {
            "total": total,
            "by_crawler": [dict(r) for r in crawler_counts],
            "last_log": dict(last_log) if last_log else None,
        }


def log_crawl_session(started_at, ended_at, total, success, error, new_items):
    """크롤 세션 로그 저장"""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO crawl_log (started_at, ended_at, total_crawlers,
                                    success_count, error_count, new_items)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (started_at, ended_at, total, success, error, new_items))


if __name__ == "__main__":
    init_db()
    print(f"DB 초기화 완료: {DB_PATH}")
    stats = get_stats()
    print(f"현재 데이터: {stats['total']}건")
