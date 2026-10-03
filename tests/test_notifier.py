# -*- coding: utf-8 -*-
"""core.notifier Server酱 推送测试（mock urllib，不产生真实网络请求）。"""
import logging
from unittest import mock

from core.notifier import ServerChanNotifier, build_notifier

logger = logging.getLogger("test.notifier")
logger.addHandler(logging.NullHandler())


class _FakeResp:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_send_success():
    n = ServerChanNotifier("testkey", logger)
    with mock.patch("urllib.request.urlopen",
                    return_value=_FakeResp(b'{"code":0,"data":{}}')):
        assert n.send("标题", "内容") is True


def test_send_failure_code():
    n = ServerChanNotifier("testkey", logger)
    with mock.patch("urllib.request.urlopen",
                    return_value=_FakeResp(b'{"code":400,"msg":"bad"}')):
        assert n.send("标题") is False


def test_send_empty_key_returns_false_no_network():
    n = ServerChanNotifier("  ", logger)
    with mock.patch("urllib.request.urlopen") as m:
        assert n.send("标题") is False
        m.assert_not_called()


def test_send_exception_returns_false():
    n = ServerChanNotifier("testkey", logger)
    with mock.patch("urllib.request.urlopen", side_effect=ConnectionError("down")):
        assert n.send("标题") is False


def test_title_truncated_to_60_chars():
    n = ServerChanNotifier("testkey", logger)
    long = "x" * 100
    captured = {}

    def fake_urlopen(req, timeout=10):
        captured["title"] = req.data
        return _FakeResp(b'{"code":0}')

    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        n.send(long)
    title_field = captured["title"].decode("utf-8").split("&")[0]
    assert title_field.startswith("title=")
    assert len(title_field) <= 6 + 60  # "title=" + 60 char


def test_send_channel_included_when_set():
    n = ServerChanNotifier("testkey", logger, channel="c1")
    captured = {}

    def fake_urlopen(req, timeout=10):
        captured["body"] = req.data.decode("utf-8")
        return _FakeResp(b'{"code":0}')

    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        n.send("标题")
    assert "channel=c1" in captured["body"]


def test_build_notifier_none_without_config():
    assert build_notifier(None, logger) is None
    assert build_notifier({}, logger) is None


def test_build_notifier_disabled():
    assert build_notifier({"serverchan": {"enabled": False, "send_key": "k"}},
                          logger) is None


def test_build_notifier_enabled_but_no_key():
    assert build_notifier({"serverchan": {"enabled": True, "send_key": ""}},
                          logger) is None


def test_build_notifier_returns_instance():
    n = build_notifier({"serverchan": {"enabled": True, "send_key": "k",
                                       "channel": "c1"}}, logger)
    assert isinstance(n, ServerChanNotifier)
    assert n.send_key == "k"
    assert n.channel == "c1"