from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import openpyxl


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = Path(
    os.environ.get(
        "CBAS_SOURCE_DIR",
        r"C:\Users\vmja2\Downloads\01_投資交易_CB_選擇權\CBAS報價及發行資訊",
    )
)
PROCESSED_DIR = ROOT / "data" / "processed"
HISTORY_DIR = ROOT / "data" / "history" / "cbas"
DIST_DATA_DIR = ROOT / "dist" / "data"
TAIPEI = timezone(timedelta(hours=8))


def compact(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value)).strip()


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def number(value: Any) -> float | int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if float(value).is_integer() else float(value)
    cleaned = str(value).replace(",", "").replace("%", "").strip()
    try:
        parsed = float(cleaned)
    except ValueError:
        return None
    return int(parsed) if parsed.is_integer() else parsed


def code_text(value: Any) -> str:
    parsed = number(value)
    if parsed is not None:
        return str(parsed)
    return compact(value)


def file_date(path: Path) -> str:
    match = re.search(r"(20\d{6}|1\d{6})", path.name)
    if not match:
        return datetime.fromtimestamp(path.stat().st_mtime, TAIPEI).date().isoformat()
    raw = match.group(1)
    if raw.startswith("20"):
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    roc_year = int(raw[:3]) + 1911
    return f"{roc_year}-{raw[3:5]}-{raw[5:7]}"


def find_header(rows: list[list[Any]], required: list[str], max_scan: int = 30) -> tuple[int, list[str]] | None:
    for index, row in enumerate(rows[:max_scan]):
        headers = [compact(cell) for cell in row]
        joined = "|".join(headers)
        if all(token in joined for token in required):
            return index, headers
    return None


def col(headers: list[str], *tokens: str, avoid: tuple[str, ...] = ()) -> int | None:
    for index, header in enumerate(headers):
        if header and all(token in header for token in tokens) and not any(token in header for token in avoid):
            return index
    return None


def val(row: list[Any], index: int | None) -> Any:
    if index is None or index >= len(row):
        return None
    return row[index]


def trim_empty(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if value not in ("", None, [])}


def row_values(ws: Any, limit: int | None = None) -> list[list[Any]]:
    rows = []
    for index, row in enumerate(ws.iter_rows(values_only=True), 1):
        rows.append(list(row))
        if limit and index >= limit:
            break
    return rows


def extract_quote_sheet(path: Path, sheet_name: str, rows: list[list[Any]]) -> list[dict[str, Any]]:
    found = find_header(rows, ["代", "權利金"])
    if not found:
        return []
    header_index, headers = found
    code_i = col(headers, "CB", "代") or col(headers, "可轉債代碼")
    name_i = col(headers, "債券名稱") or col(headers, "可轉債名稱")
    premium_100_i = col(headers, "權利金", "百元")
    premium_ref_i = col(headers, "權利金", avoid=("百元",))
    duration_i = col(headers, "期間") or col(headers, "剩餘年期")
    rate_i = col(headers, "折現率")
    cb_price_i = col(headers, "CB", "價", avoid=("轉換價值",))
    parity_i = col(headers, "轉換價值")
    premium_ratio_i = col(headers, "折溢價")
    floor_i = col(headers, "履約價") or col(headers, "BondFloor")
    expire_i = col(headers, "到期日", avoid=("賣回",)) or col(headers, "Expiration")
    put_date_i = col(headers, "賣回日") or col(headers, "賣回日期")
    put_price_i = col(headers, "賣回價格")
    stock_price_i = col(headers, "現股參考價") or col(headers, "股票市價")
    conversion_price_i = col(headers, "轉換價格", avoid=("價值",)) or col(headers, "轉換價", avoid=("價值",))
    tcri_i = col(headers, "TCRI") or col(headers, "擔保")

    results = []
    for row in rows[header_index + 1 :]:
        code = code_text(val(row, code_i))
        if not re.fullmatch(r"\d{4,6}", code):
            continue
        results.append(
            trim_empty(
                {
                    "cb_code": code,
                    "stock_code": code[:4],
                    "cb_name": text(val(row, name_i)),
                    "tcri_or_guarantor": text(val(row, tcri_i)),
                    "premium_per_100": number(val(row, premium_100_i)),
                    "premium_reference": number(val(row, premium_ref_i)),
                    "duration_years": number(val(row, duration_i)),
                    "discount_rate": number(val(row, rate_i)),
                    "cb_price": number(val(row, cb_price_i)),
                    "parity": number(val(row, parity_i)),
                    "premium_ratio": number(val(row, premium_ratio_i)),
                    "bond_floor": number(val(row, floor_i)),
                    "option_expiration": text(val(row, expire_i)),
                    "put_date": text(val(row, put_date_i)),
                    "put_price": number(val(row, put_price_i)),
                    "stock_price": number(val(row, stock_price_i)),
                    "conversion_price": number(val(row, conversion_price_i)),
                    "source_file": path.name,
                    "source_sheet": sheet_name,
                    "source_date": file_date(path),
                }
            )
        )
    return results


def extract_bond_info(path: Path, sheet_name: str, rows: list[list[Any]]) -> list[dict[str, Any]]:
    found = find_header(rows, ["代", "轉換"])
    if not found:
        return []
    header_index, headers = found
    code_i = col(headers, "CB", "代") or col(headers, "代號") or col(headers, "代碼")
    name_i = col(headers, "債券名稱") or col(headers, "名稱")
    stock_name_i = col(headers, "轉換標的名稱") or col(headers, "英文名稱")
    stock_code_i = col(headers, "轉換標的代碼")
    stock_price_i = col(headers, "股票市價") or col(headers, "現股")
    cb_price_i = col(headers, "債券市價") or col(headers, "CBPx")
    conv_i = col(headers, "轉換價格") or col(headers, "Conv.Px")
    parity_i = col(headers, "轉換價值")
    premium_i = col(headers, "折溢價")
    volume_i = col(headers, "成交量")
    issue_i = col(headers, "發行日")
    put_i = col(headers, "賣回日")
    maturity_i = col(headers, "到期日")
    balance_i = col(headers, "流通在外")

    results = []
    for row in rows[header_index + 1 :]:
        code = code_text(val(row, code_i))
        if not re.fullmatch(r"\d{4,6}", code):
            continue
        stock_code = code_text(val(row, stock_code_i)) or code[:4]
        results.append(
            trim_empty(
                {
                    "cb_code": code,
                    "stock_code": stock_code[:4],
                    "cb_name": text(val(row, name_i)),
                    "stock_name": text(val(row, stock_name_i)),
                    "stock_price": number(val(row, stock_price_i)),
                    "cb_price": number(val(row, cb_price_i)),
                    "conversion_price": number(val(row, conv_i)),
                    "parity": number(val(row, parity_i)),
                    "premium_ratio": number(val(row, premium_i)),
                    "volume": number(val(row, volume_i)),
                    "issue_date": text(val(row, issue_i)),
                    "next_put_date": text(val(row, put_i)),
                    "maturity_date": text(val(row, maturity_i)),
                    "outstanding_amount": number(val(row, balance_i)),
                    "source_file": path.name,
                    "source_sheet": sheet_name,
                    "source_date": file_date(path),
                }
            )
        )
    return results


def extract_primary_market(path: Path, sheet_name: str, rows: list[list[Any]]) -> list[dict[str, Any]]:
    found = find_header(rows, ["標的", "發行"], max_scan=20)
    if not found:
        found = find_header(rows, ["CB代碼", "標的名稱"], max_scan=20)
    if not found:
        return []
    header_index, headers = found
    code_i = col(headers, "CB代碼") or col(headers, "標的代號") or col(headers, "發行標的")
    stock_code_i = col(headers, "標的代號")
    name_i = col(headers, "標的名稱") or col(headers, "發行標的")
    issue_type_i = col(headers, "詢圈") or col(headers, "競拍")
    years_i = col(headers, "發行期間") or col(headers, "年期")
    amount_i = col(headers, "發行金額") or col(headers, "發行量") or col(headers, "額度")
    tcri_i = col(headers, "TCRI") or col(headers, "擔保")
    underwriter_i = col(headers, "主辦")
    period_i = col(headers, "期間", avoid=("發行期間",))
    listing_i = col(headers, "掛牌")
    effective_i = col(headers, "生效")
    op_i = col(headers, "OP") or col(headers, "拆解")
    conv_i = col(headers, "轉換", "價格") or col(headers, "轉換價")
    premium_i = col(headers, "溢價")

    results = []
    for row in rows[header_index + 1 :]:
        code = code_text(val(row, code_i))
        if not re.fullmatch(r"\d{4,6}", code):
            continue
        stock_code = code_text(val(row, stock_code_i)) or code[:4]
        results.append(
            trim_empty(
                {
                    "cb_code": code,
                    "stock_code": stock_code[:4],
                    "cb_name": text(val(row, name_i)),
                    "issue_type": text(val(row, issue_type_i)),
                    "years": number(val(row, years_i)) or text(val(row, years_i)),
                    "issue_amount_100m": number(val(row, amount_i)),
                    "tcri_or_guarantor": text(val(row, tcri_i)),
                    "lead_underwriter": text(val(row, underwriter_i)),
                    "bookbuilding_period": text(val(row, period_i)),
                    "effective_date": text(val(row, effective_i)),
                    "listing_date": text(val(row, listing_i)),
                    "op_effective_date": text(val(row, op_i)),
                    "conversion_price": number(val(row, conv_i)),
                    "premium_rate": number(val(row, premium_i)),
                    "source_file": path.name,
                    "source_sheet": sheet_name,
                    "source_date": file_date(path),
                }
            )
        )
    return results


def extract_events(path: Path, sheet_name: str, rows: list[list[Any]]) -> list[dict[str, Any]]:
    found = find_header(rows, ["代", "日"], max_scan=20)
    if not found:
        return []
    header_index, headers = found
    code_i = col(headers, "CB代號") or col(headers, "代碼") or col(headers, "公司代號")
    name_i = col(headers, "債券名稱") or col(headers, "公司名稱") or col(headers, "發行標的")
    status_i = col(headers, "狀態")
    subject_i = col(headers, "主旨")
    put_i = col(headers, "賣回日")
    maturity_i = col(headers, "到期日")
    redeem_i = col(headers, "強制贖回日") or col(headers, "ASO到期日")
    listing_end_i = col(headers, "終止")

    results = []
    for row in rows[header_index + 1 :]:
        code = code_text(val(row, code_i))
        if not re.fullmatch(r"\d{4,6}", code):
            continue
        event_type = text(val(row, status_i)) or ("公司贖回權" if "贖回" in sheet_name else "事件提醒")
        results.append(
            trim_empty(
                {
                    "cb_code": code if len(code) > 4 else "",
                    "stock_code": code[:4],
                    "name": text(val(row, name_i)),
                    "event_type": event_type,
                    "subject": text(val(row, subject_i)),
                    "next_put_date": text(val(row, put_i)),
                    "maturity_date": text(val(row, maturity_i)),
                    "redeem_date": text(val(row, redeem_i)) or text(val(row, listing_end_i)),
                    "source_file": path.name,
                    "source_sheet": sheet_name,
                    "source_date": file_date(path),
                }
            )
        )
    return results


def latest_by_code(rows: list[dict[str, Any]], code_key: str) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.get(code_key) or "")
        if not code:
            continue
        existing = best.get(code)
        if not existing or str(row.get("source_date", "")) >= str(existing.get("source_date", "")):
            best[code] = row
    return sorted(best.values(), key=lambda item: item.get(code_key, ""))


def build_watchlist(quotes: list[dict[str, Any]], issues: list[dict[str, Any]], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    soon_events = {event.get("stock_code") for event in events}
    issue_codes = {issue.get("cb_code") for issue in issues}
    rows = []
    for quote in quotes:
        score = 0
        if quote.get("premium_per_100") is not None:
            score += 25
        if quote.get("option_expiration"):
            score += 15
        if quote.get("cb_code") in issue_codes:
            score += 20
        if quote.get("stock_code") in soon_events:
            score += 20
        if quote.get("premium_ratio") is not None and float(quote["premium_ratio"]) < 0.2:
            score += 15
        rows.append(
            {
                "cb_code": quote.get("cb_code"),
                "stock_code": quote.get("stock_code"),
                "cb_name": quote.get("cb_name", ""),
                "score": min(score, 100),
                "premium_per_100": quote.get("premium_per_100"),
                "premium_reference": quote.get("premium_reference"),
                "cb_price": quote.get("cb_price"),
                "parity": quote.get("parity"),
                "premium_ratio": quote.get("premium_ratio"),
                "option_expiration": quote.get("option_expiration"),
                "source_file": quote.get("source_file"),
            }
        )
    return sorted(rows, key=lambda row: (row["score"], row.get("premium_per_100") or 0), reverse=True)


def pack_rows(rows: list[dict[str, Any]], columns: list[str], source_ids: dict[str, int]) -> dict[str, Any]:
    def packed_value(row: dict[str, Any], column: str) -> Any:
        if column == "source_id":
            return source_ids.get(str(row.get("source_file") or ""), None)
        return row.get(column)

    return {
        "columns": columns,
        "rows": [[packed_value(row, column) for column in columns] for row in rows],
    }


def collect() -> dict[str, Any]:
    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"找不到資料夾：{SOURCE_DIR}")

    source_files = sorted(
        [path for path in SOURCE_DIR.iterdir() if path.suffix.lower() in {".xlsx", ".xls"} and not path.name.startswith("~$")],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    warnings: list[dict[str, str]] = []
    quotes: list[dict[str, Any]] = []
    bond_info: list[dict[str, Any]] = []
    primary_market: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    for path in source_files:
        if path.suffix.lower() == ".xls":
            warnings.append(
                {
                    "source_file": path.name,
                    "message": "此檔案為舊版 .xls，當前環境缺少 xlrd 或轉檔工具，尚未納入自動彙整。",
                }
            )
            continue
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for worksheet in workbook.worksheets:
            rows = row_values(worksheet, limit=1200)
            sheet_name = worksheet.title
            if "報價" in sheet_name:
                quotes.extend(extract_quote_sheet(path, sheet_name, rows))
            if any(token in sheet_name for token in ["資料", "基本"]):
                bond_info.extend(extract_bond_info(path, sheet_name, rows))
            if any(token in sheet_name for token in ["發行", "初級"]):
                primary_market.extend(extract_primary_market(path, sheet_name, rows))
            if any(token in sheet_name for token in ["到期", "贖回"]):
                events.extend(extract_events(path, sheet_name, rows))

    latest_quotes = latest_by_code(quotes, "cb_code")
    latest_bond_info = latest_by_code(bond_info, "cb_code")
    latest_issues = latest_by_code(primary_market, "cb_code")
    generated_at = datetime.now(TAIPEI).isoformat(timespec="seconds")
    latest_source_date = max([file_date(path) for path in source_files], default="")

    source_file_rows = [
        {
            "name": path.name,
            "modified_at": datetime.fromtimestamp(path.stat().st_mtime, TAIPEI).isoformat(timespec="seconds"),
            "source_date": file_date(path),
            "included": path.suffix.lower() == ".xlsx",
        }
        for path in source_files
    ]
    source_ids = {row["name"]: index for index, row in enumerate(source_file_rows)}

    quote_columns = [
        "cb_code",
        "stock_code",
        "cb_name",
        "tcri_or_guarantor",
        "premium_per_100",
        "premium_reference",
        "cb_price",
        "parity",
        "premium_ratio",
        "option_expiration",
        "put_date",
        "source_id",
        "source_date",
    ]
    primary_columns = [
        "cb_code",
        "stock_code",
        "cb_name",
        "issue_type",
        "years",
        "issue_amount_100m",
        "tcri_or_guarantor",
        "lead_underwriter",
        "bookbuilding_period",
        "listing_date",
        "op_effective_date",
        "conversion_price",
        "source_id",
        "source_date",
    ]
    event_columns = [
        "cb_code",
        "stock_code",
        "name",
        "event_type",
        "next_put_date",
        "maturity_date",
        "redeem_date",
        "source_id",
        "source_date",
    ]

    return {
        "title": "CBAS 報價及發行資訊",
        "generated_at": generated_at,
        "latest_source_date": latest_source_date,
        "source_files": source_file_rows,
        "summary": {
            "quote_count": len(latest_quotes),
            "primary_market_count": len(latest_issues),
            "event_count": len(events),
            "included_files": sum(1 for path in source_files if path.suffix.lower() == ".xlsx"),
            "skipped_files": sum(1 for path in source_files if path.suffix.lower() == ".xls"),
        },
        "quotes": pack_rows(latest_quotes, quote_columns, source_ids),
        "primary_market": pack_rows(latest_issues, primary_columns, source_ids),
        "events": pack_rows(
            sorted(events, key=lambda item: (item.get("redeem_date") or item.get("next_put_date") or item.get("maturity_date") or "9999")),
            event_columns,
            source_ids,
        ),
        "warnings": warnings,
    }


def write_outputs(payload: dict[str, Any]) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    DIST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    date_key = payload["latest_source_date"].replace("-", "") or datetime.now(TAIPEI).strftime("%Y%m%d")
    latest_json = PROCESSED_DIR / "cbas_latest.json"
    history_json = HISTORY_DIR / f"{date_key}.json"
    js_path = DIST_DATA_DIR / "cbas-latest.js"
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    latest_json.write_text(content, encoding="utf-8")
    history_json.write_text(content, encoding="utf-8")
    js_path.write_text("window.CBAS_DATA = " + content + ";\n", encoding="utf-8")


def main() -> None:
    payload = collect()
    write_outputs(payload)
    print(f"完成 CBAS 彙整：報價 {payload['summary']['quote_count']} 筆，發行 {payload['summary']['primary_market_count']} 筆。")
    if payload["warnings"]:
        print(f"警示 {len(payload['warnings'])} 筆，請於網頁檢視來源狀態。")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"CBAS 彙整失敗：{exc}", file=sys.stderr)
        raise
