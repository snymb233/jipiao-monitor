# -*- coding: utf-8 -*-
"""保护性导入：crawlers 依赖 httpx/playwright，但解析函数均为纯逻辑（无网络/浏览器）。

测试通过全量 JSON 样本驱动各平台解析器，断言价格提取与去抖/去重逻辑。
"""
import os
import sys

# 仓库根加入路径，保证 `from core.xxx import ...` / `from crawlers.xxx import ...` 可导入
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)