from __future__ import annotations

import json
from pathlib import Path

from update_weekly import ROOT, TABLE_KEYS, find_latest_pdf, parse_latest_pdf, score_watchlist


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_pdf_parser() -> None:
    pdf_path, _ = find_latest_pdf()
    data = parse_latest_pdf(pdf_path)
    assert_true(data["report_period"]["start"] == "2026-06-08", "日期起日解析錯誤")
    assert_true(data["report_period"]["end"] == "2026-06-12", "日期迄日解析錯誤")
    for key in TABLE_KEYS:
        assert_true(key in data["tables"], f"缺少表格 {key}")
        assert_true(len(data["tables"][key]) > 0, f"表格 {key} 沒有資料")
    assert_true(len(data["tables"]["high_volume"]) == 18, "高成交量表筆數應為 18")
    assert_true(len(data["tables"]["top_gainers"]) == 10, "漲幅表筆數應為 10")
    assert_true(len(data["tables"]["top_losers"]) == 10, "跌幅表筆數應為 10")
    assert_true(len(data["tables"]["sellback_large"]) == 2, "賣回大於 100 張表筆數應為 2")


def test_watchlist_scoring() -> None:
    pdf_path, _ = find_latest_pdf()
    data = parse_latest_pdf(pdf_path)
    watchlist = score_watchlist(data)
    assert_true(len(watchlist) > 0, "追蹤名單不可為空")
    assert_true(watchlist[0]["score"] >= watchlist[-1]["score"], "追蹤名單需依分數排序")
    top_codes = {row["code"] for row in watchlist[:10]}
    assert_true("35832" in top_codes, "高轉換量辛耘二應進入前 10 名")
    risky = [row for row in watchlist if row["code"] == "64423"]
    assert_true(risky and risky[0]["risk_level"] == "高", "贖回且剩餘比率低者需標示高風險")


def test_latest_outputs_exist() -> None:
    json_path = ROOT / "data" / "processed" / "cb_weekly_latest.json"
    csv_path = ROOT / "data" / "processed" / "cb_weekly_latest.csv"
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert_true("warnings" in data, "輸出 JSON 需保留 warnings")
    assert_true(csv_path.exists() or not json_path.exists(), "若已有 JSON，也應輸出 CSV")


def main() -> None:
    test_pdf_parser()
    test_watchlist_scoring()
    test_latest_outputs_exist()
    print("測試通過：PDF 解析、日期區間、追蹤名單計分、風險標示。")


if __name__ == "__main__":
    main()
