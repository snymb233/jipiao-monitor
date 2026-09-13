# -*- coding: utf-8 -*-
"""把云端 (GitHub Actions) 抓取的 data/prices.csv 同步进本地 SQLite，
使本地 HTML 看板同时展示云端与本地抓到的数据。

用法: python sync_cloud.py [--csv data/prices.csv] [--db data/prices.db]
重复行按 (from,to,date,fetched_at,price) 去重，可反复执行。
"""
import argparse
import csv
import os
import sqlite3
import urllib.request
from pathlib import Path

REPO = "snymb233/jipiao-monitor"


def get_token() -> str:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if tok:
        return tok.strip()
    cred = Path.home() / ".git-credentials"
    if cred.exists():
        for line in cred.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "@github.com" in line and "://" in line:
                part = line.split("://", 1)[1]
                if "@" in part:
                    return part.split("@", 1)[0].split(":", 1)[-1].strip()
    return ""


def download_csv(csv_path: Path) -> bool:
    """从 GitHub 私有仓库下载 data/prices.csv"""
    token = get_token()
    if not token:
        print("未找到 GitHub 令牌（GITHUB_TOKEN 环境变量或 ~/.git-credentials）")
        return False
    url = "https://api.github.com/repos/%s/contents/data/prices.csv?ref=main" % REPO
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github.raw",
        "User-Agent": "jipiao-sync",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read().decode("utf-8-sig")
    except Exception as ex:
        print("下载失败:", ex)
        return False
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(data, encoding="utf-8")
    print("已下载云端 CSV，共 %d 行" % (len(data.splitlines()) - 1))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/prices.csv")
    ap.add_argument("--db", default="data/prices.db")
    ap.add_argument("--download", action="store_true", help="先从 GitHub 下载最新 CSV")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if args.download:
        if not download_csv(csv_path):
            if not csv_path.exists():
                return
            print("改用本地已有的 CSV")
    if not csv_path.exists():
        print("云端 CSV 不存在:", csv_path)
        return

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS flight_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL, from_city TEXT NOT NULL, to_city TEXT NOT NULL,
            depart_date TEXT NOT NULL, price REAL NOT NULL, airline TEXT,
            flight_no TEXT, depart_time TEXT, arrive_time TEXT,
            fetched_at TEXT NOT NULL, extra TEXT)
    """)

    added = 0
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                price = float(row["price"])
            except (TypeError, ValueError, KeyError):
                continue
            key = (row["from"], row["to"], row["depart_date"], row["fetched_at"], price)
            exists = cur.execute(
                "SELECT 1 FROM flight_prices WHERE from_city=? AND to_city=? "
                "AND depart_date=? AND fetched_at=? AND price=? LIMIT 1", key).fetchone()
            if exists:
                continue
            cur.execute(
                "INSERT INTO flight_prices (platform, from_city, to_city, depart_date,"
                " price, airline, flight_no, depart_time, arrive_time, fetched_at, extra)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (row.get("platform") or "tuniu-cloud", row["from"], row["to"],
                 row["depart_date"], price,
                 row.get("airline", ""), row.get("flight_no", ""), "", "",
                 row["fetched_at"], ""))
            added += 1
    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM flight_prices").fetchone()[0]
    conn.close()
    print("同步完成: 新增 %d 行, 库内共 %d 行" % (added, total))


if __name__ == "__main__":
    main()
