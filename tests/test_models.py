# -*- coding: utf-8 -*-
"""core.models 数据模型测试。"""
from core.models import FlightPrice, Route


def test_flight_price_defaults():
    fp = FlightPrice(platform="tuniu", from_city="WUX", to_city="SIA",
                     depart_date="2026-10-01", price=500.0)
    assert fp.platform == "tuniu"
    assert fp.airline == ""
    assert fp.flight_no == ""
    assert fp.depart_time == ""
    assert fp.arrive_time == ""
    assert fp.extra == ""
    assert fp.fetched_at  # 有默认值


def test_flight_price_to_dict():
    fp = FlightPrice(platform="tuniu", from_city="WUX", to_city="SIA",
                     depart_date="2026-10-01", price=500.0, airline="MU")
    d = fp.to_dict()
    assert d["platform"] == "tuniu"
    assert d["price"] == 500.0
    assert d["airline"] == "MU"
    assert "fetched_at" in d


def test_flight_price_mutable_defaults_do_not_share():
    a = FlightPrice(platform="a", from_city="x", to_city="y",
                    depart_date="d", price=1)
    b = FlightPrice(platform="b", from_city="x", to_city="y",
                    depart_date="d", price=2)
    # extra/airline 等均为 ""，不共享可变对象
    a.extra = "extra-a"
    assert b.extra == ""


def test_route_fields():
    r = Route(
        from_code="WUX", from_name="无锡", to_code="SIA", to_name="西安",
        dates=["2026-10-01", "2026-10-02"], alert_threshold=500,
    )
    assert r.from_code == "WUX"
    assert r.dates == ["2026-10-01", "2026-10-02"]
    assert r.alert_threshold == 500


def test_route_alert_threshold_default_zero():
    r = Route(from_code="WUX", from_name="无锡", to_code="SIA", to_name="西安",
              dates=["2026-10-01"])
    assert r.alert_threshold == 0