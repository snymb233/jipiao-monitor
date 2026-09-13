"""汇总当前价格库: 每条航线每天的最低价 + 历史最低价, 输出 Markdown 简报。

用法: python report.py [--db data/prices.db] [--markdown out.md] [--days 3]
"""
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/prices.db")
    ap.add_argument("--markdown", default="", help="可选: 同时写入 md 文件")
    ap.add_argument("--csv", default="", help="可选: 同时写入 csv 文件")
    args = ap.parse_args()

    if not Path(args.db).exists():
        print("数据库不存在")
        raise SystemExit(1)

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT from_city, to_city, depart_date,
               MIN(price) AS min_price,
               COUNT(*)   AS n
        FROM flight_prices
        GROUP BY from_city, to_city, depart_date
        ORDER BY from_city, to_city, depart_date
    """).fetchall()

    # 每条航线的整体历史最低
    hist = {}
    for f, t, d, p, n in cur.execute("""
        SELECT from_city, to_city, MIN(depart_date), MIN(price), COUNT(*)
        FROM flight_prices GROUP BY from_city, to_city
    """).fetchall():
        hist[(f, t)] = p

    latest = cur.execute("""
        SELECT from_city, to_city, depart_date, price, fetched_at
        FROM flight_prices p
        WHERE fetched_at = (
            SELECT MAX(fetched_at) FROM flight_prices
            WHERE from_city=p.from_city AND to_city=p.to_city AND depart_date=p.depart_date
        )
        ORDER BY from_city, to_city, depart_date
    """).fetchall()

    lines = []
    lines.append(f"# 机票价格简报 {datetime.now():%Y-%m-%d %H:%M}")
    lines.append("")
    lines.append("| 出发 | 到达 | 日期 | 最低价 | 数据来源(平台数) |")
    lines.append("|---|---|---|---|---|")
    for f, t, d, p, n in rows:
        lines.append(f"| {f} | {t} | {d} | ¥{p:.0f} | {n} |")
    lines.append("")

    # 每个日期的跨航线最低 5 条
    lines.append("## 各出发日最低 5 条航线")
    dates = sorted({r[2] for r in rows})
    for d in dates:
        day_rows = sorted([r for r in rows if r[2] == d], key=lambda r: r[3])
        lines.append(f"\n**{d}**")
        lines.append("| 航线 | 最低价 |")
        lines.append("|---|---|")
        for f, t, dd, p, n in day_rows[:5]:
            lines.append(f"| {f}→{t} | ¥{p:.0f} |")

    text = "\n".join(lines)
    print(text)

    if args.markdown:
        Path(args.markdown).write_text(text, encoding="utf-8")
    if args.csv:
        import csv as _csv
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as fh:
            w = _csv.writer(fh)
            w.writerow(["from", "to", "date", "min_price"])
            w.writerows(rows)
    conn.close()


if __name__ == "__main__":
    main()
