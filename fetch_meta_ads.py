#!/usr/bin/env python3
"""
يسحب بيانات يومية (Spend / Orders / ROAS / CPP) لكل حساب إعلاني معرّف
في config/accounts.json من Meta Marketing API، ويحدّث ملفات JSON
في docs/data/<account_key>.json عشان الداشبورد الاستاتيك يقرأها.

يشتغل عن طريق GitHub Actions يوميًا (شوف .github/workflows/daily-fetch.yml)

المتغيرات البيئية المطلوبة:
  META_ACCESS_TOKEN   - System User access token (long-lived / never-expiring)

طول الفترة اللي بيتسحبها كل مرة:
  آخر LOOKBACK_DAYS يوم (افتراضي 30) عشان لو يوم فات، الداشبورد يتصحح
  أوتوماتيك (Meta بتحدّث الأرقام بأثر رجعي أحيانًا بسبب attribution window).
"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import date, timedelta

import requests

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "accounts.json"
DATA_DIR = ROOT / "docs" / "data"

LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "30"))

# أنواع الأحداث اللي بتتحسب كـ "أوردر". عدّلها لو الحساب بيقيس
# نتيجة تانية (زي Complete Registration بدل Purchase).
PURCHASE_ACTION_TYPES = ["purchase", "omni_purchase"]


def get_access_token() -> str:
    token = os.environ.get("META_ACCESS_TOKEN")
    if not token:
        print("ERROR: META_ACCESS_TOKEN env var not set", file=sys.stderr)
        sys.exit(1)
    return token


def fetch_insights(ad_account_id: str, token: str, since: str, until: str) -> list:
    """يسحب insights يوم بيوم (time_increment=1) على مستوى الحساب كله."""
    url = f"{GRAPH_API_BASE}/{ad_account_id}/insights"
    params = {
        "access_token": token,
        "level": "account",
        "time_increment": 1,
        "time_range": json.dumps({"since": since, "until": until}),
        "fields": "spend,reach,impressions,actions,action_values",
        "limit": 100,
    }

    rows = []
    while True:
        resp = requests.get(url, params=params, timeout=60)
        if resp.status_code != 200:
            print(f"ERROR fetching {ad_account_id}: {resp.status_code} {resp.text}", file=sys.stderr)
            resp.raise_for_status()
        payload = resp.json()
        rows.extend(payload.get("data", []))

        paging = payload.get("paging", {})
        next_url = paging.get("next")
        if not next_url:
            break
        # المكالمة الجاية فيها كل حاجة جاهزة جوه next_url
        resp = requests.get(next_url, timeout=60)
        if resp.status_code != 200:
            break
        payload = resp.json()
        rows.extend(payload.get("data", []))
        if not payload.get("paging", {}).get("next"):
            break
    return rows


def extract_purchase_metrics(row: dict) -> tuple:
    """يرجّع (عدد الأوردرات, قيمة الأوردرات) من قايمة actions/action_values."""
    orders = 0.0
    value = 0.0

    actions = row.get("actions", []) or []
    for a in actions:
        if a.get("action_type") in PURCHASE_ACTION_TYPES:
            orders = max(orders, float(a.get("value", 0)))

    action_values = row.get("action_values", []) or []
    for a in action_values:
        if a.get("action_type") in PURCHASE_ACTION_TYPES:
            value = max(value, float(a.get("value", 0)))

    return orders, value


def normalize_row(raw: dict) -> dict:
    spend = float(raw.get("spend", 0) or 0)
    reach = float(raw.get("reach", 0) or 0)
    impressions = float(raw.get("impressions", 0) or 0)
    orders, value = extract_purchase_metrics(raw)

    roas = round(value / spend, 3) if spend > 0 else 0.0
    cpp = round(spend / orders, 2) if orders > 0 else 0.0
    cpm = round(spend / reach * 1000, 2) if reach > 0 else 0.0

    return {
        "date": raw.get("date_start"),
        "spend": round(spend, 2),
        "orders": int(orders),
        "value": round(value, 2),
        "reach": int(reach),
        "impressions": int(impressions),
        "roas": roas,
        "cpp": cpp,
        "cpm": cpm,
    }


def load_existing(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"days": []}


def upsert_days(existing_days: list, new_days: list) -> list:
    by_date = {d["date"]: d for d in existing_days}
    for d in new_days:
        by_date[d["date"]] = d  # بيستبدل باليوم الجديد لو موجود (تصحيح رجعي)
    return sorted(by_date.values(), key=lambda x: x["date"])


def main():
    token = get_access_token()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    until = date.today()
    since = until - timedelta(days=LOOKBACK_DAYS)

    for account in config["accounts"]:
        key = account["key"]
        ad_account_id = account["ad_account_id"]

        if ad_account_id.strip().upper().endswith("XXXXXXXXXXXX"):
            print(f"SKIP {key}: ad_account_id لسه placeholder، حدّثه في config/accounts.json")
            continue

        print(f"Fetching {account['label']} ({ad_account_id}) ...")
        try:
            raw_rows = fetch_insights(ad_account_id, token, since.isoformat(), until.isoformat())
        except requests.HTTPError:
            print(f"  -> فشل السحب لـ {key}، هيتم تخطيه")
            continue

        new_days = [normalize_row(r) for r in raw_rows]

        out_path = DATA_DIR / f"{key}.json"
        existing = load_existing(out_path)
        merged_days = upsert_days(existing.get("days", []), new_days)

        out_path.write_text(
            json.dumps(
                {
                    "label": account["label"],
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                    "days": merged_days,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"  -> saved {len(merged_days)} days to {out_path}")

    # ملف فهرس بسيط يقول للداشبورد أنهي حسابات موجودة فعلاً
    index = [
        {"key": a["key"], "label": a["label"]}
        for a in config["accounts"]
        if (DATA_DIR / f"{a['key']}.json").exists()
    ]
    (DATA_DIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
