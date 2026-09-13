# -*- coding: utf-8 -*-
"""生成机票价格看板 (HTML)，覆盖 config.yaml 中的全部航线×日期组合。

用法: python dashboard.py [--db data/prices.db] [--out ../output/机票监控看板.html]
未抓到价格的组合显示为「待抓」，便于一眼看出监控覆盖进度。
"""
import argparse
import html
import sqlite3
from datetime import datetime
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parent


def load_tasks(cfg):
    tasks = []
    for r in cfg.get("routes", []):
        for d in r.get("dates", []):
            tasks.append((r["from"], r.get("from_name", r["from"]),
                          r["to"], r.get("to_name", r["to"]), d,
                          float(r.get("alert_threshold", 0) or 0)))
    return tasks


def load_prices(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    best = {}
    for f, t, d, p, al, fn, plat in cur.execute("""
        SELECT p.from_city, p.to_city, p.depart_date, p.price, p.airline, p.flight_no, p.platform
        FROM flight_prices p
        WHERE p.price = (SELECT MIN(price) FROM flight_prices
                         WHERE from_city=p.from_city AND to_city=p.to_city
                           AND depart_date=p.depart_date)
        GROUP BY p.from_city, p.to_city, p.depart_date
    """).fetchall():
        best[(f, t, d)] = (p, al or "", fn or "", plat or "")
    # 各组合的历史最低 & 最新一次价格(用于判断涨跌)
    hist_min, latest = {}, {}
    for f, t, d, p in cur.execute("""
        SELECT from_city, to_city, depart_date, MIN(price)
        FROM flight_prices GROUP BY from_city, to_city, depart_date
    """).fetchall():
        hist_min[(f, t, d)] = p
    for f, t, d, p in cur.execute("""
        SELECT p.from_city, p.to_city, p.depart_date, p.price
        FROM flight_prices p
        WHERE p.fetched_at = (
            SELECT MAX(fetched_at) FROM flight_prices
            WHERE from_city=p.from_city AND to_city=p.to_city AND depart_date=p.depart_date
        )
    """).fetchall():
        latest[(f, t, d)] = p
    conn.close()
    return best, hist_min, latest


PLAT = {"tuniu": "途牛", "tuniu-cloud": "途牛", "tongcheng": "同程"}


def render(cfg, db_path):
    tasks = load_tasks(cfg)
    best, hist_min, latest = load_prices(db_path)
    dates = sorted({t[4] for t in tasks})
    routes = []
    seen = set()
    for f, fn, t, tn, d, th in tasks:
        if (f, t) not in seen:
            seen.add((f, t))
            routes.append((f, fn, t, tn, th))

    covered = sum(1 for t in tasks if (t[0], t[2], t[4]) in best)
    total = len(tasks)

    rows_html = []
    for f, fn, t, tn, th in routes:
        cells = []
        row_prices = []
        for d in dates:
            key = (f, t, d)
            if key in best:
                p, al, fno, plat = best[key]
                row_prices.append((d, p, al, fno))
        cheap_dates = {d for d, p, _, _ in sorted(row_prices, key=lambda x: x[1])[:1]}
        for d in dates:
            key = (f, t, d)
            if key not in best:
                cells.append('<td class="cell miss">待抓</td>')
                continue
            p, al, fno, plat = best[key]
            cls = "cell"
            if th and p <= th:
                cls += " great"
            elif d in cheap_dates:
                cls += " good"
            delta = ""
            lp = latest.get(key)
            hp = hist_min.get(key)
            if lp is not None and hp is not None and lp > hp + 1:
                delta = '<span class="delta up">较最低 +¥%.0f</span>' % (lp - hp)
            elif lp is not None and hp is not None and lp == hp:
                delta = '<span class="delta flat">当前即最低</span>'
            cells.append(
                '<td class="%s"><b>¥%.0f</b><span class="meta">%s %s %s</span>%s</td>'
                % (cls, p, html.escape(al), html.escape(fno),
                   PLAT.get(plat, ''), delta))
        rows_html.append(
            '<tr><td class="route">%s → %s</td>%s</tr>'
            % (html.escape(fn), html.escape(tn), "".join(cells)))

    # 推荐: 已抓到的组合里最便宜的 5 条
    ranked = sorted(
        [((f, t, d), v) for (f, t, d), v in best.items()], key=lambda kv: kv[1][0])[:5]
    name_of = {(t[0], t[2]): (t[1], t[3]) for t in tasks}
    rec_html = "".join(
        '<li><b>%s → %s</b> <span class="date">%s</span> <b class="price">¥%.0f</b>'
        '<span class="meta">%s %s</span></li>'
        % (html.escape(name_of.get((f, t), (f, t))[0]),
           html.escape(name_of.get((f, t), (f, t))[1]), d, v[0],
           html.escape(v[1]), html.escape(v[2]))
        for (f, t, d), v in ranked)

    pct = covered * 100 // total if total else 0
    head_dates = "".join('<th>%s</th>' % d[5:].replace("-", "/") for d in dates)

    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>机票价格监控看板</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--line:#e6e8ec;--txt:#1b1f24;--muted:#6b7280;--good:#0a8a4a;--great:#067a3d;--accent:#2563eb}}
*{{box-sizing:border-box}}
body{{margin:0;padding:28px;background:var(--bg);color:var(--txt);
font-family:"Microsoft YaHei","PingFang SC",-apple-system,Segoe UI,sans-serif}}
.wrap{{max-width:960px;margin:0 auto}}
h1{{font-size:22px;margin:0 0 4px}}
.sub{{color:var(--muted);font-size:13px;margin-bottom:18px}}
.bar{{height:6px;background:var(--line);border-radius:999px;overflow:hidden;margin:8px 0 22px}}
.bar i{{display:block;height:100%;background:var(--accent);width:{pct}%}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th,td{{border-bottom:1px solid var(--line);padding:10px 8px;text-align:left}}
th{{color:var(--muted);font-weight:600;font-size:13px}}
.route{{font-weight:600;white-space:nowrap}}
.cell{{min-width:120px}}
.cell b{{font-size:15px}}
.cell .meta{{display:block;color:var(--muted);font-size:11px;margin-top:2px}}
.cell .delta{{display:block;font-size:11px;margin-top:2px}}
.delta.up{{color:#b45309}} .delta.flat{{color:var(--good)}}
.cell.good b{{color:var(--good)}} .cell.great b{{color:var(--great);font-weight:800}}
.cell.miss{{color:#9aa1ac;font-size:13px}}
ol{{margin:0;padding-left:20px}} li{{margin:6px 0;font-size:14px}}
li .date{{color:var(--muted);font-size:12px;margin:0 6px}}
li .price{{color:var(--great)}} li .meta{{color:var(--muted);font-size:12px;margin-left:6px}}
.foot{{color:var(--muted);font-size:12px;line-height:1.7}}
</style></head><body><div class="wrap">
<h1>机票价格监控看板</h1>
<div class="sub">苏州周边（无锡 / 上海 / 盐城 / 扬州）→ 兰州 / 西安 / 成都 · 数据源：途牛 · 更新于 {now}</div>
<div class="bar"><i></i></div>
<div class="card"><table>
<tr><th>航线</th>{head_dates}</tr>{rows}
</table></div>
<div class="card"><b>当前最便宜的 5 个选择</b><ol>{rec}</ol></div>
<div class="foot">
绿色加粗 = 该航线最低出发日；深绿 = 已低于提醒阈值（西安 ¥500 / 兰州、成都 ¥600）。<br>
覆盖进度 {covered}/{total}（每 10 分钟补抓一个组合，约 6 小时完成一轮全量刷新）。<br>
监控由 Windows 计划任务 JiPiaoMonitor 驱动，每 4 小时自动更新本看板。
</div>
</div></body></html>""".format(
        pct=pct, now=datetime.now().strftime("%Y-%m-%d %H:%M"),
        head_dates=head_dates, rows="".join(rows_html), rec=rec_html,
        covered=covered, total=total)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(BASE / "data" / "prices.db"))
    ap.add_argument("--config", default=str(BASE / "config.yaml"))
    ap.add_argument("--out", default=str(BASE.parent / "output" / "机票监控看板.html"))
    args = ap.parse_args()

    with open(args.config, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(cfg, args.db), encoding="utf-8")
    print("看板已生成:", out)


if __name__ == "__main__":
    main()
