# -*- coding: utf-8 -*-
"""crawlers.fliggy 飞猪解析器测试（签名算法 + 报价解析）。"""
import json

from crawlers.fliggy import FliggyCrawler


def test_sign_matches_md5():
    # 与手动 md5 校验一致
    import hashlib
    expected = hashlib.md5(
        "tk&123&12574478&{\"a\":1}".encode("utf-8")).hexdigest()
    assert FliggyCrawler._sign("tk", "123", '{"a":1}') == expected


def test_to_price():
    assert FliggyCrawler._to_price("780") == 780.0
    assert FliggyCrawler._to_price(0) is None
    assert FliggyCrawler._to_price("abc") is None


def _sample_raw():
    return {"data": {
        "items": [
            {"itemType": "DIRECT", "itemDatas": [
                {"flightName": "HO1152", "bestPrice": "560",
                 "airlineChineseName": "吉祥", "depTime": "08:00", "arrTime": "10:30"},
                {"flightName": "MU5101", "bestPrice": "899",
                 "airlineChineseShortName": "东航", "depTimeShow": "12:00",
                 "arrTimeShow": "14:00"},
            ]},
            {"itemType": "TRANSFER", "itemDatas": [  # TRANSFER 也应解析
                {"flightName": "CZ3101-CZ3102", "bestPrice": 1200,
                 "airlineChineseName": "南航"},
            ]},
            {"itemType": "SOMETHING_ELSE", "itemDatas": [  # 非白名单 → 跳过
                {"flightName": "XX", "bestPrice": "50"},
            ]},
        ],
    }}


def test_parse_offers_item_types():
    offers = FliggyCrawler._parse_offers(_sample_raw())
    # DIRECT 2 + TRANSFER 1 = 3，SOMETHING_ELSE 被跳过
    assert len(offers) == 3


def test_parse_offers_airline_name_fallback():
    offers = FliggyCrawler._parse_offers(_sample_raw())
    by_no = {o["flight_no"]: o for o in offers}
    assert by_no["HO1152"]["airline"] == "吉祥"
    assert by_no["MU5101"]["airline"] == "东航"  # 用了 ShortName 回退


def test_parse_offers_skips_missing_flight_name():
    raw = _sample_raw()
    raw["data"]["items"][0]["itemDatas"].append({"bestPrice": "700"})  # 无 flightName
    offers = FliggyCrawler._parse_offers(raw)
    assert any(o["flight_no"] == "HO1152" for o in offers)
    assert len(offers) == 3


def test_lowest_offer():
    offers = FliggyCrawler._parse_offers(_sample_raw())
    best = FliggyCrawler._lowest_offer(offers)
    assert best["price"] == 560.0
    assert best["flight_no"] == "HO1152"


def test_parse_offers_none_raw():
    assert FliggyCrawler._parse_offers(None) == []
    assert FliggyCrawler._parse_offers({}) == []


def test_looks_like_real_price():
    # 真实响应最低价在 data 内
    good = json.dumps({"ret": ["SUCCESS::调用成功"],
                       "data": {"items": [], "success": True, "lowestPrice": 460}})
    assert FliggyCrawler._looks_like_real_price(good) is True
    # 无 success
    bad = json.dumps({"ret": ["SUCCESS::ok"], "data": {"items": []}})
    assert FliggyCrawler._looks_like_real_price(bad) is False
    # 无 items/lowestPrice
    assert FliggyCrawler._looks_like_real_price(
        '{"ret": ["SUCCESS::ok"], "data": {"success": true}}') is False
    assert FliggyCrawler._looks_like_real_price("") is False