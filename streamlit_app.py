"""Streamlit Community Cloud 推荐入口文件。"""

from __future__ import annotations

import sys
from pathlib import Path

# 在 Cloud 上确保仓库根目录进入模块搜索路径。
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import main


if __name__ == "__main__":
    main()
