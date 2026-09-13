# -*- coding: utf-8 -*-
"""云端（GitHub Actions）单组合抓取。

与本地 fetch_batch.py 的区别:
  - 数据写入 CSV (data/prices.csv) 而不是 SQLite，便于直接用 git 提交与管理
  - 每次运行只抓一个 (航线 × 日期) 组合后退出，游标在 data/cursor.json
  - 不做重试等待: 失败留给下一个调度周期（约 20 分钟后）
"""
import csv
import json
import os
import sys

import yaml

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
sys.path.insert(0, BASE)

from core.logger import setup_logger
from crawlers.tuniu import TuniuCrawler

DATA_DIR = "data"
CURSOR_FILE = os.path.join(DATA_DIR, "cursor.json")
CSV_FILE = os.path.join(DATA_DIR, "prices.csv")
CSV_HEADER = ["fetched_at", "from", "from_name", "to", "to_name",
              "depart_date", "price", "airline", "flight_no"]
MAX_FAILS = 3


def load_tasks(cfg):
    tasks = []
    for r in cfg.get("routes", []):
        for d in r.get("dates", []):
            tasks.append({
                "from": r["from"], "from_name": r.get("from_name", r["from"]),
                "to": r["to"], "to_name": r.get("to_name", r["to"]),
                "date": d,
            })
    return tasks


def read_cursor(total):
    if os.path.exists(CURSOR_FILE):
        try:
            with open(CURSOR_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d.get("index"), int):
                return {"index": d["index"] % total, "fails": int(d.get("fails", 0))}
        except Exception:
            pass
    return {"index": 0, "fails": 0}


def write_cursor(state):
    with open(CURSOR_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def append_rows(rows):
    os.makedirs(DATA_DIR, exist_ok=True)
    new = not os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(CSV_HEADER)
        w.writerows(rows)


def main():
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    tasks = load_tasks(cfg)
    logger = setup_logger("logs/monitor.log", "jipiao")

    state = read_cursor(len(tasks))
    t = tasks[state["index"]]
    label = "%s(%s)->%s(%s) %s" % (t["from_name"], t["from"], t["to_name"], t["to"], t["date"])

    crawler_cfg = dict(cfg.get("crawler", {}))
    crawler_cfg.update({"max_attempts": 1, "block_max_attempts": 1,
                        "rate_limit": False, "delay_min": 0, "delay_max": 0})
    crawler = TuniuCrawler(crawler_cfg, logger)

    prices = []
    try:
        prices = crawler.fetch(t["from"], t["to"], [t["date"]])
    except Exception as ex:
        logger.warning("[云端] %s 抓取异常: %s", label, ex)

    if prices:
        best = min(prices, key=lambda p: p.price)
        append_rows([[
            best.fetched_at, t["from"], t["from_name"], t["to"], t["to_name"],
            t["date"], "%.0f" % best.price, best.airline, best.flight_no,
        ]])
        logger.info("[云端] %s 完成 最低价 ¥%.0f (%s %s)",
                    label, best.price, best.airline, best.flight_no)
        state["index"] = (state["index"] + 1) % len(tasks)
        state["fails"] = 0
    else:
        state["fails"] += 1
        logger.warning("[云端] %s 未抓到价格 (连续失败 %d 次)", label, state["fails"])
        if state["fails"] > MAX_FAILS:
            logger.warning("[云端] %s 连续失败超上限, 跳过", label)
            state["index"] = (state["index"] + 1) % len(tasks)
            state["fails"] = 0

    write_cursor(state)
    # 供 workflow 读取
    print("label=%s ok=%s" % (label, bool(prices)))


if __name__ == "__main__":
    main()
