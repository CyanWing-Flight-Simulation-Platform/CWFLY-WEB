"""Backend pytest 最小护栏：不连接数据库、不访问网络。"""
from __future__ import annotations

import os

os.environ.setdefault("JWT_SECRET", "test-only-secret-" + "x" * 40)
os.environ.setdefault("ENV", "test")
os.environ.setdefault("DATABASE_URL", "mysql+asyncmy://test:test@127.0.0.1:3306/cwfly_test")
