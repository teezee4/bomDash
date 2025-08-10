# migrate_excel_data.py
import argparse
import os
import re
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import (
    create_engine, String, Integer, Float, DateTime, Text, MetaData, Table, Column, Index,
    inspect
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

# ---------------------------
# Expected headers (canonical)
# ---------------------------
EXPECTED_COLUMNS = [
    "Part Number",
    "Part Name",
    "Supplier",
    "Description",
    "Type",
    "Qty Needed Per LRV",
    "Total needed for 233 LRV",
    "Total quantity received by store",
    "Quantity shipped out by store",
    "Quantity currently in stock at store",
    "Quantity Back Ordered",
    "Back Order Delivery Info",
    "Notes",
    "Stock for Number of Trains",
    "No. of Trains Next Delivery",
    "Qty Required for # More Trains",
]

NUMERIC_COLUMNS = {
    "Qty Needed Per LRV",
    "Total needed for 233 LRV",
    "Total quantity received by store",
    "Quantity shipped out by store",
    "Quantity currently in stock at store",
    "Quantity Back Ordered",
    "Stock for Number of Trains",
    "No. of Trains Next Delivery",
    "Qty Required for # More Trains",
}

NA_TOKENS = {"N/A", "NA", "#N/A", "NONE", "NULL", "—", "-", "--"}

# -----------------------------------
# Header normalization/mapping helpers
# -----------------------------------
def normalize_header_name(name: str) -> str:
    """
    Normalize a header:
    - Replace non-breaking spaces
    - Strip leading/trailing whitespace and control characters
    - Remove trailing newlines/tabs
    - Collapse multiple internal whitespace into single space
    """
    if name is None:
        return ""
    s = str(name).replace("\u00A0", " ")
    s = s.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def build_header_map(found_cols):
    """
    Build a mapping from current dataframe columns to the canonical EXPECTED_COLUMNS.
    Performs normalization and exact matching after normalization.
    """
    norm_found = {c: normalize_header_name(c) for c in found_cols}

    # Direct mapping where normalized names match expected exactly
    reverse_norm = {v: k for k, v in norm_found.items()}

    mapping = {}
    missing = []
    for expected in EXPECTED_COLUMNS:
        if expected in reverse_norm:
            orig_col = reverse_norm[expected]
            mapping[orig_col] = expected
        else:
            # Try tolerant matches for very small differences (e.g., double spaces)
            def simplify(s):
                s2 = s.lower()
                s2 = re.sub(r"[^a-z0-9]+", " ", s2)
                s2 = re.sub(r"\s+", " ", s2).strip()
                return s2

            expected_simple = simplify(expected)
            candidates = [orig for orig, norm in norm_found.items() if simplify(norm) == expected_simple]
            if candidates:
                mapping[candidates[0]] = expected
            else:
                missing.append(expected)

    if missing:
        raise ValueError(
            f"Missing expected columns after normalization: {missing}. "
            f"Found (normalized): {sorted(set(norm_found.values()))}"
        )

    return mapping

# ----------------
# Value normalizers
# ----------------
def clean_text(val):
    if val is None:
        return None
    s = str(val).replace("\u00A0", " ").strip()
    if s == "" or s.upper() in NA_TOKENS:
        return None
    return s

def to_number(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        try:
            if pd.isna(val):
                return None
        except Exception:
            pass
        return float(val)
    s = clean_text(val)
    if s is None:
        return None
    # remove thousands separators and spaces
    s = re.sub(r"[,\s]", "", s)
    # capture numeric prefix (handles scientific notation)
    m = re.match(r"^([+-]?\d+(\.\d+)?([eE][+-]?\d+)?)", s)
    if m:
        s = m.group(1)
    try:
        return float(s)
    except Exception:
        return None

def compute_helpers(row):
    qty_per_lrv = to_number(row.get("Qty Needed Per LRV"))
    current_stock = to_number(row.get("Quantity currently in stock at store"))
    total_needed_233 = to_number(row.get("Total needed for 233 LRV"))

    coverage_lrvs = None
    if qty_per_lrv and qty_per_lrv > 0 and current_stock is not None:
        coverage_lrvs = int(current_stock // qty_per_lrv)

    qty_short_for_233 = None
    if total_needed_233 is not None and current_stock is not None:
        qty_short_for_233 = max(0.0, total_needed_233 - current_stock)

    return coverage_lrvs, qty_short_for_233

# -------------
# DB definition and safe creation
# -------------
def ensure_schema(engine):
    """
    Create schema if it doesn't exist, or ensure it matches expected structure.
    Uses inspector to check existing tables/indexes before creating.
    """
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    meta = MetaData()
    
    # Define tables
    main_bom_storage = Table(
        "main_bom_storage",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("part_number", String(128), nullable=False, unique=True, index=True),
        Column("part_name", Text),
        Column("supplier", Text),
        Column("description", Text),
        Column("type", Text),

        Column("qty_needed_per_lrv", Float),
        Column("total_needed_for_233_lrv", Float),
        Column("total_quantity_received_by_store", Float),
        Column("quantity_shipped_out_by_store", Float),
        Column("quantity_currently_in_stock_at_store", Float),
        Column("quantity_back_ordered", Float),
        Column("back_order_delivery_info", Text),
        Column("notes", Text),

        Column("stock_for_number_of_trains", Float),
        Column("no_of_trains_next_delivery", Float),
        Column("qty_required_for_more_trains", Float),

        Column("coverage_lrvs", Integer),
        Column("qty_short_for_233", Float),

        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
    )

    delivery_log = Table(
        "delivery_log",
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("part_number", String(128), nullable=False, index=True),
        Column("part_name", Text),
        Column("supplier", Text),
        Column("quantity_received", Float),
        Column("date_received", DateTime),
        Column("notes", Text),
        Column("created_at", DateTime, nullable=False),
    )

    # Create tables that don't exist
    tables_to_create = []
    if "main_bom_storage" not in existing_tables:
        tables_to_create.append(main_bom_storage)
    if "delivery_log" not in existing_tables:
        tables_to_create.append(delivery_log)
    
    if tables_to_create:
        for table in tables_to_create:
            table.create(engine)
        print(f"Created {len(tables_to_create)} new table(s)")
    
    # Handle indexes separately to avoid conflicts
    if "main_bom_storage" in existing_tables:
        existing_indexes = inspector.get_indexes("main_bom_storage")
        index_names = [idx['name'] for idx in existing_indexes]
        
        # Only create the named index if it doesn't exist
        if "ix_main_bom_storage_part_number" not in index_names:
            idx = Index("ix_main_bom_storage_part_number", main_bom_storage.c.part_number, unique=True)
            idx.create(engine)
    
    return main_bom_storage, delivery_log

# ---------------
# Main processing
# ---------------
def main():
    parser = argparse.ArgumentParser(description="Import BOM Excel into SQLite (header-normalized, schema-safe).")
    parser.add_argument("excel_path", help="Path to .xlsx file")
    parser.add_argument("--sheet", dest="sheet_name", default=None, help="Worksheet name (default: first sheet)")
    parser.add_argument("--db", dest="db_path", default=os.path.join("instance", "bominventory.db"),
                        help="SQLite DB path (default: instance/bominventory.db)")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.db_path), exist_ok=True)

    # Read Excel with minimal NA coercion
    if args.sheet_name:
        df = pd.read_excel(args.excel_path, sheet_name=args.sheet_name, keep_default_na=False, na_filter=False)
    else:
        df = pd.read_excel(args.excel_path, keep_default_na=False, na_filter=False)

    print(f"Read Excel file with {len(df)} rows and {len(df.columns)} columns")

    # Normalize headers and remap to canonical names
    original_cols = list(df.columns)
    mapping = build_header_map(original_cols)
    df = df.rename(columns=mapping)

    # Normalize values per column types
    for c in df.columns:
        if c in NUMERIC_COLUMNS:
            df[c] = df[c].map(to_number)
        else:
            df[c] = df[c].map(clean_text)

    # Compute helpers
    helpers = df.apply(compute_helpers, axis=1, result_type="expand")
    df["coverage_lrvs"] = helpers[0] if len(helpers.columns) > 0 else None
    df["qty_short_for_233"] = helpers[1] if len(helpers.columns) > 1 else None

    # Use timezone-aware datetime
    now = datetime.now(timezone.utc)

    engine = create_engine(f"sqlite:///{args.db_path}")
    main_bom_storage, delivery_log = ensure_schema(engine)

    # Build records and upsert
    records = []
    for _, row in df.iterrows():
        part_number = row.get("Part Number")
        if not part_number:
            continue

        rec = {
            "part_number": part_number,
            "part_name": row.get("Part Name"),
            "supplier": row.get("Supplier"),
            "description": row.get("Description"),
            "type": row.get("Type"),

            "qty_needed_per_lrv": row.get("Qty Needed Per LRV"),
            "total_needed_for_233_lrv": row.get("Total needed for 233 LRV"),
            "total_quantity_received_by_store": row.get("Total quantity received by store"),
            "quantity_shipped_out_by_store": row.get("Quantity shipped out by store"),
            "quantity_currently_in_stock_at_store": row.get("Quantity currently in stock at store"),
            "quantity_back_ordered": row.get("Quantity Back Ordered"),
            "back_order_delivery_info": row.get("Back Order Delivery Info"),
            "notes": row.get("Notes"),

            "stock_for_number_of_trains": row.get("Stock for Number of Trains"),
            "no_of_trains_next_delivery": row.get("No. of Trains Next Delivery"),
            "qty_required_for_more_trains": row.get("Qty Required for # More Trains"),

            "coverage_lrvs": row.get("coverage_lrvs"),
            "qty_short_for_233": row.get("qty_short_for_233"),

            "created_at": now,
            "updated_at": now,
        }
        records.append(rec)

    print(f"Prepared {len(records)} records for import")

    with engine.begin() as conn:
        if records:
            ins = sqlite_insert(main_bom_storage).values(records)
            stmt = ins.on_conflict_do_update(
                index_elements=[main_bom_storage.c.part_number],
                set_={
                    "part_name": ins.excluded.part_name,
                    "supplier": ins.excluded.supplier,
                    "description": ins.excluded.description,
                    "type": ins.excluded.type,

                    "qty_needed_per_lrv": ins.excluded.qty_needed_per_lrv,
                    "total_needed_for_233_lrv": ins.excluded.total_needed_for_233_lrv,
                    "total_quantity_received_by_store": ins.excluded.total_quantity_received_by_store,
                    "quantity_shipped_out_by_store": ins.excluded.quantity_shipped_out_by_store,
                    "quantity_currently_in_stock_at_store": ins.excluded.quantity_currently_in_stock_at_store,
                    "quantity_back_ordered": ins.excluded.quantity_back_ordered,
                    "back_order_delivery_info": ins.excluded.back_order_delivery_info,
                    "notes": ins.excluded.notes,

                    "stock_for_number_of_trains": ins.excluded.stock_for_number_of_trains,
                    "no_of_trains_next_delivery": ins.excluded.no_of_trains_next_delivery,
                    "qty_required_for_more_trains": ins.excluded.qty_required_for_more_trains,

                    "coverage_lrvs": ins.excluded.coverage_lrvs,
                    "qty_short_for_233": ins.excluded.qty_short_for_233,

                    "updated_at": datetime.now(timezone.utc),
                }
            )
            result = conn.execute(stmt)
            print(f"Upserted records - affected rows: {result.rowcount}")

    print(f"Import completed successfully! Database: {args.db_path}")

if __name__ == "__main__":
    main()
