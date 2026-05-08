from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import Column, Float, Integer, MetaData, String, Table, create_engine, delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

metadata = MetaData()
# tables definitions
upload_batches = Table("upload_batches", metadata, Column("id", Integer, primary_key=True), Column("batch_id", String), Column("table_type", String), Column("file_name", String), Column("row_count", Integer), Column("date_min", String), Column("date_max", String), Column("file_hash", String), Column("uploaded_at", String))
orders_raw = Table("orders_raw", metadata, Column("id", Integer, primary_key=True), Column("order_key", String, unique=True), Column("platform", String), Column("store_name", String), Column("goods_id", String), Column("order_date", String), Column("pay_date", String), Column("raw_json", String), Column("batch_id", String), Column("uploaded_at", String))
promotion_raw = Table("promotion_raw", metadata, Column("id", Integer, primary_key=True), Column("promo_key", String, unique=True), Column("platform", String), Column("store_name", String), Column("goods_id", String), Column("promo_date", String), Column("spend", Float), Column("raw_json", String), Column("batch_id", String), Column("uploaded_at", String))
product_master_current = Table("product_master_current", metadata, Column("id", Integer, primary_key=True), Column("row_key", String, unique=True), Column("raw_json", String), Column("uploaded_at", String))
sales_spec_mapping_current = Table("sales_spec_mapping_current", metadata, Column("id", Integer, primary_key=True), Column("row_key", String, unique=True), Column("raw_json", String), Column("uploaded_at", String))
link_spec_mapping_current = Table("link_spec_mapping_current", metadata, Column("id", Integer, primary_key=True), Column("row_key", String, unique=True), Column("raw_json", String), Column("uploaded_at", String))
cashflow_raw = Table("cashflow_raw", metadata, Column("id", Integer, primary_key=True), Column("cashflow_key", String, unique=True), Column("platform", String), Column("store_name", String), Column("cashflow_time", String), Column("cashflow_date", String), Column("flow_type", String), Column("transaction_amount", Float), Column("transaction_summary", String), Column("raw_json", String), Column("batch_id", String), Column("uploaded_at", String))

def get_database_url() -> str:
    secret = None
    try:
        secret = st.secrets.get("DATABASE_URL")
    except Exception:
        secret = None
    return str(secret or os.getenv("DATABASE_URL") or f"sqlite:///{Path('/tmp/aland_history').resolve() / 'aland_history.db'}")

def _engine():
    url = get_database_url(); Path('/tmp/aland_history').mkdir(parents=True, exist_ok=True)
    return create_engine(url, pool_pre_ping=True, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})

def init_history_db():
    metadata.create_all(_engine())
    ensure_history_schema()


def ensure_history_schema():
    eng = _engine()
    with eng.begin() as conn:
        if eng.dialect.name == "postgresql":
            conn.exec_driver_sql("ALTER TABLE IF EXISTS orders_raw ADD COLUMN IF NOT EXISTS platform VARCHAR DEFAULT '拼多多';")
            conn.exec_driver_sql("ALTER TABLE IF EXISTS promotion_raw ADD COLUMN IF NOT EXISTS platform VARCHAR DEFAULT '拼多多';")
            conn.exec_driver_sql("ALTER TABLE IF EXISTS cashflow_raw ADD COLUMN IF NOT EXISTS platform VARCHAR DEFAULT '拼多多';")
            conn.exec_driver_sql("ALTER TABLE IF EXISTS cashflow_raw ADD COLUMN IF NOT EXISTS store_name VARCHAR;")
            conn.exec_driver_sql("ALTER TABLE IF EXISTS cashflow_raw ADD COLUMN IF NOT EXISTS cashflow_time VARCHAR;")
            conn.exec_driver_sql("ALTER TABLE IF EXISTS cashflow_raw ADD COLUMN IF NOT EXISTS cashflow_date VARCHAR;")
            conn.exec_driver_sql("ALTER TABLE IF EXISTS cashflow_raw ADD COLUMN IF NOT EXISTS flow_type VARCHAR;")
            conn.exec_driver_sql("ALTER TABLE IF EXISTS cashflow_raw ADD COLUMN IF NOT EXISTS transaction_amount FLOAT;")
            conn.exec_driver_sql("ALTER TABLE IF EXISTS cashflow_raw ADD COLUMN IF NOT EXISTS transaction_summary VARCHAR;")
            conn.exec_driver_sql("ALTER TABLE IF EXISTS cashflow_raw ADD COLUMN IF NOT EXISTS raw_json VARCHAR;")
            conn.exec_driver_sql("ALTER TABLE IF EXISTS cashflow_raw ADD COLUMN IF NOT EXISTS batch_id VARCHAR;")
            conn.exec_driver_sql("ALTER TABLE IF EXISTS cashflow_raw ADD COLUMN IF NOT EXISTS uploaded_at VARCHAR;")
            return

        if eng.dialect.name == "sqlite":
            def _sqlite_add_column_if_missing(table_name: str, column_name: str, column_sql: str):
                exists = conn.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                ).fetchone()
                if not exists:
                    return
                cols = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()}
                if column_name not in cols:
                    conn.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")

            _sqlite_add_column_if_missing("orders_raw", "platform", "platform VARCHAR DEFAULT '拼多多'")
            _sqlite_add_column_if_missing("promotion_raw", "platform", "platform VARCHAR DEFAULT '拼多多'")
            _sqlite_add_column_if_missing("cashflow_raw", "platform", "platform VARCHAR DEFAULT '拼多多'")
            _sqlite_add_column_if_missing("cashflow_raw", "store_name", "store_name VARCHAR")
            _sqlite_add_column_if_missing("cashflow_raw", "cashflow_time", "cashflow_time VARCHAR")
            _sqlite_add_column_if_missing("cashflow_raw", "cashflow_date", "cashflow_date VARCHAR")
            _sqlite_add_column_if_missing("cashflow_raw", "flow_type", "flow_type VARCHAR")
            _sqlite_add_column_if_missing("cashflow_raw", "transaction_amount", "transaction_amount FLOAT")
            _sqlite_add_column_if_missing("cashflow_raw", "transaction_summary", "transaction_summary VARCHAR")
            _sqlite_add_column_if_missing("cashflow_raw", "raw_json", "raw_json VARCHAR")
            _sqlite_add_column_if_missing("cashflow_raw", "batch_id", "batch_id VARCHAR")
            _sqlite_add_column_if_missing("cashflow_raw", "uploaded_at", "uploaded_at VARCHAR")

def _col(df, names): return next((n for n in names if n in df.columns), None)
def _text(v): return "" if pd.isna(v) else str(v).strip()
def _date(v):
    t=pd.to_datetime(v, errors='coerce'); return "" if pd.isna(t) else t.strftime('%Y-%m-%d')
def _insert_batch(conn,*args):
    batch_id, table_type, file_name, row_count, date_min, date_max, file_hash=args
    conn.execute(insert(upload_batches).values(batch_id=batch_id,table_type=table_type,file_name=file_name or "",row_count=row_count,date_min=date_min or "",date_max=date_max or "",file_hash=file_hash,uploaded_at=datetime.utcnow().isoformat()))
def _upsert_stmt(table, rows, key_col, dialect):
    base = pg_insert(table).values(rows) if dialect=='postgresql' else sqlite_insert(table).values(rows)
    return base.on_conflict_do_update(index_elements=[key_col], set_={c.name:getattr(base.excluded,c.name) for c in table.columns if c.name not in ('id',key_col)})

def save_orders_history(df: pd.DataFrame, file_name: str|None=None)->dict:
    init_history_db();batch_id=datetime.utcnow().strftime('%Y%m%d_%H%M%S_orders')
    key_col=_col(df,("订单号","订单编号","父订单编号","子订单编号"));gid=_col(df,("商品ID","商品id","goods_id"));platform_col=_col(df,("平台",));store_col=_col(df,("店铺名称",));dcol=_col(df,("订单成交时间",));pcol=_col(df,("支付时间",))
    rows=[];dates=[]
    for _,r in df.fillna("").iterrows():
        raw=r.to_dict();platform=_text(raw.get(platform_col)) or '拼多多';store=_text(raw.get(store_col));oid=_text(raw.get(key_col));
        if not oid: continue
        od,pd_=_date(raw.get(dcol)),_date(raw.get(pcol));eff=od or pd_; dates += [eff] if eff else []
        rows.append({"order_key":f"{platform}|{store}|{oid}","platform":platform,"store_name":store,"goods_id":_text(raw.get(gid)),"order_date":od,"pay_date":pd_,"raw_json":json.dumps(raw,ensure_ascii=False,default=str),"batch_id":batch_id,"uploaded_at":datetime.utcnow().isoformat()})
    eng=_engine(); inserted=updated=0
    with eng.begin() as conn:
        keys=[x['order_key'] for x in rows]; ex=set(conn.execute(select(orders_raw.c.order_key).where(orders_raw.c.order_key.in_(keys))).scalars().all()) if keys else set(); updated=len(ex); inserted=len(keys)-len(ex)
        for i in range(0,len(rows),1000):
            ch=rows[i:i+1000]
            if ch: conn.execute(_upsert_stmt(orders_raw,ch,'order_key',eng.dialect.name))
        dmin,dmax=(min(dates),max(dates)) if dates else ("","")
        _insert_batch(conn,batch_id,'orders',file_name,len(df),dmin,dmax,"")
    return {"batch_id":batch_id,"inserted":inserted,"updated":updated,"skipped":0,"date_min":dmin,"date_max":dmax,"row_count":len(df)}

def save_promotion_history(df: pd.DataFrame, file_name: str|None=None)->dict:
    init_history_db();batch_id=datetime.utcnow().strftime('%Y%m%d_%H%M%S_promotion')
    dcol=_col(df,("日期","时间","统计日期","推广日期"));gid=_col(df,("商品ID","商品id","商品 Id","goods_id"));sp=_col(df,("实际成交花费(元)","实际成交花费","成交花费","花费","推广花费","消耗"));platform_col=_col(df,("平台",));store_col=_col(df,("店铺名称",))
    rows=[];dates=[]
    for _,r in df.fillna("").iterrows():
        raw=r.to_dict();platform=_text(raw.get(platform_col)) or '拼多多';store=_text(raw.get(store_col));g=_text(raw.get(gid));d=_date(raw.get(dcol));
        if not (g and d): continue
        dates.append(d)
        rows.append({"promo_key":f"{platform}|{store}|{d}|{g}","platform":platform,"store_name":store,"goods_id":g,"promo_date":d,"spend":pd.to_numeric(raw.get(sp),errors='coerce'),"raw_json":json.dumps(raw,ensure_ascii=False,default=str),"batch_id":batch_id,"uploaded_at":datetime.utcnow().isoformat()})
    eng=_engine(); inserted=updated=0
    with eng.begin() as conn:
        keys=[x['promo_key'] for x in rows]; ex=set(conn.execute(select(promotion_raw.c.promo_key).where(promotion_raw.c.promo_key.in_(keys))).scalars().all()) if keys else set(); updated=len(ex); inserted=len(keys)-len(ex)
        for i in range(0,len(rows),1000):
            ch=rows[i:i+1000]
            if ch: conn.execute(_upsert_stmt(promotion_raw,ch,'promo_key',eng.dialect.name))
        dmin,dmax=(min(dates),max(dates)) if dates else ("","")
        _insert_batch(conn,batch_id,'promotion',file_name,len(df),dmin,dmax,"")
    return {"batch_id":batch_id,"inserted":inserted,"updated":updated,"skipped":0,"date_min":dmin,"date_max":dmax,"row_count":len(df)}

def save_master_table_history(table_key:str,df:pd.DataFrame,file_name:str|None=None)->dict:
    mapping={"product_master":(product_master_current,lambda r:_text(r.get("标准产品ID"))),"sales_spec_mapping":(sales_spec_mapping_current,lambda r:_text(r.get("销售规格ID"))),"link_spec_mapping":(link_spec_mapping_current,lambda r:f"{_text(r.get('平台')) or '拼多多'}|{_text(r.get('店铺名称'))}|{_text(r.get('商品ID') or r.get('商品id'))}|{_text(r.get('商品规格'))}")}
    table,keyer=mapping[table_key];batch_id=datetime.utcnow().strftime(f'%Y%m%d_%H%M%S_{table_key}')
    by={}
    for _,r in df.fillna("").iterrows():
        raw=r.to_dict();k=keyer(raw)
        if k: by[k]={"row_key":k,"raw_json":json.dumps(raw,ensure_ascii=False,default=str),"uploaded_at":datetime.utcnow().isoformat()}
    rows=list(by.values());dup=max(len(df)-len(rows),0)
    eng=_engine();inserted=updated=0
    with eng.begin() as conn:
        keys=[x['row_key'] for x in rows]; ex=set(conn.execute(select(table.c.row_key).where(table.c.row_key.in_(keys))).scalars().all()) if keys else set(); updated=len(ex); inserted=len(keys)-len(ex)
        for i in range(0,len(rows),1000):
            ch=rows[i:i+1000]
            if ch: conn.execute(_upsert_stmt(table,ch,'row_key',eng.dialect.name))
        _insert_batch(conn,batch_id,table_key,file_name,len(df),"","","")
    return {"batch_id":batch_id,"inserted":inserted,"updated":updated,"skipped":0,"date_min":"","date_max":"","row_count":len(rows),"duplicates_removed":dup}

def save_cashflow_history(df:pd.DataFrame,file_name:str|None=None)->dict:
    init_history_db();batch_id=datetime.utcnow().strftime('%Y%m%d_%H%M%S_cashflow')
    tcol=_col(df,("时间",));fcol=_col(df,("流水类型",));acol=_col(df,("交易金额",));scol=_col(df,("交易摘要",));platform_col=_col(df,("平台",));store_col=_col(df,("店铺名称",))
    rows=[];dates=[];skipped=0
    for _,r in df.fillna("").iterrows():
        raw=r.to_dict();ft=_text(raw.get(fcol));sm=_text(raw.get(scol))
        if ("支出" not in ft) or ("推广支出" not in sm): skipped+=1; continue
        platform=_text(raw.get(platform_col)) or '拼多多';store=_text(raw.get(store_col));tm=_text(raw.get(tcol));d=_date(raw.get(tcol));dates += [d] if d else []
        amt=pd.to_numeric(raw.get(acol),errors='coerce')
        key=f"{platform}|{store}|{tm}|{ft}|{amt}|{sm}"
        rows.append({"cashflow_key":key,"platform":platform,"store_name":store,"cashflow_time":tm,"cashflow_date":d,"flow_type":ft,"transaction_amount":amt,"transaction_summary":sm,"raw_json":json.dumps(raw,ensure_ascii=False,default=str),"batch_id":batch_id,"uploaded_at":datetime.utcnow().isoformat()})
    eng=_engine();inserted=updated=0
    with eng.begin() as conn:
        keys=[x['cashflow_key'] for x in rows]; ex=set(conn.execute(select(cashflow_raw.c.cashflow_key).where(cashflow_raw.c.cashflow_key.in_(keys))).scalars().all()) if keys else set(); updated=len(ex); inserted=len(keys)-len(ex)
        for i in range(0,len(rows),1000):
            ch=rows[i:i+1000]
            if ch: conn.execute(_upsert_stmt(cashflow_raw,ch,'cashflow_key',eng.dialect.name))
        dmin,dmax=(min(dates),max(dates)) if dates else ("","")
        _insert_batch(conn,batch_id,'cashflow',file_name,len(df),dmin,dmax,"")
    return {"batch_id":batch_id,"inserted":inserted,"updated":updated,"skipped":skipped,"date_min":dmin,"date_max":dmax,"row_count":len(rows)}

def _load_raw_json_df(conn,table):
    rows=conn.execute(select(table.c.raw_json)).fetchall(); return pd.DataFrame([json.loads(r[0]) for r in rows if r[0]]) if rows else pd.DataFrame()

def load_history_tables(date_start=None,date_end=None)->dict[str,pd.DataFrame]:
    with _engine().begin() as conn:
        od=_load_raw_json_df(conn,orders_raw); pm=_load_raw_json_df(conn,product_master_current); sm=_load_raw_json_df(conn,sales_spec_mapping_current); lm=_load_raw_json_df(conn,link_spec_mapping_current); pr=_load_raw_json_df(conn,promotion_raw); cf=_load_raw_json_df(conn,cashflow_raw)
    if not od.empty:
        d=pd.to_datetime(od.get('订单成交时间'),errors='coerce').fillna(pd.to_datetime(od.get('支付时间'),errors='coerce'))
        if date_start is not None: od=od[d>=pd.to_datetime(date_start)]; d=d[d>=pd.to_datetime(date_start)]
        if date_end is not None: od=od[d<=pd.to_datetime(date_end)]
    if not pr.empty:
        dc=next((c for c in ('日期','统计日期','推广日期','时间') if c in pr.columns),None)
        if dc:
            d=pd.to_datetime(pr[dc],errors='coerce')
            if date_start is not None: pr=pr[d>=pd.to_datetime(date_start)]; d=d[d>=pd.to_datetime(date_start)]
            if date_end is not None: pr=pr[d<=pd.to_datetime(date_end)]
    if not cf.empty and '时间' in cf.columns:
        d=pd.to_datetime(cf['时间'],errors='coerce')
        if date_start is not None: cf=cf[d>=pd.to_datetime(date_start)]; d=d[d>=pd.to_datetime(date_start)]
        if date_end is not None: cf=cf[d<=pd.to_datetime(date_end)]
    return {"orders":od,"product_master":pm,"sales_spec_mapping":sm,"link_spec_mapping":lm,"promotion":pr,"cashflow":cf}

def list_upload_batches(limit=50)->pd.DataFrame:
    with _engine().begin() as conn: rows=conn.execute(select(upload_batches).order_by(upload_batches.c.id.desc()).limit(limit)).mappings().all()
    return pd.DataFrame(rows)

def get_history_stats()->dict:
    with _engine().begin() as conn:
        order_min,order_max=conn.execute(select(func.min(orders_raw.c.order_date),func.max(orders_raw.c.order_date))).one();promo_min,promo_max=conn.execute(select(func.min(promotion_raw.c.promo_date),func.max(promotion_raw.c.promo_date))).one();cash_min,cash_max=conn.execute(select(func.min(cashflow_raw.c.cashflow_date),func.max(cashflow_raw.c.cashflow_date))).one();order_count=conn.execute(select(func.count()).select_from(orders_raw)).scalar() or 0;promo_count=conn.execute(select(func.count()).select_from(promotion_raw)).scalar() or 0;cash_count=conn.execute(select(func.count()).select_from(cashflow_raw)).scalar() or 0
    return {"order_min":order_min,"order_max":order_max,"promo_min":promo_min,"promo_max":promo_max,"cashflow_min":cash_min,"cashflow_max":cash_max,"order_count":order_count,"promo_count":promo_count,"cashflow_count":cash_count}
