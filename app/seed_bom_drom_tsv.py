# scripts/seed_bom_from_tsv.py
import os, re, sys, math
from datetime import datetime

# Flexible import (works whether your package is "app" or flat files)
try:
    from app import create_app, db
    from app.models import MainBOMStorage
except Exception:
    from __init__ import create_app, db  # fallback
    import models as _m
    MainBOMStorage = _m.MainBOMStorage

import pandas as pd

FIELD_MAP = {
    "Part Number": "part_number",
    "Description": "part_name",            # your sheet’s “Description” is the display name
    "Supplier": "supplier",
    "Component": "component",
    "Qty per LRV": "qty_per_lrv",
    "No. of car": "num_cars",
    "Total": "qty_total",
    "Qty on Site": "qty_on_site",
    "Shipped out of store": "qty_shipped_out",
    "Qty should be remaining": "qty_should_be_remaining",
    "Qty actually remaining": "qty_current_stock",  # dashboard likely uses current stock
    "Notes": "notes",
    "More needed for 50": "more_needed_for_50",
    "Back Order \nQty": "back_order_qty",
    "Back Order Qty": "back_order_qty",
    "Order Status": "order_status",
    "Stock for Number of Trains": "stock_for_num_trains",
    "No. of Trains Next Delivery": "num_trains_next_delivery",
    "Qty Required for # More Trains": "qty_required_more_trains",
    "Materials Shipped out for No. of Trains": "materials_shipped_for_trains",
    "Type": "item_type",
}

NUMERIC_COLS = {
    "qty_per_lrv","num_cars","qty_total","qty_on_site","qty_shipped_out",
    "qty_should_be_remaining","qty_current_stock","more_needed_for_50",
    "back_order_qty","stock_for_num_trains","num_trains_next_delivery",
    "qty_required_more_trains","materials_shipped_for_trains"
}

PKEY = "part_number"

def coerce_number(v, note_list):
    if v is None or (isinstance(v, float) and math.isnan(v)): return None
    s = str(v).strip()
    if s in ("", "#VALUE!", "NA", "N/A", "None", "-"): return None
    # Handle "25(16)" -> 25 and add a note about the "(16)"
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*\(([^)]+)\)\s*$", s)
    if m:
        try:
            base = float(m.group(1))
            note_list.append(f"Parsed '{s}': stored {base}, extra='{m.group(2)}'")
            return base
        except:
            pass
    # Strip commas and try float/int
    s2 = s.replace(",", "")
    try:
        f = float(s2)
        # collapse 12.0 to 12
        return int(f) if f.is_integer() else f
    except:
        note_list.append(f"Kept as text: {s}")
        return None

def load_frame(path_guess="bom_seed.tsv"):
    if os.path.exists(path_guess):
        if path_guess.endswith(".csv"):
            return pd.read_csv(path_guess, dtype=str).fillna("")
        return pd.read_csv(path_guess, sep="\t", dtype=str).fillna("")
    # fallbacks
    for p in ("bom_seed.csv", "data/bom_seed.tsv", "data/bom_seed.csv"):
        if os.path.exists(p):
            return load_frame(p)
    raise SystemExit("Could not find bom_seed.tsv or bom_seed.csv in repo root.")

def main():
    app = create_app()
    with app.app_context():
        df = load_frame()
        # Normalize headers
        df.columns = [c.replace("\u00a0"," ").replace("\r"," ").replace("\n"," ").strip() for c in df.columns]
        # Build records
        created, updated, skipped = 0, 0, 0
        for idx, row in df.iterrows():
            # Build payload with mapped keys
            notes_extra = []
            payload = {}
            for col, attr in FIELD_MAP.items():
                if col not in df.columns: 
                    continue
                val = row[col]
                if attr in NUMERIC_COLS:
                    val = coerce_number(val, notes_extra)
                else:
                    val = (str(val).strip() if str(val).strip() != "" else None)
                payload[attr] = val

            if not payload.get(PKEY):
                skipped += 1
                continue

            # Merge notes
            existing_notes = payload.get("notes") or ""
            if notes_extra:
                merged = (existing_notes + (" | " if existing_notes else "") + "; ".join(notes_extra)).strip()
                payload["notes"] = merged

            # Upsert by part_number
            obj = MainBOMStorage.query.filter_by(part_number=payload[PKEY]).first()
            if obj is None:
                obj = MainBOMStorage()
                setattr(obj, PKEY, payload[PKEY])
                created += 1
            else:
                updated += 1

            # Set only attributes that actually exist on the model
            for k, v in payload.items():
                if k == PKEY: 
                    continue
                if hasattr(MainBOMStorage, k):
                    setattr(obj, k, v)
                else:
                    # If model lacks the column, append to notes so data isn't lost
                    if hasattr(MainBOMStorage, "notes") and v not in (None, "") and k not in ( "notes", ):
                        extra = f"{k}={v}"
                        obj.notes = (obj.notes + " | " if obj.notes else "") + extra

            # Optional: recompute coverage if the model has a helper
            if hasattr(obj, "calculate_lrv_coverage"):
                try: obj.calculate_lrv_coverage()
                except Exception: pass

            db.session.add(obj)

        db.session.commit()
        print(f"Done. created={created}, updated={updated}, skipped(no part#)={skipped}")

if __name__ == "__main__":
    main()
