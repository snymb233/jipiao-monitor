# -*- coding: utf-8 -*-
"""crawlers.tuniu 途牛逆向解析器测试（纯逻辑，无网络）。"""
import json
import re

from crawlers.tuniu import TuniuCrawler


# ---------- _new_guid ----------
def test_new_guid_format():
    g = TuniuCrawler._new_guid()
    assert re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", g)


def test_new_guid_unique():
    assert TuniuCrawler._new_guid() != TuniuCrawler._new_guid()


def test_b64():
    # base64("1,0,") 结果固定，验证与 tac.js 复刻一致
    assert TuniuCrawler._b64("abc") == "YWJj"


# ---------- _to_price ----------
def test_to_price_valid():
    assert TuniuCrawler._to_price("560.5") == 560.5
    assert TuniuCrawler._to_price(560) == 560.0


def test_to_price_non_positive_none():
    assert TuniuCrawler._to_price(0) is None
    assert TuniuCrawler._to_price(-5) is None


def test_to_price_garbage_none():
    assert TuniuCrawler._to_price("abc") is None
    assert TuniuCrawler._to_price(None) is None


# ---------- _adt_fare ----------
def test_adt_fare_picks_min_adult():
    price_list = [
        {"fareBreakdownList": [
            {"psgType": "ADT", "baseFare": "900"},
            {"psgType": "CHD", "baseFare": "600"},
        ]},
        {"fareBreakdownList": [{"psgType": "ADT", "baseFare": 640}]},
    ]
    assert TuniuCrawler._adt_fare(price_list) == 640


def test_adt_fare_no_adult_none():
    price_list = [{"fareBreakdownList": [{"psgType": "CHD", "baseFare": "600"}]}]
    assert TuniuCrawler._adt_fare(price_list) is None


def test_adt_fare_empty_none():
    assert TuniuCrawler._adt_fare([]) is None
    assert TuniuCrawler._adt_fare(None) is None


# ---------- _find_flight_detail ----------
def test_find_flight_detail_exact_key():
    fl = {"MU123": {"airlineCompany": "东航"}, "CZ": {"a": 1}}
    d = TuniuCrawler._find_flight_detail(fl, "MU123")
    assert d.get("airlineCompany") == "东航"


def test_find_flight_detail_key_after_hash():
    fl = {"MU123#123": {"airlineCompany": "东航"}}
    d = TuniuCrawler._find_flight_detail(fl, "MU123")
    assert d.get("airlineCompany") == "东航"


def test_find_flight_detail_missing():
    assert TuniuCrawler._find_flight_detail({"A": {}}, "MU999") == {}
    assert TuniuCrawler._find_flight_detail(None, "MU999") == {}


# ---------- _parse_offers ----------
def _sample_raw():
    return {
        "data": {
            "fareList": [
                {
                    "flightOptions": [{"flightNos": "MU5101-CZ3102"}],
                    "flightPriceList": [
                        {"fareBreakdownList": [{"psgType": "ADT", "baseFare": "899"}]},
                    ],
                },
                {
                    "flightOptions": [{"flightNos": "HO1152"}],
                    "flightPriceList": [
                        {"fareBreakdownList": [{"psgType": "ADT", "baseFare": 560}]},
                    ],
                },
            ],
            "flightList": {
                "MU5101": {"airlineCompany": "东航", "departureTime": "08:00",
                           "arrivalTime": "09:40"},
                "HO1152": {"airlineCompany": "吉祥", "departureTime": "20:15",
                           "arrivalTime": "22:05"},
            },
        }
    }


def test_parse_offers_two():
    offers = TuniuCrawler._parse_offers(_sample_raw())
    assert len(offers) == 2
    prices = sorted(o["price"] for o in offers)
    assert prices == [560.0, 899.0]


def test_parse_offers_deduplicates_same_key():
    raw = _sample_raw()
    raw["data"]["fareList"].append(raw["data"]["fareList"][0])  # 重复 flightOptions
    offers = TuniuCrawler._parse_offers(raw)
    assert len(offers) == 2


def test_parse_offers_skips_missing_flight_nos():
    raw = _sample_raw()
    raw["data"]["fareList"].append({"flightOptions": [], "flightPriceList": []})
    offers = TuniuCrawler._parse_offers(raw)
    assert len(offers) == 2


def test_parse_offers_none_raw():
    assert TuniuCrawler._parse_offers(None) == []
    assert TuniuCrawler._parse_offers({}) == []


def test_lowest_offer():
    offers = TuniuCrawler._parse_offers(_sample_raw())
    best = TuniuCrawler._lowest_offer(offers)
    assert best["price"] == 560.0
    assert best["flight_no"] == "HO1152"
    assert best["airline"] == "吉祥"


def test_lowest_offer_none_when_no_price():
    assert TuniuCrawler._lowest_offer([{"price": None}, {"price": 0}]) is None
    assert TuniuCrawler._lowest_offer([]) is None


# ---------- _looks_like_real_price / _has_price ----------
def _success_body():
    # 真实途牛响应为压缩 JSON（冒号后无空格），success 前无空格
    return json.dumps({"success": True, "data": {
        "fareList": [{"flightOptions": [{"flightNos": "MU1"}],
                      "flightPriceList": [{"fareBreakdownList":
                                           [{"psgType": "ADT", "baseFare": 500}]}]}]}},
        separators=(",", ":"))


def test_looks_like_real_price_true():
    assert TuniuCrawler._looks_like_real_price(_success_body()) is True


def test_looks_like_real_price_missing_success():
    assert TuniuCrawler._looks_like_real_price('{"data": {"fareList": []}}') is False


def test_looks_like_real_price_farelist_empty_false():
    assert TuniuCrawler._looks_like_real_price(
        '{"success": true, "data": {"fareList": []}}') is False


def test_looks_like_real_price_garbage_false():
    assert TuniuCrawler._looks_like_real_price("not json") is False
    assert TuniuCrawler._looks_like_real_price("") is False


def test_has_price_recursive_dict_and_list():
    node = {"a": {"b": [{"salePrice": 300}]}}
    assert TuniuCrawler._has_price(node) is True


def test_has_price_zero_not_counted():
    assert TuniuCrawler._has_price({"salePrice": 0}) is False
    assert TuniuCrawler._has_price({"baseFare": -1}) is False


def test_has_price_none():
    assert TuniuCrawler._has_price({}) is False
    assert TuniuCrawler._has_price([{"x": "y"}]) is False