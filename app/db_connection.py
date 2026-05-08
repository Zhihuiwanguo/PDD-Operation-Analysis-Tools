from __future__ import annotations
import os
from pathlib import Path
from sqlalchemy import create_engine
import streamlit as st

_ENGINE = None
_URL = None

def _get_url() -> str:
    secret = None
    try:
        secret = st.secrets.get("DATABASE_URL")
    except Exception:
        secret = None
    return str(secret or os.getenv("DATABASE_URL") or f"sqlite:///{(Path('/tmp/aland_history') / 'aland_history_v2.db').resolve()}")

def get_engine():
    global _ENGINE, _URL
    url = _get_url()
    if _ENGINE is None or _URL != url:
        if url.startswith('sqlite'):
            Path('/tmp/aland_history').mkdir(parents=True, exist_ok=True)
            _ENGINE = create_engine(url, pool_pre_ping=True, connect_args={"check_same_thread": False})
        else:
            _ENGINE = create_engine(url, pool_pre_ping=True)
        _URL = url
    return _ENGINE

def get_backend_label() -> str:
    url = _get_url()
    if 'supabase.co' in url or 'postgres' in url:
        return 'Supabase/PostgreSQL'
    if url.startswith('sqlite'):
        return 'SQLite fallback'
    return 'Unknown'
