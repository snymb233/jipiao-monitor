# -*- coding: utf-8 -*-
"""单组合抓取（短突发模式）。

每次运行只抓取 config.yaml 中的下一个 (航线 × 日期) 组合，抓完即退出。
由 Windows 计划任务每 10 分钟调用一次，因此天然满足途牛的频率限制
（约 1 次 / 10 分钟），也避免了长驻进程被意外终止导致整轮丢失的问题。

游标状态保存在 .cursor.json；同一组合连续失败 MAX_FAILS 次后才跳过，
保证受临时风控影响的组合会在后续运行中补抓。
"""
import json
import os
import sys

import yaml

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
sys.path.insert(0, BASE)

from core.logger import setup_logger
from core.storage import PriceStorage
from crawlers.tuniu import TuniuCrawler

CURSOR_FILE = ".cursor.json"
MAX_FAILS = 2


def load_tasks(cfg: dict):
    tasks = []
    for r in cfg.get("routes", []):
        for d in r.get("dates", []):
            tasks.append({
                "from": r["from"], "from_name": r.get("from_name", r["from"]),
                "to": r["to"], "to_name": r.get("to_name", r["to"]),
                "date": d,
            })
    return tasks


def read_cursor(total: int) -> dict:
    if os.path.exists(CURSOR_FILE):
        try:
            with open(CURSOR_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data.get("index"), int):
                return {"index": data["index"] % total, "fails": int(data.get("fails", 0))}
        except Exception:
            pass
    return {"index": 0, "fails": 0}


def write_cursor(state: dict):
    tmp = CURSOR_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, CURSOR_FILE)


def main():
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    tasks = load_tasks(cfg)
    if not tasks:
        print("config.yaml 中没有配置任何航线")
        return

    logger = setup_logger(cfg.get("output", {}).get("log_path", "logs/monitor.log"), "jipiao")
    storage = PriceStorage(cfg.get("output", {}).get("db_path", "data/prices.db"))

    state = read_cursor(len(tasks))
    task = tasks[state["index"]]
    label = "%s(%s)->%s(%s) %s" % (task["from_name"], task["from"], task["to_name"], task["to"], task["date"])

    # 突发模式：不做重试等待，失败交给下一次调度
    crawler_cfg = dict(cfg.get("crawler", {}))
    crawler_cfg.update({"max_attempts": 1, "block_max_attempts": 1,
                        "rate_limit": False, "delay_min": 0, "delay_max": 0})
    crawler = TuniuCrawler(crawler_cfg, logger)

    try:
        prices = crawler.fetch(task["from"], task["to"], [task["date"]])
    except Exception as ex:
        logger.warning("[批次] %s 抓取异常: %s", label, ex)
        prices = []

    if prices:
        storage.save_many(prices)
        low = min(p.price for p in prices)
        best = min(prices, key=lambda p: p.price)
        logger.info("[批次] %s 完成 最低价 ¥%.0f (%s %s)", label, low, best.airline, best.flight_no)
        state["index"] = (state["index"] + 1) % len(tasks)
        state["fails"] = 0
    else:
        state["fails"] += 1
        logger.warning("[批次] %s 未抓到价格 (连续失败 %d 次)", label, state["fails"])
        if state["fails"] > MAX_FAILS:
            logger.warning("[批次] %s 连续失败超上限, 跳过进入下一组合", label)
            state["index"] = (state["index"] + 1) % len(tasks)
            state["fails"] = 0

    write_cursor(state)


if __name__ == "__main__":
    main()
