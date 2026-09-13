# -*- coding: utf-8 -*-
"""跨平台比价：对途牛已抓到的组合中「最便宜的若干条」用同程再查一遍，
结果追加到 data/prices.csv（platform 列区分来源），用于验证低价是否真实。

用法: python compare_platforms.py --top 12
"""
import argparse
import csv
import os
import sys

import yaml

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
sys.path.insert(0, BASE)

from core.logger import setup_logger
from crawlers.tongcheng import TongchengCrawler

CSV_FILE = os.path.join(BASE, "data", "prices.csv")
CSV_HEADER = ["fetched_at", "from", "from_name", "to", "to_name",
              "depart_date", "price", "airline", "flight_no", "platform"]


def load_targets(top):
    """选出各 (航线,日期) 组合的最低价，取最便宜的 top 条"""
    best = {}
    if not os.path.exists(CSV_FILE):
        return []
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                p = float(row["price"])
            except (TypeError, ValueError):
                continue
            key = (row["from"], row["from_name"], row["to"], row["to_name"], row["depart_date"])
            if key not in best or p < best[key]:
                best[key] = p
    ranked = sorted(best.items(), key=lambda kv: kv[1])
    return [k for k, _ in ranked[:top]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()

    logger = setup_logger("logs/monitor.log", "jipiao")
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    targets = load_targets(args.top)
    if not targets:
        print("没有可比价的目标（prices.csv 为空）")
        return

    crawler_cfg = dict(cfg.get("crawler", {}))
    crawler_cfg.update({"max_attempts": 1, "delay_min": 2, "delay_max": 4,
                        "timeout_seconds": 90})
    crawler = TongchengCrawler(crawler_cfg, logger)

    os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
    new = not os.path.exists(CSV_FILE)
    n_ok = 0
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(CSV_HEADER)
        for fc, fn, tc, tn, date in targets:
            try:
                prices = crawler.fetch(fc, tc, [date])
            except Exception as ex:
                logger.warning("[比价] %s→%s %s 异常: %s", fn, tn, date, ex)
                continue
            if not prices:
                logger.warning("[比价] %s→%s %s 同程无结果", fn, tn, date)
                continue
            best = min(prices, key=lambda p: p.price)
            w.writerow([best.fetched_at, fc, fn, tc, tn, date, "%.0f" % best.price,
                        best.airline, best.flight_no, "tongcheng"])
            logger.info("[比价] %s→%s %s 同程 ¥%.0f", fn, tn, date, best.price)
            n_ok += 1
    print("比价完成: %d/%d 条拿到同程价格" % (n_ok, len(targets)))


if __name__ == "__main__":
    main()
