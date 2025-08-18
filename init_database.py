import pandas as pd
import os
from datetime import datetime
from app import create_app, db
from app.models import MainBOMStorage

def load_bom_seed_csv():
    """Load data from bom_seed.csv and insert/update all records in MainBOMStorage."""
    app = create_app()
    with app.app_context():
        try:
            # Read CSV from root folder
            csv_path = os.path.join(os.getcwd(), "bom_seed.csv")
            if not os.path.isfile(csv_path):
                print(f"File not found: {csv_path}")
                return False

            print(f"Loading BOM data from {csv_path} ...")
            df = pd.read_csv(csv_path)
            imported_count = 0
            updated_count = 0

            # Insert or update each row
            for i, row in df.iterrows():
                part_number = str(row.get('Part Number', '')).strip()
                if not part_number:
                    continue

                # Map CSV columns to model fields
                part_name = str(row.get('Description', '')).strip()
                supplier = str(row.get('Supplier', '')).strip()
                component = str(row.get('Component', '')).strip()
                qty_per_lrv = float(row.get('Qty per LRV', 0) or 0)
                qty_on_site = float(row.get('Qty in Site Inventory', 0) or 0)
                qty_current_stock = float(row.get('Qty Remaining', 0) or 0)
                notes = str(row.get('Notes', '') if not pd.isna(row.get('Notes', '')) else "").strip()
                order_status = str(row.get('Order Status', '') if not pd.isna(row.get('Order Status', '')) else "").strip()
                consumable_or_essential = str(row.get('Type', '') if not pd.isna(row.get('Type', '')) else "Essential").strip()
                # Optional: Add other fields you want from the CSV

                # Compute total_needed_233_lrv if you want (else remove this)
                total_needed_233_lrv = qty_per_lrv * 233
                lrv_coverage = float(row.get('Stock for Number of Trains', 0) or 0)

                # Try to find existing part
                part = MainBOMStorage.query.filter_by(part_number=part_number).first()
                if part:
                    # Update fields
                    part.part_name = part_name
                    part.supplier = supplier
                    part.component = component
                    part.qty_per_lrv = qty_per_lrv
                    part.qty_on_site = qty_on_site
                    part.qty_current_stock = qty_current_stock
                    part.notes = notes
                    part.order_status = order_status
                    part.consumable_or_essential = consumable_or_essential
                    part.total_needed_233_lrv = total_needed_233_lrv
                    part.lrv_coverage = lrv_coverage
                    part.updated_at = datetime.utcnow()
                    part.calculate_lrv_coverage()
                    updated_count += 1
                else:
                    # Insert new record
                    new_part = MainBOMStorage(
                        part_number=part_number,
                        part_name=part_name,
                        supplier=supplier,
                        component=component,
                        qty_per_lrv=qty_per_lrv,
                        qty_on_site=qty_on_site,
                        qty_current_stock=qty_current_stock,
                        notes=notes,
                        order_status=order_status,
                        consumable_or_essential=consumable_or_essential,
                        total_needed_233_lrv=total_needed_233_lrv,
                        lrv_coverage=lrv_coverage,
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

            # Always import data for a true "seed" script—otherwise, comment out if you want one-time only
            return load_bom_seed_csv()

        except Exception as e:
            print(f"Database initialization error: {e}")
            return False

if __name__ == '__main__':
    print("BOM Inventory Dashboard - Database Initialization")
    print("=" * 50)
    if init_database():
        print("\n✅ Database is ready!")
        print("You can now start your application with: python app.py")
    else:
        print("\n❌ Database initialization failed!")
        print("Please check the error messages above.")
