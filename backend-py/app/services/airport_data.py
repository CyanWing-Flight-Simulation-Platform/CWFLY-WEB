"""机场地面数据覆盖（/uploads/airports/）索引维护。

前端 3D/2D 图层按需请求 /uploads/airports/{ICAO}.json（超管在机场编辑器提交的覆盖数据），
不存在时回退到前端内置的 /airports/{ICAO}.json。为了让前端不用先对一个不存在的覆盖
文件发请求（会产生 404 噪声），服务端维护 index.json 列出当前存在的覆盖机场，前端只对
索引内的机场发覆盖请求。

- 覆盖目录：backend-py/app/data（main.py 中 mount 到 /uploads/airports）
- 索引文件：backend-py/app/data/index.json，内容 {"icaos": ["ZUUU", ...]}
"""
from __future__ import annotations

import json
import re
from pathlib import Path

AIRPORT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
INDEX_NAME = "index.json"
_CODE_RE = re.compile(r"^[A-Z0-9]{4}$")


def refresh_override_index() -> list[str]:
    """扫描覆盖目录并重写 index.json，返回当前覆盖的 ICAO 列表。

    幂等：目录不存在时创建空目录并写入空索引；任何单个文件的异常不影响其余文件。
    """
    AIRPORT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    codes: list[str] = []
    try:
        for path in AIRPORT_DATA_DIR.glob("*.json"):
            if path.name == INDEX_NAME:
                continue
            code = path.stem.upper()
            if _CODE_RE.match(code):
                codes.append(code)
    except OSError:
        codes = []
    codes.sort()
    try:
        (AIRPORT_DATA_DIR / INDEX_NAME).write_text(
            json.dumps({"icaos": codes}, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    except OSError:
        # 索引写失败只影响一次多余请求，不影响主流程
        return codes
    return codes
