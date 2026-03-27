"""数据加载。"""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import pandas as pd

from app.constants import UPLOAD_SPEC_MAP
from app.utils import clean_columns


def _read_excel_with_best_sheet(file_obj: BinaryIO | str | Path, key: str | None) -> pd.DataFrame:
    if key is None or key not in UPLOAD_SPEC_MAP:
        return pd.read_excel(file_obj)

    expected = set(UPLOAD_SPEC_MAP[key].required_columns)
    xls = pd.ExcelFile(file_obj)
    best_sheet = xls.sheet_names[0]
    best_score = -1

    for sheet in xls.sheet_names:
        preview = clean_columns(pd.read_excel(xls, sheet_name=sheet, nrows=20))
        score = len(expected.intersection(set(preview.columns)))
        if score > best_score:
            best_score = score
            best_sheet = sheet

    return pd.read_excel(xls, sheet_name=best_sheet)


def load_table(file_obj: BinaryIO | str | Path, file_name: str, key: str | None = None) -> pd.DataFrame:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(file_obj)
    elif suffix in {".xlsx", ".xls"}:
        df = _read_excel_with_best_sheet(file_obj, key)
    else:
        raise ValueError(f"暂不支持的文件类型: {suffix}")

    df = clean_columns(df)
    return df


def load_sample_tables(sample_dir: str) -> dict[str, pd.DataFrame]:
    base = Path(sample_dir)
    mapping = {
        "product_master": "艾兰得标准产品主档表.xlsx",
        "sales_spec_mapping": "艾兰得销售规格映射表.xlsx",
        "link_spec_mapping": "拼多多艾兰得店铺链接规格映射表.xlsx",
        "orders": "订单表样例.csv",
        "promotion": "商品推广表样例.xlsx",
        "cashflow": "流水明细样例.xls",
    }
    result: dict[str, pd.DataFrame] = {}
    for key, filename in mapping.items():
        path = base / filename
        result[key] = load_table(path, filename, key=key)
    return result
