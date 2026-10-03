# -*- coding: utf-8 -*-
"""crawlers.tongcheng 同程解析器测试（lp/atp + 余票筛选）。"""
import json

from crawlers.tongcheng import TongchengCrawler


def _success_json():
    return json.dumps({
        "data": {
            "lp": 500,  # 权威当前日期最低价
            "fl": [
                {
                    "lps": [
                        {"atp": 800, "brs": [{"al": 5}]},
                        {"atp": 450, "brs": [{"al": 0}]},  # 无票 → 剔除
                        {"atp": 700, "brs": [{"al": -1}]},  # 余票充足 → 保留
                    ],
                },
                {
                    "lps": [
                        {"atp": 620, "brs": [{"al": 2}]},
                    ],
                },
            ],
            "pc": [{"price": 300}],  # 价格日历：其它日期，必须排除
        },
    })


def test_extract_prices_includes_lp_and_has_ticket():
    prices = TongchengCrawler._extract_prices(_success_json())
    assert sorted(prices) == [500, 620, 700, 800]


def test_extract_prices_excludes_no_ticket_and_calendar():
    # 无票 450 与日历 300 都不出现
    prices = TongchengCrawler._extract_prices(_success_json())
    assert 450 not in prices and 300 not in prices


def test_extract_prices_blank():
    assert TongchengCrawler._extract_prices("") == []
    assert TongchengCrawler._extract_prices(None) == []


def test_extract_prices_invalid_json():
    assert TongchengCrawler._extract_prices("not json") == []


def test_has_ticket_al_zero_no_ticket():
    assert TongchengCrawler._has_ticket([{"al": 0}]) is False


def test_has_ticket_al_nonzero_ticket():
    assert TongchengCrawler._has_ticket([{"al": 5}]) is True
    assert TongchengCrawler._has_ticket([{"al": -1}]) is True


def test_has_ticket_no_info_does_not_kill():
    assert TongchengCrawler._has_ticket(None) is True
    assert TongchengCrawler._has_ticket([]) is True
    assert TongchengCrawler._has_ticket([{"unknown": "x"}]) is True


def test_lp_out_of_ignored_range():
    text = json.dumps({"data": {"lp": 60, "fl": [
        {"lps": [{"atp": 500, "brs": [{"al": 1}]}]}]}})
    prices = TongchengCrawler._extract_prices(text)
    assert prices == [500]