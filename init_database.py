import pandas as pd
import os
from datetime import datetime
from app import create_app, db
from app.models import MainBOMStorage, InventoryDivision, DivisionPartInventory

def safe_str(val, maxlen):
    """Convert to string and cut to maxlen chars, unless empty/NaN."""
    if pd.isna(val):
        return ""
    s = str(val)
    return s[:maxlen]

def safe_float(val):
    """Convert to float if possible, else 0.0"""
    try:
        if pd.isna(val) or val == "" or str(val).startswith("#") or str(val).strip() == "":
            return 0.0
        s = str(val).replace(",", "").strip()
        if s in ["#VALUE!", "nan"]:
            return 0.0
        return float(s)
    except Exception:
        return 0.0

def load_bom_seed_csv():
    """Load data from bom_seed.csv and insert/update all records in MainBOMStorage."""
    app = create_app()
    with app.app_context():
        try:
            csv_path = os.path.join(os.getcwd(), "bom_seed.csv")
            if not os.path.isfile(csv_path):
                print(f"File not found: {csv_path}")
                return False

            print(f"Loading BOM data from {csv_path} ...")
            df = pd.read_csv(csv_path)
            imported_count = 0
            updated_count = 0

            for i, row in df.iterrows():
                part_number = safe_str(row.get('Part Number', ''), 99)
                if not part_number:
                    continue

                part_name = safe_str(row.get('Description', ''), 99)
                supplier = safe_str(row.get('Supplier', ''), 99)
                component = safe_str(row.get('Component', ''), 99)
                consumable_or_essential = safe_str(row.get('Type', ''), 99)
                order_status = safe_str(row.get('Order Status', ''), 99)
                notes = safe_str(row.get('Notes', ''), 255)

                qty_per_lrv = safe_float(row.get('Qty per LRV', 0))
                no_of_car = safe_float(row.get('No. of car', 0))
                total_needed = safe_float(row.get('Total', 0))
                qty_on_site = safe_float(row.get('Qty on Site', 0))
                qty_shipped_out = safe_float(row.get('Shipped out of store', 0))
                qty_should_be_remaining = safe_float(row.get('Qty should be remaining', 0))
                qty_actual_remaining = safe_float(row.get('Qty actually remaining', 0))
                back_order_qty = safe_float(row.get('Back Order \n Qty', 0))
                more_needed_50 = safe_float(row.get('More needed for 50', 0))

                stock_for_trains = safe_float(row.get('Stock for Number of Trains', 0))
                next_delivery_trains = safe_float(row.get('No. of Trains Next Delivery', 0))
                qty_required_more_trains = safe_float(row.get('Qty Required for # More Trains', 0))

                # Choose what to map/import:
                # For a comprehensive BOM, these are typical model fields. You can expand your MainBOMStorage model to add more.
                part = MainBOMStorage.query.filter_by(part_number=part_number).first()
                if part:
                    part.part_name = part_name
                    part.supplier = supplier
                    part.component = component
                    part.qty_per_lrv = qty_per_lrv
                    part.qty_on_site = qty_on_site
                    part.qty_shipped_out = qty_shipped_out
                    part.qty_current_stock = qty_actual_remaining
                    part.notes = notes
                    part.order_status = order_status
                    part.consumable_or_essential = consumable_or_essential
                    part.total_needed_233_lrv = total_needed
                    part.lrv_coverage = stock_for_trains
                    part.back_order_qty = back_order_qty
                    part.updated_at = datetime.utcnow()
                    part.calculate_lrv_coverage()
                    updated_count += 1
                else:
                    new_part = MainBOMStorage(
                        part_number=part_number,
                        part_name=part_name,
                        supplier=supplier,
                        component=component,
                        qty_per_lrv=qty_per_lrv,
                        qty_on_site=qty_on_site,
                        qty_shipped_out=qty_shipped_out,
                        qty_current_stock=qty_actual_remaining,
                        notes=notes,
                        order_status=order_status,
                        consumable_or_essential=consumable_or_essential,
                        total_needed_233_lrv=total_needed,
                        lrv_coverage=stock_for_trains,
                        back_order_qty=back_order_qty,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    new_part.calculate_lrv_coverage()
                    db.session.add(new_part)
                    imported_count += 1
            db.session.commit()
            print(f"\nImport completed!")
            print(f"New parts imported: {imported_count}")
            print(f"Existing parts updated: {updated_count}")
            print(f"Total parts in database: {MainBOMStorage.query.count()}")

            return True
        except Exception as e:
            print(f"Error loading BOM seed CSV: {e}")
            db.session.rollback()
            return False

def init_database():
    """Initialize the database and load BOM seed data."""
    app = create_app()
    with app.app_context():
        try:
            print("Initializing database...")
            db.create_all()
            print("Database tables created successfully!")
            return load_bom_seed_csv()

        except Exception as e:
            print(f"Database initialization error: {e}")
            return False

def seed_divisions():
    """Seed the database with initial divisions and their part inventories."""
    app = create_app()
    with app.app_context():
        try:
            print("Seeding divisions...")
            division_names = ['Division 11', 'Division 14', 'Division 16', 'Division 21']
            parts = MainBOMStorage.query.all()

            for name in division_names:
                division = InventoryDivision.query.filter_by(division_name=name).first()
                if not division:
                    division = InventoryDivision(division_name=name)
                    db.session.add(division)
                    db.session.flush()  # Get the division ID
                    print(f"Created division: {name}")

                for part in parts:
                    div_part_inv = DivisionPartInventory.query.filter_by(
                        part_id=part.id,
                        division_id=division.id
                    ).first()

                    if not div_part_inv:
                        new_div_part = DivisionPartInventory(
                            part_id=part.id,
                            division_id=division.id,
                            qty_sent_to_site=0,
                            qty_used_on_site=0,
                            qty_remaining=0
                        )
                        db.session.add(new_div_part)

            db.session.commit()
            print("Divisions and their part inventories seeded successfully!")
            return True
        except Exception as e:
            print(f"Error seeding divisions: {e}")
            db.session.rollback()
            return False

if __name__ == '__main__':
    print("BOM Inventory Dashboard - Database Initialization")
    print("=" * 50)
    if init_database():
        load_bom_seed_csv()
        seed_divisions()
        print("\n✅ Database is ready!")
        print("You can now start your application with: python app.py")
    else:
        print("\n❌ Database initialization failed!")
        print("Please check the error messages above.")
