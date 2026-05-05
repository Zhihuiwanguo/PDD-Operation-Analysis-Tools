"""SQLite 数据存储模块（V2）。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.storage import DEFAULT_CONFIG, _from_jsonable, _to_jsonable

DB_PATH = Path("data") / "aland.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                total_sales REAL,
                total_spend REAL,
                roi REAL,
                gross_margin REAL,
                result_json TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS business_config (
                id INTEGER PRIMARY KEY,
                q2_sales_target REAL,
                q2_roi_target REAL,
                gross_margin_warning REAL,
                personal_score REAL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS business_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                note_type TEXT,
                target TEXT,
                note TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS product_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT,
                tag TEXT
            )
            """
        )
        conn.commit()


def save_analysis(result_dict: dict) -> int:
    metrics = result_dict.get("overview", {}).get("metrics", {})
    payload = json.dumps(_to_jsonable(result_dict), ensure_ascii=False)
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO analysis_results (date, total_sales, total_spend, roi, gross_margin, result_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(metrics.get("统计周期", "")),
                float(metrics.get("销售额", 0) or 0),
                float(metrics.get("推广花费", 0) or 0),
                float(metrics.get("ROI", 0) or 0),
                float(metrics.get("毛利率", 0) or 0),
                payload,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def load_latest_analysis():
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT result_json FROM analysis_results ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
    if not row:
        return None
    return _from_jsonable(json.loads(row[0]))


def save_config(config_dict: dict) -> None:
    merged = DEFAULT_CONFIG.copy()
    merged.update(config_dict or {})
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO business_config (id, q2_sales_target, q2_roi_target, gross_margin_warning, personal_score)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                q2_sales_target=excluded.q2_sales_target,
                q2_roi_target=excluded.q2_roi_target,
                gross_margin_warning=excluded.gross_margin_warning,
                personal_score=excluded.personal_score
            """,
            (
                float(merged.get("q2_sales_target", 0) or 0),
                float(merged.get("q2_roi_target", 1.0) or 1.0),
                float(merged.get("gross_margin_warning", 0.5) or 0.5),
                float(merged.get("personal_score", 100) or 100),
            ),
        )
        conn.commit()


def load_config() -> dict:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT q2_sales_target, q2_roi_target, gross_margin_warning, personal_score FROM business_config WHERE id=1"
        )
        row = cur.fetchone()
    if not row:
        return DEFAULT_CONFIG.copy()
    return {
        "q2_sales_target": row[0],
        "q2_roi_target": row[1],
        "gross_margin_warning": row[2],
        "personal_score": row[3],
    }


def add_note(date: str, note_type: str, target: str, note: str) -> int:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO business_notes (date, note_type, target, note) VALUES (?, ?, ?, ?)",
            (date, note_type, target, note),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_notes(date: str | None = None) -> list[dict]:
    with _get_conn() as conn:
        cur = conn.cursor()
        if date:
            cur.execute(
                "SELECT id, date, note_type, target, note FROM business_notes WHERE date=? ORDER BY id DESC",
                (date,),
            )
        else:
            cur.execute("SELECT id, date, note_type, target, note FROM business_notes ORDER BY id DESC")
        rows = cur.fetchall()
    return [
        {"id": r[0], "date": r[1], "note_type": r[2], "target": r[3], "note": r[4]}
        for r in rows
    ]


def add_product_tag(product: str, tag: str) -> int:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO product_tags (product_name, tag) VALUES (?, ?)", (product, tag))
        conn.commit()
        return int(cur.lastrowid)


def get_product_tags(product: str) -> list[str]:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT tag FROM product_tags WHERE product_name=? ORDER BY id DESC",
            (product,),
        )
        rows = cur.fetchall()
    return [str(r[0]) for r in rows]
