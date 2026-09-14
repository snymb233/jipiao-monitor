# -*- coding: utf-8 -*-
"""由 data/prices.csv 生成 README.md 价格表（GitHub Actions 每次抓取后自动刷新）。

用法: python build_readme.py
"""
import csv
import os
from collections import defaultdict
from datetime import datetime

import yaml

BASE = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE, "data", "prices.csv")
README = os.path.join(BASE, "README.md")


def main():
    with open(os.path.join(BASE, "config.yaml"), "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    routes, dates, thresh = [], [], {}
    for r in cfg.get("routes", []):
        routes.append((r["from"], r.get("from_name", r["from"]),
                       r["to"], r.get("to_name", r["to"])))
        thresh[(r["from"], r["to"])] = float(r.get("alert_threshold", 0) or 0)
        for d in r.get("dates", []):
            if d not in dates:
                dates.append(d)
    dates.sort()
    seen, uniq_routes = set(), []
    for rt in routes:
        if rt not in seen:
            seen.add(rt)
            uniq_routes.append(rt)

    best = {}
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    p = float(row["price"])
                except (TypeError, ValueError):
                    continue
                key = (row["from"], row["to"], row["depart_date"])
                if key not in best or p < best[key][0]:
                    best[key] = (p, row.get("airline", ""), row.get("flight_no", ""))

    total = len(uniq_routes) * len(dates)
    title = str(cfg.get("title", "机票价格监控"))
    lines = ["# " + title, ""]
    if cfg.get("subtitle"):
        lines += [str(cfg["subtitle"]), ""]
    lines += ["- 数据源：途牛（纯接口抓取）",
              "- 云端执行：GitHub Actions，每 20 分钟抓一个航线×日期组合，约 %d 小时完成一轮全量刷新"
              % (total * 20 // 60 + 1),
              "- 最后更新：**%s**（UTC+8）" % datetime.now().strftime("%Y-%m-%d %H:%M"),
              "- 覆盖进度：**%d / %d**" % (len(best), total), ""]

    lines.append("## 价格总览（各航线每日最低价）")
    lines.append("")
    lines.append("| 航线 | " + " | ".join(d[5:].replace("-", "/") for d in dates) + " |")
    lines.append("|---" * (len(dates) + 1) + "|")
    for f, fn, t, tn in uniq_routes:
        cells = []
        row_vals = [(d, best[(f, t, d)][0]) for d in dates if (f, t, d) in best]
        cheapest = min(row_vals, key=lambda x: x[1])[0] if row_vals else None
        for d in dates:
            key = (f, t, d)
            if key not in best:
                cells.append("待抓")
                continue
            p, _, _ = best[key]
            mark = ""
            if thresh.get((f, t)) and p <= thresh[(f, t)]:
                mark = " 🔥"
            elif d == cheapest:
                mark = " ⭐"
            cells.append("¥%.0f%s" % (p, mark))
        lines.append("| %s → %s | %s |" % (fn, tn, " | ".join(cells)))

    if best:
        lines += ["", "## 目前最便宜的 5 个选择", ""]
        name_of = {(f, t): (fn, tn) for f, fn, t, tn in uniq_routes}
        ranked = sorted(best.items(), key=lambda kv: kv[1][0])[:5]
        for (f, t, d), (p, al, fno) in ranked:
            fn, tn = name_of.get((f, t), (f, t))
            lines.append("- **¥%.0f**　%s → %s　%s　%s %s" % (p, fn, tn, d, al, fno))

    lines += ["", "---", "",
              "⭐ = 该航线最低出发日　🔥 = 已低于提醒阈值", "",
              "数据文件：`data/prices.csv`（每次抓取追加一行，含全部历史价格）"]

    # 拼接使用指南（GUIDE.md 存在时附加在价格表之后，朋友 clone 后可随时查阅）
    guide = os.path.join(BASE, "GUIDE.md")
    if os.path.exists(guide):
        with open(guide, "r", encoding="utf-8") as f:
            lines += ["", "---", "", f.read().rstrip()]

    with open(README, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("README 已更新，覆盖 %d/%d" % (len(best), total))


if __name__ == "__main__":
    main()
