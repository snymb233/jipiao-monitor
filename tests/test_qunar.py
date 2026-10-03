# -*- coding: utf-8 -*-
"""crawlers.qunar 去哪儿解析器测试（仅 minPrice 可信，totalPrice 忽略）。"""
import json

from crawlers.qunar import QunarCrawler


def _sample_text():
    # data 字段是字符串化的 JSON
    data = {
        "minPrice": 910,
        "flights": [{"minPrice": 780, "totalPrice": "127b"},
                    {"minPrice": 50, "totalPrice": "4"}],  # 50 <100 排除
    }
    return json.dumps({"data": json.dumps(data, ensure_ascii=False)})


def test_extract_qunar_prefers_top_minprice():
    prices = QunarCrawler._extract_qunar_prices(_sample_text())
    assert prices == [910]


def test_extract_qunar_recursive_when_no_top_minprice():
    data = {"flights": [{"minPrice": 780}, {"minPrice": 660, "extra": [{"minPrice": 999}]}]}
    text = json.dumps({"data": json.dumps(data)})
    prices = QunarCrawler._extract_qunar_prices(text)
    assert sorted(prices) == [660, 780, 999]


def test_extract_qunar_filters_out_of_range():
    text = json.dumps({"data": json.dumps({"minPrice": 60})})  # <100
    assert QunarCrawler._extract_qunar_prices(text) == []


def test_regex_extract_escaped_quotes():
    # 真实响应 data 是字符串化 JSON，内部引号转义为 \;minPrice\":\"910\"
    text = '\\"minPrice\\":\\"910\\"'
    assert QunarCrawler._regex_extract_prices(text) == [910]


def test_regex_extract_plain_quotes():
    text = '{"minPrice": "880"}'
    assert QunarCrawler._regex_extract_prices(text) == [880]


def test_regex_extract_ignores_non_minprice_totalprice():
    # totalPrice 含 "127b" 等非数字，正则只认 minPrice
    text = '{"totalPrice": "127b", "minPrice": "880"}'
    assert QunarCrawler._regex_extract_prices(text) == [880]
    text2 = '{"totalPrice": "127b"}'
    assert QunarCrawler._regex_extract_prices(text2) == []


def test_regex_out_of_range():
    text = '{"minPrice": "45"}'
    assert QunarCrawler._regex_extract_prices(text) == []


def test_is_risk_text():
    assert QunarCrawler._is_risk_text('{"bstatus": {"code": 1999}}') is True
    assert QunarCrawler._is_risk_text('{"ret": false, "data": null}') is True
    assert QunarCrawler._is_risk_text('{"bstatus": {"code": 0}, "data": {}}') is False
    assert QunarCrawler._is_risk_text("not json") is False


def test_extract_qunar_blank():
    assert QunarCrawler._extract_qunar_prices("") == []
    assert QunarCrawler._extract_qunar_prices(None) == []