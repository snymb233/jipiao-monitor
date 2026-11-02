# -*- coding: utf-8 -*-
"""crawlers.ctrip 携程解析器：tprice/quantity 配对（剔除无票诱饵价）。"""
import json

from crawlers.ctrip import CtripCrawler


def _success_json():
    return json.dumps({
        "fltitem": [
            {
                "policyinfo": [
                    {"tprice": 900, "quantity": 9},
                    {"tprice": 560, "quantity": 0},   # 无票诱饵价 → 剔除
                    {"tprice": 700, "quantity": None},  # null 余票 → 剔除
                    {"tprice": 650, "quantity": 3},
                ],
                "flightid": "MU1",
            },
        ]
    })


def test_extract_ctrip_prices_removes_no_ticket():
    prices = CtripCrawler._extract_ctrip_prices(_success_json())
    assert sorted(prices) == [650, 900]


def test_extract_ctrip_prices_all_no_ticket_empty():
    text = json.dumps({"fltitem": [{"policyinfo": [
        {"tprice": 500, "quantity": 0}, {"tprice": 600, "quantity": 0}]}]})
    assert CtripCrawler._extract_ctrip_prices(text) == []


def test_extract_ctrip_prices_non_numeric_tprice_skipped():
    text = json.dumps({"fltitem": [{"policyinfo": [{"tprice": "abc", "quantity": 5}]}]})
    assert CtripCrawler._extract_ctrip_prices(text) == []


def test_extract_ctrip_prices_blank():
    assert CtripCrawler._extract_ctrip_prices("") == []
    assert CtripCrawler._extract_ctrip_prices(None) == []


def test_extract_ctrip_prices_invalid_json_regex_fallback():
    # 非法 JSON 走 regex_fallback；tprice 后紧跟 quantity 才被采纳
    text = '{"fltitem":[{"policy":{"tprice": 880, "quantity": 5}}]}'
    prices = CtripCrawler._extract_ctrip_prices(text)
    assert prices == [880]


def test_regex_fallback_filters_null_quantity():
    text = '{"tprice": 880, "quantity": null}'
    assert CtripCrawler._regex_fallback(text) == []


def test_regex_fallback_filters_zero_quantity():
    text = '{"tprice": 880, "quantity": 0}'
    assert CtripCrawler._regex_fallback(text) == []


def test_regex_fallback_keeps_positive_quoted():
    text = '{"tprice": 880, "quantity": "5"}'
    assert CtripCrawler._regex_fallback(text) == [880]


def test_pick_lowest_filters_range():
    c = CtripCrawler({}, _null_logger())
    captured = [{"text": '{"tprice": 60, "quantity": 9}'}]  # <100 被滤掉
    assert c._pick_lowest(captured) is None
    captured = [{"text": '{"tprice": 320, "quantity": 9}'}]
    assert c._pick_lowest(captured) == 320.0


def _null_logger():
    import logging
    lg = logging.getLogger("test.ctrip")
    lg.addHandler(logging.NullHandler())
    return lg