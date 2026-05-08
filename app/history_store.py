from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import (
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    func,
    insert,
    select,
)

from sqlalchemy.exc import OperationalError


metadata = MetaData()

upload_batches = Table(
    "upload_batches",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("batch_id", String),
    Column("table_type", String),
    Column("file_name", String),
    Column("row_count", Integer),
    Column("date_min", String),
    Column("date_max", String),
    Column("file_hash", String),
    Column("uploaded_at", String),
)

orders_raw = Table(
    "orders_raw",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("order_key", String, unique=True),
    Column("store_name", String),
    Column("goods_id", String),
    Column("goods_name", String),
    Column("goods_spec", String),
    Column("order_status", String),
    Column("after_sale_status", String),
    Column("order_date", String),
    Column("pay_date", String),
    Column("merchant_receivable", Float),
    Column("raw_json", String),
    Column("batch_id", String),
    Column("uploaded_at", String),
)

promotion_raw = Table(
    "promotion_raw",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("promo_key", String, unique=True),
    Column("store_name", String),
    Column("goods_id", String),
    Column("promo_date", String),
    Column("spend", Float),
    Column("transaction_amount", Float),
    Column("raw_json", String),
    Column("batch_id", String),
    Column("uploaded_at", String),
)

product_master_current = Table("product_master_current", metadata, Column("id", Integer, primary_key=True, autoincrement=True), Column("row_key", String, unique=True), Column("raw_json", String), Column("uploaded_at", String))
sales_spec_mapping_current = Table("sales_spec_mapping_current", metadata, Column("id", Integer, primary_key=True, autoincrement=True), Column("row_key", String, unique=True), Column("raw_json", String), Column("uploaded_at", String))
link_spec_mapping_current = Table("link_spec_mapping_current", metadata, Column("id", Integer, primary_key=True, autoincrement=True), Column("row_key", String, unique=True), Column("raw_json", String), Column("uploaded_at", String))


def get_database_url() -> str:
    try:
        secret_url = st.secrets.get("DATABASE_URL")
        if secret_url:
            return str(secret_url)
    except Exception:
        pass

    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    fallback_dir = Path("/tmp/aland_history")
    fallback_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{fallback_dir / 'aland_history.db'}"


def _engine():
    url = get_database_url()
    if url.startswith("sqlite"):
        return create_engine(url, pool_pre_ping=True, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)


def init_history_db():
    try:
        metadata.create_all(_engine())
    except OperationalError as e:
        raise RuntimeError(
            "历史数据库初始化失败。若在 Streamlit Cloud 长期使用，请配置 Supabase/PostgreSQL 的 DATABASE_URL；"
            "如果只是临时测试，系统会尝试使用 /tmp/aland_history/aland_history.db。原始错误："
            + str(e)
        ) from e


def _col(df: pd.DataFrame, names: tuple[str, ...]):
    for n in names:
        if n in df.columns:
            return n
    return None


def _text(v):
    if pd.isna(v):
        return ""
    return str(v).strip()


def _num(v):
    try:
        return float(v)
    except Exception:
        return None


def _date(v):
    ts = pd.to_datetime(v, errors="coerce")
    if pd.isna(ts):
        return ""
    return ts.strftime("%Y-%m-%d")


def _hash_row(row: dict) -> str:
    return hashlib.md5(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def _insert_batch(conn, batch_id, table_type, file_name, row_count, date_min, date_max, file_hash):
    conn.execute(insert(upload_batches).values(batch_id=batch_id, table_type=table_type, file_name=file_name or "", row_count=row_count, date_min=date_min or "", date_max=date_max or "", file_hash=file_hash, uploaded_at=datetime.utcnow().isoformat()))


def save_orders_history(orders_df: pd.DataFrame, file_name: str | None = None) -> dict:
    init_history_db()
    batch_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S_orders")
    date_col = _col(orders_df, ("订单成交时间", "支付时间"))
    pay_col = _col(orders_df, ("支付时间",))
    recv_col = _col(orders_df, ("商家实收金额(元)", "商家实收", "商家实收金额", "商家实收(元)"))
    goods_id_col = _col(orders_df, ("商品id", "商品ID", "商品Id"))
    key_col = _col(orders_df, ("订单号", "订单编号", "父订单编号", "子订单编号"))

    inserted = updated = skipped = 0
    all_dates = []
    with _engine().begin() as conn:
        for idx, row in orders_df.fillna("").iterrows():
            raw = row.to_dict()
            order_date = _date(raw.get(date_col)) if date_col else ""
            pay_date = _date(raw.get(pay_col)) if pay_col else ""
            effective_date = order_date or pay_date
            if effective_date:
                all_dates.append(effective_date)

            if key_col and _text(raw.get(key_col)):
                order_key = _text(raw.get(key_col))
            else:
                fallback = f"{_text(raw.get(goods_id_col))}|{_text(raw.get('商品规格'))}|{pay_date}|{_text(raw.get(recv_col))}|{idx}"
                order_key = hashlib.md5(fallback.encode()).hexdigest()

            payload = {
                "order_key": order_key,
                "store_name": _text(raw.get("店铺名称")),
                "goods_id": _text(raw.get(goods_id_col)) if goods_id_col else "",
                "goods_name": _text(raw.get("商品名称")),
                "goods_spec": _text(raw.get("商品规格")),
                "order_status": _text(raw.get("订单状态")),
                "after_sale_status": _text(raw.get("售后状态")),
                "order_date": order_date,
                "pay_date": pay_date,
                "merchant_receivable": _num(raw.get(recv_col)) if recv_col else None,
                "raw_json": json.dumps(raw, ensure_ascii=False, default=str),
                "batch_id": batch_id,
                "uploaded_at": datetime.utcnow().isoformat(),
            }
            exists = conn.execute(select(orders_raw.c.id).where(orders_raw.c.order_key == order_key)).first()
            if exists:
                conn.execute(orders_raw.update().where(orders_raw.c.order_key == order_key).values(**payload))
                updated += 1
            else:
                conn.execute(insert(orders_raw).values(**payload))
                inserted += 1

        file_hash = hashlib.md5(pd.util.hash_pandas_object(orders_df.astype(str), index=True).values.tobytes()).hexdigest() if not orders_df.empty else ""
        dmin, dmax = (min(all_dates), max(all_dates)) if all_dates else ("", "")
        _insert_batch(conn, batch_id, "orders", file_name, len(orders_df), dmin, dmax, file_hash)

    return {"batch_id": batch_id, "inserted": inserted, "updated": updated, "skipped": skipped, "date_min": dmin, "date_max": dmax, "row_count": len(orders_df)}


def save_promotion_history(promo_df: pd.DataFrame, file_name: str | None = None) -> dict:
    init_history_db()
    batch_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S_promotion")
    date_col = _col(promo_df, ("日期", "统计日期", "推广日期", "开始日期", "结束日期"))
    spend_col = _col(promo_df, ("成交花费", "成交花费(元)", "实际成交花费(元)", "实际成交花费", "推广费"))
    goods_id_col = _col(promo_df, ("商品ID", "商品id"))
    inserted = updated = skipped = 0
    all_dates = []
    with _engine().begin() as conn:
        for idx, row in promo_df.fillna("").iterrows():
            raw = row.to_dict()
            promo_date = _date(raw.get(date_col)) if date_col else ""
            if promo_date:
                all_dates.append(promo_date)
            core_hash = _hash_row({"goods_id": _text(raw.get(goods_id_col)) if goods_id_col else "", "promo_date": promo_date, "spend": _text(raw.get(spend_col)) if spend_col else "", "row": raw})
            if promo_date and goods_id_col:
                promo_key = f"{_text(raw.get(goods_id_col))}|{promo_date}|{core_hash[:12]}"
            else:
                promo_key = f"{batch_id}|{idx}|{core_hash}"
            payload = {
                "promo_key": promo_key,
                "store_name": _text(raw.get("店铺名称")),
                "goods_id": _text(raw.get(goods_id_col)) if goods_id_col else "",
                "promo_date": promo_date,
                "spend": _num(raw.get(spend_col)) if spend_col else None,
                "transaction_amount": _num(raw.get("总交易额(元)")) or _num(raw.get("交易金额")),
                "raw_json": json.dumps(raw, ensure_ascii=False, default=str),
                "batch_id": batch_id,
                "uploaded_at": datetime.utcnow().isoformat(),
            }
            exists = conn.execute(select(promotion_raw.c.id).where(promotion_raw.c.promo_key == promo_key)).first()
            if exists:
                conn.execute(promotion_raw.update().where(promotion_raw.c.promo_key == promo_key).values(**payload))
                updated += 1
            else:
                conn.execute(insert(promotion_raw).values(**payload))
                inserted += 1
        file_hash = hashlib.md5(pd.util.hash_pandas_object(promo_df.astype(str), index=True).values.tobytes()).hexdigest() if not promo_df.empty else ""
        dmin, dmax = (min(all_dates), max(all_dates)) if all_dates else ("", "")
        _insert_batch(conn, batch_id, "promotion", file_name, len(promo_df), dmin, dmax, file_hash)
    return {"batch_id": batch_id, "inserted": inserted, "updated": updated, "skipped": skipped, "date_min": dmin, "date_max": dmax, "row_count": len(promo_df)}


def save_master_table_history(table_key: str, df: pd.DataFrame, file_name: str | None = None) -> dict:
    mapping = {
        "product_master": (product_master_current, ("标准产品ID",)),
        "sales_spec_mapping": (sales_spec_mapping_current, ("销售规格ID",)),
        "link_spec_mapping": (link_spec_mapping_current, ("商品ID", "商品规格")),
    }
    if table_key not in mapping:
        raise ValueError("unsupported table_key")
    init_history_db()
    table, key_cols = mapping[table_key]
    batch_id = datetime.utcnow().strftime(f"%Y%m%d_%H%M%S_{table_key}")
    with _engine().begin() as conn:
        conn.execute(delete(table))
        for _, row in df.fillna("").iterrows():
            raw = row.to_dict()
            if len(key_cols) == 1 and key_cols[0] in raw and _text(raw.get(key_cols[0])):
                row_key = _text(raw.get(key_cols[0]))
            elif all(_text(raw.get(c)) for c in key_cols):
                row_key = "|".join(_text(raw.get(c)) for c in key_cols)
            else:
                row_key = _hash_row(raw)
            conn.execute(insert(table).values(row_key=row_key, raw_json=json.dumps(raw, ensure_ascii=False, default=str), uploaded_at=datetime.utcnow().isoformat()))
        file_hash = hashlib.md5(pd.util.hash_pandas_object(df.astype(str), index=True).values.tobytes()).hexdigest() if not df.empty else ""
        _insert_batch(conn, batch_id, table_key, file_name, len(df), "", "", file_hash)
    return {"batch_id": batch_id, "inserted": len(df), "updated": 0, "skipped": 0, "date_min": "", "date_max": "", "row_count": len(df)}


def _load_raw_json_df(conn, table):
    rows = conn.execute(select(table.c.raw_json)).fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([json.loads(r[0]) for r in rows if r[0]])


def load_history_tables(date_start=None, date_end=None) -> dict[str, pd.DataFrame]:
    init_history_db()
    with _engine().begin() as conn:
        od = _load_raw_json_df(conn, orders_raw)
        pdm = _load_raw_json_df(conn, promotion_raw)
        pm = _load_raw_json_df(conn, product_master_current)
        sm = _load_raw_json_df(conn, sales_spec_mapping_current)
        lm = _load_raw_json_df(conn, link_spec_mapping_current)

    if not od.empty:
        order_date = pd.to_datetime(od.get("订单成交时间"), errors="coerce")
        pay_date = pd.to_datetime(od.get("支付时间"), errors="coerce")
        effective = order_date.fillna(pay_date)
        if date_start is not None:
            effective_start = pd.to_datetime(date_start)
            od = od[effective >= effective_start]
            effective = effective[effective >= effective_start]
        if date_end is not None:
            effective_end = pd.to_datetime(date_end)
            od = od[effective <= effective_end]

    if not pdm.empty:
        date_col = _col(pdm, ("日期", "统计日期", "推广日期", "开始日期", "结束日期"))
        if date_col:
            ds = pd.to_datetime(pdm[date_col], errors="coerce")
            if date_start is not None:
                pdm = pdm[ds >= pd.to_datetime(date_start)]
                ds = ds[ds >= pd.to_datetime(date_start)]
            if date_end is not None:
                pdm = pdm[ds <= pd.to_datetime(date_end)]

    return {"orders": od if od is not None else pd.DataFrame(), "promotion": pdm if pdm is not None else pd.DataFrame(), "product_master": pm if pm is not None else pd.DataFrame(), "sales_spec_mapping": sm if sm is not None else pd.DataFrame(), "link_spec_mapping": lm if lm is not None else pd.DataFrame(), "cashflow": pd.DataFrame()}


def list_upload_batches(limit=50) -> pd.DataFrame:
    init_history_db()
    with _engine().begin() as conn:
        rows = conn.execute(select(upload_batches).order_by(upload_batches.c.id.desc()).limit(limit)).mappings().all()
    return pd.DataFrame(rows)


def delete_upload_batch(batch_id: str) -> dict:
    init_history_db()
    with _engine().begin() as conn:
        o = conn.execute(delete(orders_raw).where(orders_raw.c.batch_id == batch_id)).rowcount or 0
        p = conn.execute(delete(promotion_raw).where(promotion_raw.c.batch_id == batch_id)).rowcount or 0
        b = conn.execute(delete(upload_batches).where(upload_batches.c.batch_id == batch_id)).rowcount or 0
    return {"batch_id": batch_id, "orders_deleted": o, "promotion_deleted": p, "batch_deleted": b}


def get_history_stats() -> dict:
    init_history_db()
    with _engine().begin() as conn:
        order_min, order_max = conn.execute(select(func.min(orders_raw.c.order_date), func.max(orders_raw.c.order_date))).one()
        promo_min, promo_max = conn.execute(select(func.min(promotion_raw.c.promo_date), func.max(promotion_raw.c.promo_date))).one()
        order_count = conn.execute(select(func.count()).select_from(orders_raw)).scalar() or 0
        promo_count = conn.execute(select(func.count()).select_from(promotion_raw)).scalar() or 0
    return {"order_min": order_min, "order_max": order_max, "promo_min": promo_min, "promo_max": promo_max, "order_count": order_count, "promo_count": promo_count}
