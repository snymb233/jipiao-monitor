# -*- coding: utf-8 -*-
"""crawlers.base.extract_prices_from_text 回退价格提取器测试。"""
from crawlers.base import BaseCrawler


def test_blank_text_empty():
    assert BaseCrawler.extract_prices_from_text("") == []
    assert BaseCrawler.extract_prices_from_text(None) == []


def test_tier1_lowest_price_fields():
    text = '{"lowestPrice": 899, "salePrice": 760}'
    out = BaseCrawler.extract_prices_from_text(text)
    assert 899 in out and 760 in out


def test_tier1_quoted_values():
    text = '{"TotalPrice": "1200"}'
    out = BaseCrawler.extract_prices_from_text(text)
    assert out == [1200]


def test_tier1_then_tier2_not_mixed_outside_range():
    # 只有 tier2 字段时走 tier2
    text = '{"minPrice": 640}'
    assert BaseCrawler.extract_prices_from_text(text) == [640]


def test_tier2_price_field():
    text = '{"adultPrice": 780}'
    out = BaseCrawler.extract_prices_from_text(text)
    assert 780 in out


def test_yuan_text_fallback():
    text = "最低价 ¥1020"
    assert BaseCrawler.extract_prices_from_text(text) == [1020]


def test_both_yuan_variants():
    text = "¥900 与 ￥800"
    out = BaseCrawler.extract_prices_from_text(text)
    assert 900 in out and 800 in out


def test_out_of_range_filtered():
    text = '{"lowestPrice": 60, "salePrice": 99999}'  # <100 且 >50000
    assert BaseCrawler.extract_prices_from_text(text) == []


def test_non_numeric_ignored():
    text = '{"lowestPrice": "abc", "salePrice": null}'
    assert BaseCrawler.extract_prices_from_text(text) == []


def test_no_relevant_fields_empty():
    text = '{"foo": "bar", "n": 5}'
    assert BaseCrawler.extract_prices_from_text(text) == []