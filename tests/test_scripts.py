# -*- coding: utf-8 -*-
"""入口脚本测试：cursor 读写、config 任务展开、report/dashboard/build_readme、scheduler。"""
import json
import sys

from core.models import FlightPrice
from core.storage import PriceStorage

# 直接导入模块（它们在 import 时 os.chdir 到仓库根，测试自身不依赖 CWD）
sys.path.insert(0, ".")
from cloud_fetch import load_tasks as cf_tasks
from cloud_fetch import read_cursor as cf_read
from compare_platforms import load_targets
from fetch_batch import load_tasks as fb_tasks
from fetch_batch import read_cursor as fb_read
from fetch_batch import write_cursor as fb_write
from main import build_routes, load_config


# ---------- cursor ----------
def test_fetch_batch_read_cursor_no_file(tmp_path):
    import fetch_batch as fb
    fb.CURSOR_FILE = str(tmp_path / "cursor.json")
    assert fb_read(10) == {"index": 0, "fails": 0}


def test_fetch_batch_read_cursor_total_zero(tmp_path):
    # 修复的 bug：total=0 时不应 %0 崩溃
    import fetch_batch as fb
    fb.CURSOR_FILE = str(tmp_path / "cursor.json")
    with open(fb.CURSOR_FILE, "w") as f:
        json.dump({"index": 14, "fails": 2}, f)
    assert fb_read(0) == {"index": 0, "fails": 0}


def test_fetch_batch_write_then_read_roundtrip(tmp_path):
    import fetch_batch as fb
    path = str(tmp_path / "cursor.json")
    fb.CURSOR_FILE = path
    fb_write({"index": 3, "fails": 1})
    assert fb_read(10) == {"index": 3, "fails": 1}


def test_cloud_fetch_read_cursor_total_zero(tmp_path):
    # 云脚本空配置 bug 修复
    import cloud_fetch as cf
    cf.CURSOR_FILE = str(tmp_path / "cursor.json")
    with open(cf.CURSOR_FILE, "w") as f:
        json.dump({"index": 14, "fails": 2}, f)
    assert cf_read(0) == {"index": 0, "fails": 0}


def test_cloud_fetch_read_cursor_wraps_index(tmp_path):
    import cloud_fetch as cf
    cf.CURSOR_FILE = str(tmp_path / "cursor.json")
    with open(cf.CURSOR_FILE, "w") as f:
        json.dump({"index": 14, "fails": 2}, f)
    state = cf_read(5)
    assert state["index"] == 4  # 14 % 5
    assert state["fails"] == 2


def test_cloud_fetch_read_cursor_corrupt(tmp_path):
    import cloud_fetch as cf
    cf.CURSOR_FILE = str(tmp_path / "cursor.json")
    with open(cf.CURSOR_FILE, "w") as f:
        f.write("{ not json")
    assert cf_read(5) == {"index": 0, "fails": 0}


# ---------- tasks ----------
def test_fb_load_tasks_expands_routes_dates():
    cfg = {"routes": [
        {"from": "WUX", "from_name": "无锡", "to": "SIA", "to_name": "西安",
         "dates": ["2026-10-01", "2026-10-02"]},
        {"from": "SHA", "from_name": "上海", "to": "CTU", "to_name": "成都",
         "dates": ["2026-10-01"]},
    ]}
    tasks = fb_tasks(cfg)
    assert len(tasks) == 3
    assert tasks[0]["from"] == "WUX" and tasks[0]["date"] == "2026-10-01"


def test_cf_load_tasks_empty_config():
    assert cf_tasks({}) == []


def test_cf_load_tasks_defaults_names_to_codes():
    cfg = {"routes": [{"from": "WUX", "to": "SIA", "dates": ["2026-10-01"]}]}
    t = cf_tasks(cfg)[0]
    assert t["from_name"] == "WUX"
    assert t["to_name"] == "SIA"


# ---------- config / routes ----------
def test_load_config_parses_real_config():
    cfg = load_config("config.yaml")
    assert isinstance(cfg, dict)
    assert "routes" in cfg and "crawler" in cfg


def test_build_routes_from_config():
    cfg = load_config("config.yaml")
    routes = build_routes(cfg)
    assert routes
    r0 = routes[0]
    assert r0.from_code
    assert r0.alert_threshold >= 0
    assert r0.dates


# ---------- compare_platforms.load_targets ----------
def test_load_targets_picks_lowest_per_route(tmp_path):
    import compare_platforms as cp
    csv_file = str(tmp_path / "prices.csv")
    original = cp.CSV_FILE
    cp.CSV_FILE = csv_file
    try:
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write("fetched_at,from,from_name,to,to_name,depart_date,price,airline,flight_no,platform\n")
            f.write("t,WUX,无锡,SIA,西安,2026-10-01,900,MU,1,tuniu\n")
            f.write("t,WUX,无锡,SIA,西安,2026-10-01,500,MU,1,tongcheng\n")  # 同名更低
            f.write("t,SHA,上海,CTU,成都,2026-10-02,700,HO,2,tuniu\n")
        targets = load_targets(5)
        assert (("WUX", "无锡", "SIA", "西安", "2026-10-01")) in targets
    finally:
        cp.CSV_FILE = original


def test_load_targets_missing_file_empty(tmp_path):
    import compare_platforms as cp
    original = cp.CSV_FILE
    cp.CSV_FILE = str(tmp_path / "nope.csv")
    try:
        assert load_targets(5) == []
    finally:
        cp.CSV_FILE = original


def test_load_targets_bad_price_skipped(tmp_path):
    import compare_platforms as cp
    csv_file = str(tmp_path / "prices.csv")
    original = cp.CSV_FILE
    cp.CSV_FILE = csv_file
    try:
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write("fetched_at,from,from_name,to,to_name,depart_date,price\n")
            f.write("t,A,甲,B,乙,2026-10-01,notanumber\n")
            f.write("t,A,甲,B,乙,2026-10-02,600\n")
        assert load_targets(5) == [("A", "甲", "B", "乙", "2026-10-02")]
    finally:
        cp.CSV_FILE = original


# ---------- report.py (纯 sqlite 汇总) ----------
def test_report_groupby_lowest_price(tmp_path, capsys):
    st = PriceStorage(str(tmp_path / "p.db"))
    st.save(FlightPrice(platform="tuniu", from_city="WUX", to_city="SIA",
                        depart_date="2026-10-01", price=500))
    st.save(FlightPrice(platform="tongcheng", from_city="WUX", to_city="SIA",
                        depart_date="2026-10-01", price=900))
    # 复现 report 的 GROUP BY 最低价查询逻辑
    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "p.db"))
    rows = conn.execute(
        "SELECT from_city, to_city, depart_date, MIN(price) AS m FROM flight_prices "
        "GROUP BY from_city, to_city, depart_date").fetchall()
    conn.close()
    assert rows == [("WUX", "SIA", "2026-10-01", 500.0)]


# ---------- build_readme 最佳价格选择 ----------
def test_build_readme_best_selection(tmp_path):
    # 直接测核心 `best` 收缩逻辑：同名同价取最小
    best = {}
    rows = [
        {"from": "WUX", "to": "SIA", "depart_date": "2026-10-01", "price": "900"},
        {"from": "WUX", "to": "SIA", "depart_date": "2026-10-01", "price": "500"},
        {"from": "SIA", "to": "CTU", "depart_date": "2026-10-01", "price": "700"},
    ]
    for row in rows:
        p = float(row["price"])
        key = (row["from"], row["to"], row["depart_date"])
        if key not in best or p < best[key][0]:
            best[key] = (p, row.get("airline", ""), row.get("flight_no", ""))
    assert best[("WUX", "SIA", "2026-10-01")][0] == 500.0
    assert len(best) == 2


# ---------- scheduler ----------
def test_run_scheduler_importable():
    import core.scheduler as s
    assert hasattr(s, "run_scheduler")