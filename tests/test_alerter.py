# -*- coding: utf-8 -*-
"""core.alerter 低价提醒 + 去抖逻辑测试。"""
import logging

from core.alerter import Alerter
from core.models import FlightPrice, Route

logger = logging.getLogger("test.alerter")
logger.addHandler(logging.NullHandler())


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def send(self, title, desp):
        self.calls.append((title, desp))
        return True


class FakeStorage:
    """内存版 alert_state 存储。"""

    def __init__(self):
        self.state = {}

    def get_alert_state(self, key):
        return self.state.get(key)

    def set_alert_state(self, key, price):
        self.state[key] = price

    def clear_alert_state(self, key):
        self.state.pop(key, None)


def _route(threshold=0, dates=("2026-10-01",)):
    return Route(from_code="WUX", from_name="无锡", to_code="SIA", to_name="西安",
                 dates=list(dates), alert_threshold=threshold)


def _prices(*vals):
    return [FlightPrice(platform="tuniu", from_city="WUX", to_city="SIA",
                        depart_date="2026-10-01", price=v) for v in vals]


def test_should_push_first_time():
    a = Alerter(logger)
    ok, reason = a._should_push(500.0, None)
    assert ok and reason == "首次"


def test_should_push_drop_large():
    a = Alerter(logger, push_drop_min=30)
    ok, reason = a._should_push(450.0, 500.0)
    assert ok and reason == "降¥50"


def test_should_push_drop_below_minimum():
    a = Alerter(logger, push_drop_min=30)
    ok, reason = a._should_push(480.0, 500.0)
    assert not ok
    assert "波动" in reason


def test_should_push_rise_large():
    a = Alerter(logger, push_rise_min=50)
    ok, reason = a._should_push(580.0, 500.0)
    assert ok and reason == "涨¥80"


def test_should_push_small_fluctuation_no():
    a = Alerter(logger, push_drop_min=30, push_rise_min=50)
    ok, _ = a._should_push(510.0, 500.0)
    assert not ok


def test_no_prices_noop():
    a = Alerter(logger, notifier=FakeNotifier(), storage=FakeStorage())
    a.check_and_alert(_route(threshold=500), [])
    # 无价格时不推送、不写入状态


def test_above_threshold_clears_state_and_skips_push():
    store = FakeStorage()
    notifier = FakeNotifier()
    a = Alerter(logger, notifier=notifier, storage=store)
    store.state["WUX-SIA-2026-10-01"] = 450.0
    # 当前价 800 > 阈值 500 → 清除状态，不推送
    a._handle_threshold(_route(threshold=500), _prices(800))
    assert "WUX-SIA-2026-10-01" not in store.state
    assert notifier.calls == []


def test_below_threshold_first_push_and_state_recorded():
    store = FakeStorage()
    notifier = FakeNotifier()
    a = Alerter(logger, notifier=notifier, storage=store)
    a._handle_threshold(_route(threshold=500), _prices(450))
    assert len(notifier.calls) == 1
    assert store.state.get("WUX-SIA-2026-10-01") == 450.0


def test_below_threshold_small_change_no_repush():
    store = FakeStorage()
    notifier = FakeNotifier()
    store.state["WUX-SIA-2026-10-01"] = 450.0
    a = Alerter(logger, notifier=notifier, storage=store)
    # 445 距上次 450 只降 5，低于 push_drop_min=30 → 不推
    a._handle_threshold(_route(threshold=500), _prices(445))
    assert notifier.calls == []
    # 状态不被覆盖（仍保留上次推送价）
    assert store.state["WUX-SIA-2026-10-01"] == 450.0


def test_large_drop_triggers_repush():
    store = FakeStorage()
    notifier = FakeNotifier()
    store.state["WUX-SIA-2026-10-01"] = 500.0
    a = Alerter(logger, notifier=notifier, storage=store)
    a._handle_threshold(_route(threshold=500), _prices(400))
    assert len(notifier.calls) == 1
    assert store.state["WUX-SIA-2026-10-01"] == 400.0


def test_no_storage_no_crash_still_pushes():
    notifier = FakeNotifier()
    a = Alerter(logger, notifier=notifier, storage=None)
    a._handle_threshold(_route(threshold=500), _prices(450))
    assert len(notifier.calls) == 1


def test_build_view_url_all_platforms():
    a = Alerter(logger)
    r = _route()
    url = a._build_view_url(r, "2026-10-01", "ctrip")
    assert "m.ctrip.com" in url and "WUX" in url and "2026-10-01" in url
    url = a._build_view_url(r, "2026-10-01", "tongcheng")
    assert "m.ly.com" in url
    url = a._build_view_url(r, "2026-10-01", "qunar")
    assert "touch.qunar.com" in url and "无锡" in url
    url = a._build_view_url(r, "2026-10-01", "tuniu")
    assert "m.tuniu.com" in url
    url = a._build_view_url(r, "2026-10-01", "fliggy")
    assert "outfliggys.m.taobao.com" in url
    url = a._build_view_url(r, "2026-10-01", "unknown")
    assert "fliggy" in url or "taobao" in url  # 默认 fliggy


def test_push_message_contains_price_and_threshold(tmp_path, caplog):
    notifier = FakeNotifier()
    store = FakeStorage()
    a = Alerter(logger, notifier=notifier, storage=store)
    r = _route(threshold=500)
    a.check_and_alert(r, _prices(450))
    assert len(notifier.calls) == 1
    title, desp = notifier.calls[0]
    assert "¥450" in title
    assert "无锡" in title and "西安" in title
    assert "¥500" in desp  # 阈值在 body


def test_compare_platforms_logs_existing_price(tmp_path, caplog):
    a = Alerter(logger)
    # 同日期多平台对比，去抖逻辑不参与（仅日志）
    prices = [
        FlightPrice(platform="tuniu", from_city="WUX", to_city="SIA",
                    depart_date="2026-10-01", price=900),
        FlightPrice(platform="tongcheng", from_city="WUX", to_city="SIA",
                    depart_date="2026-10-01", price=500),
    ]
    with caplog.at_level(logging.INFO):
        a._compare_platforms(_route(), prices)
    assert any("tongcheng" in r.message for r in caplog.records)


def test_compare_dates_single_date_skipped(tmp_path, caplog):
    a = Alerter(logger)
    with caplog.at_level(logging.INFO):
        a._compare_dates(_route(dates=("2026-10-01",)), _prices(900))
    assert all("[多日期]" not in r.message for r in caplog.records)