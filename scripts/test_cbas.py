from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LATEST_JSON = ROOT / "data" / "processed" / "cbas_latest.json"
LATEST_JS = ROOT / "dist" / "data" / "cbas-latest.js"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_dataset(payload: dict, key: str) -> None:
    dataset = payload.get(key)
    assert_true(isinstance(dataset, dict), f"{key} 必須是資料集物件")
    assert_true(isinstance(dataset.get("columns"), list), f"{key}.columns 必須是清單")
    assert_true(isinstance(dataset.get("rows"), list), f"{key}.rows 必須是清單")
    assert_true(len(dataset["rows"]) >= 1, f"{key} 至少要有 1 筆資料")


def main() -> None:
    assert_true(LATEST_JSON.exists(), f"找不到 {LATEST_JSON}")
    assert_true(LATEST_JS.exists(), f"找不到 {LATEST_JS}")
    payload = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    summary = payload.get("summary") or {}
    assert_true(payload.get("generated_at"), "缺少 generated_at")
    assert_true(payload.get("source_files"), "缺少來源檔案清單")
    assert_true(summary.get("included_files", 0) >= 1, "至少要納入 1 個 .xlsx 來源檔")
    assert_true(summary.get("quote_count", 0) >= 1, "至少要有 1 筆報價資料")
    assert_true(summary.get("primary_market_count", 0) >= 1, "至少要有 1 筆發行資料")
    assert_dataset(payload, "quotes")
    assert_dataset(payload, "primary_market")
    assert_dataset(payload, "events")
    assert_true(LATEST_JS.read_text(encoding="utf-8").startswith("window.CBAS_DATA = "), "JS 資料檔格式錯誤")
    print("CBAS data check passed")


if __name__ == "__main__":
    main()
