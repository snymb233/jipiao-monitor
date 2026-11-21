# -*- coding: utf-8 -*-
"""core.storage SQLite 存储测试，全部使用 tmp_path 临时库。"""
from core.models import FlightPrice
from core.storage import PriceStorage


def _make_price(price, platform="tuniu", date="2026-10-01", **kw):
    return FlightPrice(platform=platform, from_city="WUX", to_city="SIA",
                       depart_date=date, price=price, **kw)


def test_save_and_last_lowest(tmp_path):
    db = tmp_path / "prices.db"
    st = PriceStorage(str(db))
    st.save(_make_price(900))
    st.save(_make_price(500, platform="tongcheng"))
    st.save(_make_price(700, platform="fliggy"))
    row = st.last_lowest("WUX", "SIA", "2026-10-01")
    assert row["price"] == 500
    assert row["platform"] == "tongcheng"


def test_last_lowest_with_platform_filter(tmp_path):
    db = tmp_path / "prices.db"
    st = PriceStorage(str(db))
    st.save(_make_price(900, platform="tuniu"))
    st.save(_make_price(500, platform="tongcheng"))
    row = st.last_lowest("WUX", "SIA", "2026-10-01", platform="tuniu")
    assert row is not None
    assert row["price"] == 900
    assert row["platform"] == "tuniu"


def test_last_lowest_returns_none_when_missing(tmp_path):
    db = tmp_path / "prices.db"
    st = PriceStorage(str(db))
    assert st.last_lowest("WUX", "SIA", "2026-10-01") is None


def test_save_many(tmp_path):
    db = tmp_path / "prices.db"
    st = PriceStorage(str(db))
    st.save_many([_make_price(600, date="2026-10-01"),
                  _make_price(800, date="2026-10-02")])
    assert st.last_lowest("WUX", "SIA", "2026-10-01")["price"] == 600
    assert st.last_lowest("WUX", "SIA", "2026-10-02")["price"] == 800


def test_alert_state_roundtrip_and_conflict(tmp_path):
    db = tmp_path / "prices.db"
    st = PriceStorage(str(db))
    key = "WUX-SIA-2026-10-01"
    assert st.get_alert_state(key) is None
    st.set_alert_state(key, 500.0)
    assert st.get_alert_state(key) == 500.0
    # upsert：同 key 覆盖
    st.set_alert_state(key, 450.0)
    assert st.get_alert_state(key) == 450.0


def test_clear_alert_state(tmp_path):
    db = tmp_path / "prices.db"
    st = PriceStorage(str(db))
    key = "WUX-SIA-2026-10-01"
    st.set_alert_state(key, 500.0)
    st.clear_alert_state(key)
    assert st.get_alert_state(key) is None


def test_schema_initialized_idempotent(tmp_path):
    db = tmp_path / "prices.db"
    PriceStorage(str(db))
    PriceStorage(str(db))  # 再初始化不应抛错
    st = PriceStorage(str(db))
    st.save(_make_price(1000))
    assert st.last_lowest("WUX", "SIA", "2026-10-01")["price"] == 1000