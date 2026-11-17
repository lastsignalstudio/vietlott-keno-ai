
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]

SEED = ROOT / "data/official-confirmed.json/data/official-confirmed.json"
CSV_FILE = ROOT / ".cache/keno/draws.csv"
REPORT = ROOT / ".cache/keno/incremental-update-report.json"
OUTPUT = ROOT / "data/keno-draws.json"


def read_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def valid_numbers(numbers):
    return (
        isinstance(numbers, list)
        and len(numbers) == 20
        and len(set(numbers)) == 20
        and all(type(n) is int and 1 <= n <= 80 for n in numbers)
    )


old = read_json(OUTPUT, {})
records = {
    str(x["draw_id"]).zfill(7): x
    for x in old.get("records", [])
}

# Giữ lại các kỳ đã nhập thủ công từ ảnh Vietlott
seed = read_json(SEED, {"draws": []})

for draw in seed.get("draws", []):
    draw_id = str(draw["draw_id"]).replace("#", "").zfill(7)
    numbers = draw.get("numbers", [])

    if not valid_numbers(numbers):
        continue

    records[draw_id] = {
        "draw_id": draw_id,
        "date": draw["date"],
        "numbers": numbers,
        "verification_status": "screenshot_confirmed_manual",
        "source": seed.get("source", "user_screenshot"),
        "source_url": None
    }

conflicts = old.get("conflicts", [])
official_count = 0
secondary_count = 0

# Nhập dữ liệu từ collector
if CSV_FILE.exists():
    with CSV_FILE.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("product") != "keno":
                continue

            try:
                result = json.loads(row["result_json"])
                numbers = result.get("numbers", [])
                draw_id = str(row["draw_id"]).zfill(7)
                date = row["draw_date"]

                if not valid_numbers(numbers):
                    continue

                attrs = json.loads(row.get("attributes_json") or "{}")
                source_url = row.get("source_url", "")
                host = urlparse(source_url).hostname or ""

                is_official = (
                    (host == "vietlott.vn" or host.endswith(".vietlott.vn"))
                    and attrs.get("data_source") == "official_vietlott"
                    and row.get("draw_status") == "confirmed"
                    and row.get("validation_status") != "warning"
                )

                status = (
                    "official_verified"
                    if is_official
                    else "secondary_pending"
                )

                new_record = {
                    "draw_id": draw_id,
                    "date": date,
                    "numbers": numbers,
                    "verification_status": status,
                    "source": attrs.get("data_source", "unknown"),
                    "source_url": source_url,
                    "fetched_at": row.get("fetched_at")
                }

                current = records.get(draw_id)

                if is_official:
                    official_count += 1

                    if current and current["numbers"] != numbers:
                        conflicts.append({
                            "draw_id": draw_id,
                            "previous": current,
                            "official_candidate": new_record
                        })

                    records[draw_id] = new_record

                else:
                    secondary_count += 1

                    if current is None:
                        records[draw_id] = new_record
                    elif current["numbers"] != numbers:
                        conflicts.append({
                            "draw_id": draw_id,
                            "existing": current,
                            "secondary_candidate": new_record
                        })

            except (ValueError, KeyError, TypeError):
                continue

# Loại bỏ bản ghi trùng và sắp xếp
ordered = sorted(
    records.values(),
    key=lambda x: int(x["draw_id"])
)

# Giới hạn lịch sử xung đột, tránh file phình to
conflicts = conflicts[-200:]

payload = {
    "schema_version": 1,
    "product": "VIETLOTT_KENO",
    "updated_at_utc": old.get("updated_at_utc"),
    "latest_draw_id": ordered[-1]["draw_id"] if ordered else None,
    "source_policy": "official_first_secondary_fallback",
    "records": ordered,
    "conflicts": conflicts,
    "source_summary": {
        "official_records_seen": official_count,
        "secondary_records_seen": secondary_count,
        "total_saved": len(ordered)
    }
}

# Chỉ cập nhật timestamp khi nội dung dữ liệu thay đổi
old_compare = {
    k: v for k, v in old.items() if k != "updated_at_utc"
}
new_compare = {
    k: v for k, v in payload.items() if k != "updated_at_utc"
}

if old_compare != new_compare or not OUTPUT.exists():
    payload["updated_at_utc"] = datetime.now(
        timezone.utc
    ).isoformat()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    print("KENO DATA UPDATED")
else:
    print("NO NEW DATA")

print("Total records:", len(ordered))
print("Latest draw:", payload["latest_draw_id"])
print("Official candidates:", official_count)
print("Secondary candidates:", secondary_count)
