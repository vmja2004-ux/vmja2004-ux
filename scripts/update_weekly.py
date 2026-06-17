from __future__ import annotations

import csv
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
HISTORY_DIR = ROOT / "data" / "history"
DIST_DIR = ROOT / "dist"

TABLE_KEYS = [
    "high_volume",
    "top_gainers",
    "top_losers",
    "sellback_large",
    "new_listings",
    "conversion_large",
    "auction_cases",
    "company_calls",
    "putback_within_3m",
    "maturity_within_3m",
]


@dataclass(frozen=True)
class Column:
    key: str
    title: str
    x0: float
    x1: float


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value)).strip()


def parse_number(value: Any) -> float | None:
    text = clean_text(value).replace("%", "").replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    number = parse_number(value)
    return int(number) if number is not None else None


def parse_date(value: Any) -> str:
    text = clean_text(value)
    match = re.search(r"(20\d{2})/(\d{1,2})/(\d{1,2})", text)
    if not match:
        return text
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def percent_value(value: Any) -> float | None:
    return parse_number(value)


def normalize_price_percent(value: Any) -> float | str | None:
    text = clean_text(value)
    if not text:
        return None
    if "未開標" in text:
        return "未開標"
    return parse_number(text)


def find_latest_pdf() -> tuple[Path, list[dict[str, str]]]:
    warnings: list[dict[str, str]] = []
    pdfs = sorted(RAW_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime)
    if not pdfs:
        root_pdfs = sorted(ROOT.glob("*.pdf"), key=lambda p: p.stat().st_mtime)
        if not root_pdfs:
            raise FileNotFoundError("找不到 PDF：請將元大週評 PDF 放在 data/raw。")
        source = root_pdfs[-1]
        target = RAW_DIR / source.name
        if not target.exists():
            shutil.copy2(source, target)
        warnings.append(
            {
                "level": "info",
                "table": "source_file",
                "message": "data/raw 原本沒有 PDF，已使用專案根目錄最新 PDF 並複製到 data/raw。",
            }
        )
        return target, warnings
    return pdfs[-1], warnings


def report_period_from_pdf(pdf_path: Path) -> dict[str, str]:
    name_match = re.search(r"(20\d{6})-(\d{4})", pdf_path.name)
    if name_match:
        start_raw, end_md = name_match.groups()
        start = f"{start_raw[:4]}-{start_raw[4:6]}-{start_raw[6:8]}"
        end = f"{start_raw[:4]}-{end_md[:2]}-{end_md[2:4]}"
        return {"start": start, "end": end}
    with pdfplumber.open(str(pdf_path)) as pdf:
        text = pdf.pages[0].extract_text() or ""
    match = re.search(r"\((20\d{2})/(\d{1,2})/(\d{1,2})~(20\d{2})/(\d{1,2})/(\d{1,2})\)", text)
    if not match:
        raise ValueError("無法解析報告日期區間。")
    y1, m1, d1, y2, m2, d2 = match.groups()
    return {
        "start": f"{int(y1):04d}-{int(m1):02d}-{int(d1):02d}",
        "end": f"{int(y2):04d}-{int(m2):02d}-{int(d2):02d}",
    }


def group_rows(words: list[dict[str, Any]], y0: float, y1: float, tolerance: float = 4.0) -> list[list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    for word in words:
        if not (y0 <= word["top"] <= y1):
            continue
        for row in rows:
            if abs(row["top"] - word["top"]) <= tolerance:
                row["items"].append(word)
                break
        else:
            rows.append({"top": word["top"], "items": [word]})
    return [row["items"] for row in sorted(rows, key=lambda row: row["top"])]


def row_value(items: list[dict[str, Any]], column: Column) -> str:
    parts = [w for w in items if column.x0 <= w["x0"] <= column.x1]
    return clean_text("".join(w["text"] for w in sorted(parts, key=lambda w: w["x0"])))


def parse_position_table(page: Any, y0: float, y1: float, columns: list[Column], min_first_col: bool = True) -> list[dict[str, str]]:
    words = page.extract_words(x_tolerance=1, y_tolerance=2, keep_blank_chars=False)
    rows: list[dict[str, str]] = []
    for items in group_rows(words, y0, y1):
        row = {column.key: row_value(items, column) for column in columns}
        if min_first_col and not row.get(columns[0].key):
            continue
        if any(row.values()):
            rows.append(row)
    return rows


def parse_pdf_table(page: Any, expected_cols: int) -> list[list[str]]:
    for table in page.extract_tables():
        if table and max(len(row) for row in table) == expected_cols:
            return [[clean_text(cell) for cell in row] for row in table]
    return []


def parse_ranked_price(rows: list[list[str]], direction_key: str) -> list[dict[str, Any]]:
    output = []
    for row in rows[1:]:
        if len(row) < 5 or not row[0].isdigit():
            continue
        output.append(
            {
                "rank": parse_int(row[0]),
                "code": row[1],
                "name": row[2],
                "close_price": parse_number(row[3]),
                direction_key: parse_number(row[4]),
            }
        )
    return output


def parse_latest_pdf(pdf_path: Path) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    period = report_period_from_pdf(pdf_path)
    with pdfplumber.open(str(pdf_path)) as pdf:
        pages = pdf.pages
        high_volume = parse_position_table(
            pages[0],
            180,
            500,
            [
                Column("rank", "排名", 115, 145),
                Column("code", "標的代碼", 185, 252),
                Column("name", "標的名稱", 285, 390),
                Column("weekly_volume", "成交張數", 440, 520),
            ],
        )
        for row in high_volume:
            row["rank"] = parse_int(row["rank"])
            row["weekly_volume"] = parse_int(row["weekly_volume"])
            row["avg_daily_volume"] = round((row["weekly_volume"] or 0) / 5, 1)

        top_gainers = parse_ranked_price(parse_pdf_table(pages[0], 5), "change_pct")

        loser_rows = parse_position_table(
            pages[1],
            145,
            385,
            [
                Column("rank", "排名", 90, 110),
                Column("code", "標的代碼", 135, 185),
                Column("name", "標的名稱", 210, 290),
                Column("close_price", "收盤價", 340, 405),
                Column("change_pct", "跌幅度%", 445, 505),
            ],
        )
        top_losers = [
            {
                "rank": parse_int(row["rank"]),
                "code": row["code"],
                "name": row["name"],
                "close_price": parse_number(row["close_price"]),
                "change_pct": parse_number(row["change_pct"]),
            }
            for row in loser_rows
        ]

        sellback_rows = parse_position_table(
            pages[1],
            460,
            510,
            [
                Column("code", "標的代碼", 84, 118),
                Column("name", "標的名稱", 135, 190),
                Column("current_outstanding", "本週張數", 220, 260),
                Column("previous_outstanding", "上週張數", 305, 340),
                Column("weekly_sellback_volume", "本週賣回張數", 390, 425),
                Column("remaining_ratio_pct", "剩餘比率%", 470, 500),
            ],
        )
        sellback_large = []
        for row in sellback_rows:
            sellback_large.append(
                {
                    "code": row["code"],
                    "name": row["name"],
                    "current_outstanding": parse_int(row["current_outstanding"]),
                    "previous_outstanding": parse_int(row["previous_outstanding"]),
                    "weekly_sellback_volume": parse_int(row["weekly_sellback_volume"]),
                    "remaining_ratio_pct": percent_value(row["remaining_ratio_pct"]),
                }
            )

        listing_table = parse_pdf_table(pages[1], 9)
        new_listings = []
        for row in listing_table[1:]:
            if len(row) < 9:
                continue
            new_listings.append(
                {
                    "underwriting_method": row[0],
                    "code": row[1],
                    "name": row[2],
                    "tcri_or_guarantor": row[3],
                    "issue_amount_100m": parse_number(row[4]),
                    "conversion_price": parse_number(row[5]),
                    "listing_date": parse_date(row[6]),
                    "issue_price_pct": normalize_price_percent(row[7]),
                    "decomposition_date": parse_date(row[8]),
                }
            )

        auction_rows = parse_position_table(
            pages[2],
            165,
            350,
            [
                Column("bid_open_date", "開標日期", 90, 123),
                Column("name", "證券名稱", 128, 162),
                Column("code", "證券代號", 172, 196),
                Column("tcri_or_guarantor", "TCRI/擔保行", 202, 240),
                Column("bid_start_date", "投標開始日", 246, 276),
                Column("bid_end_date", "投標結束日", 283, 311),
                Column("auction_quantity", "競拍數量", 320, 346),
                Column("minimum_bid_price", "最低投標價格", 350, 392),
                Column("listing_date", "掛牌日", 392, 423),
                Column("lead_underwriter", "主辦券商", 428, 462),
                Column("conversion_price", "轉換價格", 464, 496),
                Column("issue_price_pct", "發行價", 498, 528),
            ],
        )
        auction_cases = []
        for row in auction_rows:
            listing_date = row["listing_date"]
            if re.match(r"026/", listing_date):
                listing_date = "2" + listing_date
            auction_cases.append(
                {
                    "bid_open_date": parse_date(row["bid_open_date"]),
                    "name": row["name"],
                    "code": row["code"],
                    "tcri_or_guarantor": row["tcri_or_guarantor"],
                    "bid_start_date": parse_date(row["bid_start_date"]),
                    "bid_end_date": parse_date(row["bid_end_date"]),
                    "auction_quantity": parse_int(row["auction_quantity"]),
                    "minimum_bid_price": parse_number(row["minimum_bid_price"]),
                    "listing_date": parse_date(listing_date),
                    "lead_underwriter": row["lead_underwriter"],
                    "conversion_price": parse_number(row["conversion_price"]),
                    "issue_price_pct": normalize_price_percent(row["issue_price_pct"]),
                }
            )

        company_table = parse_pdf_table(pages[2], 6)
        company_calls = []
        for row in company_table[1:]:
            company_calls.append(
                {
                    "code": row[0],
                    "name": row[1],
                    "original_issue_volume": parse_int(row[2]),
                    "current_outstanding": parse_int(row[3]),
                    "remaining_ratio_pct": percent_value(row[4]),
                    "termination_date": parse_date(row[5]),
                }
            )

        conversion_table = parse_pdf_table(pages[3], 6)
        conversion_large = []
        for row in conversion_table[1:]:
            current = parse_int(row[2])
            previous = parse_int(row[3])
            converted = abs(parse_int(row[4]) or 0)
            intensity = round(converted / previous * 100, 2) if previous else None
            if intensity is None:
                level = "資料不足"
            elif intensity > 30:
                level = "後段壓力"
            elif intensity > 20:
                level = "警示"
            elif intensity > 10:
                level = "觀察"
            else:
                level = "一般"
            conversion_large.append(
                {
                    "code": row[0],
                    "name": row[1],
                    "current_outstanding": current,
                    "previous_outstanding": previous,
                    "weekly_conversion_volume": converted,
                    "remaining_ratio_pct": percent_value(row[5]),
                    "conversion_intensity_pct": intensity,
                    "conversion_flag": level,
                }
            )

        putback_rows = parse_position_table(
            pages[4],
            140,
            485,
            [
                Column("code", "標的代碼", 100, 135),
                Column("name", "標的名稱", 160, 212),
                Column("putback_date", "賣回日", 235, 280),
                Column("original_issue_volume", "原發行張數", 300, 355),
                Column("current_outstanding", "流通在外張數", 370, 430),
                Column("remaining_ratio_pct", "剩餘比率%", 460, 522),
            ],
        )
        putback_within_3m = [
            {
                "code": row["code"],
                "name": row["name"],
                "putback_date": parse_date(row["putback_date"]),
                "original_issue_volume": parse_int(row["original_issue_volume"]),
                "current_outstanding": parse_int(row["current_outstanding"]),
                "remaining_ratio_pct": percent_value(row["remaining_ratio_pct"]),
            }
            for row in putback_rows
        ]

        maturity_table = parse_pdf_table(pages[5], 8)
        maturity_within_3m = []
        for row in maturity_table[1:]:
            maturity_within_3m.append(
                {
                    "code": row[0],
                    "name": row[1],
                    "maturity_date": parse_date(row[2]),
                    "original_issue_volume": parse_int(row[3]),
                    "current_outstanding": parse_int(row[4]),
                    "conversion_stop_start": parse_date(row[5]),
                    "conversion_stop_end": parse_date(row[6]),
                    "remaining_ratio_pct": percent_value(row[7]),
                }
            )

    tables = {
        "high_volume": high_volume,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "sellback_large": sellback_large,
        "new_listings": new_listings,
        "conversion_large": conversion_large,
        "auction_cases": auction_cases,
        "company_calls": company_calls,
        "putback_within_3m": putback_within_3m,
        "maturity_within_3m": maturity_within_3m,
    }
    for key, rows in tables.items():
        if not rows:
            warnings.append({"level": "warning", "table": key, "message": f"{key} 未解析到資料。"})
    return {
        "report_period": period,
        "source_file": str(pdf_path.relative_to(ROOT)).replace("\\", "/"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
        "warnings": warnings,
    }


def by_code(tables: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for table_name, rows in tables.items():
        for row in rows:
            code = str(row.get("code", ""))
            if not code:
                continue
            record = records.setdefault(code, {"code": code, "name": row.get("name", ""), "signals": {}, "raw": {}})
            if row.get("name") and not record.get("name"):
                record["name"] = row.get("name")
            record["signals"][table_name] = row
            record["raw"][table_name] = row
    return records


def score_watchlist(data: dict[str, Any]) -> list[dict[str, Any]]:
    tables = data["tables"]
    records = by_code(tables)
    max_conv = max([r.get("weekly_conversion_volume") or 0 for r in tables["conversion_large"]] or [1])
    max_volume = max([r.get("weekly_volume") or 0 for r in tables["high_volume"]] or [1])
    watchlist = []
    for code, record in records.items():
        signals = record["signals"]
        score = 0.0
        reasons: list[str] = []
        risks: list[str] = []
        signal_types: list[str] = []

        if "conversion_large" in signals:
            row = signals["conversion_large"]
            volume = row.get("weekly_conversion_volume") or 0
            intensity = row.get("conversion_intensity_pct") or 0
            score += min(40, 22 * volume / max_conv + min(18, intensity * 0.8))
            signal_types.append("轉換量")
            reasons.append(f"本週轉換 {volume:,} 張，轉換強度約 {intensity:.2f}%。")

        if "new_listings" in signals:
            row = signals["new_listings"]
            score += 18
            signal_types.append("新掛牌")
            issue = row.get("issue_price_pct")
            if isinstance(issue, (int, float)) and issue > 130:
                risks.append("發行價格偏高，掛牌後賣壓需留意。")
            reasons.append(f"近期掛牌，掛牌日 {row.get('listing_date')}。")

        if "auction_cases" in signals:
            score += 7
            signal_types.append("競拍")
            reasons.append("近期競拍案件，適合事件型追蹤。")

        if "high_volume" in signals:
            row = signals["high_volume"]
            volume = row.get("weekly_volume") or 0
            score += min(15, 15 * volume / max_volume)
            signal_types.append("流動性")
            reasons.append(f"週成交量 {volume:,} 張，日均約 {row.get('avg_daily_volume')} 張。")

        if "sellback_large" in signals:
            row = signals["sellback_large"]
            score -= 8
            signal_types.append("賣回")
            risks.append(f"本週賣回 {abs(row.get('weekly_sellback_volume') or 0):,} 張，需確認市場接受度。")

        if "company_calls" in signals:
            row = signals["company_calls"]
            ratio = row.get("remaining_ratio_pct") or 0
            score -= 14 if ratio < 5 else 10
            signal_types.append("贖回風險")
            risks.append(f"公司執行贖回權，終止掛牌日 {row.get('termination_date')}，剩餘比率 {ratio}%。")

        if "putback_within_3m" in signals:
            row = signals["putback_within_3m"]
            score -= 5
            signal_types.append("三個月賣回")
            risks.append(f"三個月內賣回，賣回日 {row.get('putback_date')}。")

        if "maturity_within_3m" in signals:
            row = signals["maturity_within_3m"]
            ratio = row.get("remaining_ratio_pct") or 0
            score -= 8 if ratio < 10 else 4
            signal_types.append("三個月到期")
            risks.append(f"三個月內到期，到期日 {row.get('maturity_date')}。")

        if "top_gainers" in signals:
            score += 6
            signal_types.append("漲幅")
            reasons.append("進入漲幅榜，僅作動能參考。")
        if "top_losers" in signals:
            score -= 2
            signal_types.append("跌幅")
            risks.append("進入跌幅榜，需確認基本面或轉換賣壓原因。")

        risk_level = "低"
        if any(word in " ".join(risks) for word in ["贖回", "到期", "賣回"]) or score < 35:
            risk_level = "中"
        if "company_calls" in signals and (signals["company_calls"].get("remaining_ratio_pct") or 0) < 5:
            risk_level = "高"

        bounded = max(0, min(100, round(score, 1)))
        if risk_level == "高":
            action = "Avoid / remove from watchlist"
        elif bounded >= 55:
            action = "Priority research"
        elif "auction_cases" in signals or "new_listings" in signals:
            action = "Event-driven only"
        else:
            action = "Watch only"

        watchlist.append(
            {
                "code": code,
                "name": record.get("name", ""),
                "score": bounded,
                "signal_type": "、".join(dict.fromkeys(signal_types)) or "參考",
                "risk_level": risk_level,
                "trading_interpretation": "；".join(reasons) if reasons else "本週有週評訊號，建議搭配流動性與剩餘比率檢查。",
                "risk_warning": "；".join(risks) if risks else "未見明顯賣回、贖回或到期風險，但仍需檢查溢價率與正股走勢。",
                "suggested_action": action,
                "raw": record["raw"],
            }
        )
    return sorted(watchlist, key=lambda item: item["score"], reverse=True)


def market_summary(data: dict[str, Any]) -> dict[str, Any]:
    tables = data["tables"]
    text = (
        f"本週高轉換量標的有 {len(tables['conversion_large'])} 檔，"
        f"新掛牌 {len(tables['new_listings'])} 檔，"
        f"高成交量 {len(tables['high_volume'])} 檔。"
        "追蹤順序以轉換量與新掛牌為主，賣回、贖回與到期風險會降低一般交易優先度。"
    )
    return {
        "high_volume_count": len(tables["high_volume"]),
        "new_listings_count": len(tables["new_listings"]),
        "conversion_large_count": len(tables["conversion_large"]),
        "sellback_large_count": len(tables["sellback_large"]),
        "company_call_count": len(tables["company_calls"]),
        "interpretation_zh": text,
    }


def write_outputs(data: dict[str, Any]) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    data["watchlist"] = score_watchlist(data)
    data["summary"] = market_summary(data)

    period_id = data["report_period"]["start"].replace("-", "") + "_" + data["report_period"]["end"].replace("-", "")
    json_path = PROCESSED_DIR / "cb_weekly_latest.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (HISTORY_DIR / f"{period_id}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = PROCESSED_DIR / "cb_weekly_latest.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "rank",
                "code",
                "name",
                "score",
                "signal_type",
                "risk_level",
                "suggested_action",
                "trading_interpretation",
                "risk_warning",
            ],
        )
        writer.writeheader()
        for index, row in enumerate(data["watchlist"], 1):
            writer.writerow({"rank": index, **{key: row.get(key, "") for key in writer.fieldnames if key != "rank"}})

    data_js = "window.CB_WEEKLY_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n"
    (DIST_DIR / "data.js").write_text(data_js, encoding="utf-8")


def main() -> None:
    pdf_path, source_warnings = find_latest_pdf()
    data = parse_latest_pdf(pdf_path)
    data["warnings"] = source_warnings + data["warnings"]
    write_outputs(data)
    parsed_count = sum(1 for rows in data["tables"].values() if rows)
    print(f"資料期間：{data['report_period']['start']} ~ {data['report_period']['end']}")
    print(f"來源檔案：{data['source_file']}")
    print(f"成功解析表格：{parsed_count}/10")
    print(f"追蹤名單筆數：{len(data['watchlist'])}")
    print("前 10 名：" + "、".join(f"{row['code']} {row['name']}" for row in data["watchlist"][:10]))


if __name__ == "__main__":
    main()
