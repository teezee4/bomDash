import pandas as pd
import os
from datetime import datetime
from app import create_app, db
from app.models import MainBOMStorage

def import_bom_from_csv(csv_file_path='bom_seed.csv'):
    """Import BOM data from CSV file."""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if file exists in root folder
            if not os.path.exists(csv_file_path):
                print(f"CSV file not found: {csv_file_path}")
                print("Make sure bom_seed.csv is in the root folder of your project.")
                return False
                
            print(f"Reading CSV file: {csv_file_path}")
            # Read CSV file
            df = pd.read_csv(csv_file_path)
            print(f"Found {len(df)} rows in CSV file")

            imported_count = 0
            updated_count = 0
            error_count = 0

            for index, row in df.iterrows():
                try:
                    if pd.isna(row.get('Part Number')) or str(row.get('Part Number')).strip() == '':
                        continue

                    part_number = str(row['Part Number']).strip()
                    
                    existing_part = MainBOMStorage.query.filter_by(part_number=part_number).first()

                    # Map your CSV columns to MainBOMStorage fields
                    part_name = str(row.get('Description', '')).strip()
                    supplier = str(row.get('Supplier', '')).strip()
                    component = str(row.get('Component', '')).strip()
                    qty_per_lrv = float(row.get('Qty per LRV', 0)) if not pd.isna(row.get('Qty per LRV')) else 0
                    qty_on_site = float(row.get('Qty in Site Inventory', 0)) if not pd.isna(row.get('Qty in Site Inventory')) else 0
                    qty_used_on_site = float(row.get('Qty Used on Site', 0)) if not pd.isna(row.get('Qty Used on Site')) else 0
                    qty_current_stock = float(row.get('Qty Remaining', 0)) if not pd.isna(row.get('Qty Remaining')) else 0
                    notes = str(row.get('Notes', '')).strip() if not pd.isna(row.get('Notes')) else ''
                    order_status = str(row.get('Order Status', '')).strip() if not pd.isna(row.get('Order Status')) else ''
                    lrv_coverage = float(row.get('Stock for Number of Trains', 0)) if not pd.isna(row.get('Stock for Number of Trains')) else 0
                    type_col = str(row.get('Type', '')).strip() if not pd.isna(row.get('Type')) else 'Essential'
                    no_of_cars = float(row.get('No. of car', 0)) if not pd.isna(row.get('No. of car')) else 0

                    # Calculate total needed (assuming you want to track this)
                    total_needed_233_lrv = qty_per_lrv * 233  # For 233 LRVs as in your original setup

                    if existing_part:
                        # Update existing part
                        existing_part.part_name = part_name
                        existing_part.supplier = supplier
                        existing_part.component = component
                        existing_part.qty_per_lrv = qty_per_lrv
                        existing_part.total_needed_233_lrv = total_needed_233_lrv
                        existing_part.qty_on_site = qty_on_site
                        existing_part.qty_current_stock = qty_current_stock
                        existing_part.notes = notes
                        existing_part.order_status = order_status
                        existing_part.lrv_coverage = lrv_coverage
                        existing_part.consumable_or_essential = type_col
                        # Recalculate LRV coverage
                        existing_part.calculate_lrv_coverage()

                        updated_count += 1
                    else:
                        # Create new part
                        new_part = MainBOMStorage(
                            part_number=part_number,
                            part_name=part_name,
                            supplier=supplier,
                            component=component,
                            qty_per_lrv=qty_per_lrv,
                            total_needed_233_lrv=total_needed_233_lrv,
                            qty_on_site=qty_on_site,
                            qty_current_stock=qty_current_stock,
                            notes=notes,
                            order_status=order_status,
                            consumable_or_essential=type_col
                        )
                        # Calculate LRV coverage
                        new_part.calculate_lrv_coverage()
                        
                        db.session.add(new_part)
                        imported_count += 1
                        
                except Exception as e:
                    print(f"Error processing row {index}: {e}")
                    print(f"Row data: {row.to_dict()}")
                    error_count += 1
                    continue

            db.session.commit()
            print(f"\nImport completed!")
            print(f"New parts imported: {imported_count}")
            print(f"Existing parts updated: {updated_count}")
            print(f"Errors encountered: {error_count}")
            print(f"Total parts in database: {MainBOMStorage.query.count()}")

            return True

        except Exception as e:
            print(f"Error importing CSV file: {e}")
            db.session.rollback()
            return False

def clear_existing_data():
    """Clear all existing BOM data - use with caution!"""
    app = create_app()
    with app.app_context():
        try:
            count = MainBOMStorage.query.count()
            MainBOMStorage.query.delete()
            db.session.commit()
            print(f"Cleared {count} existing records from database.")
            return True
        except Exception as e:
            print(f"Error clearing data: {e}")
            db.session.rollback()
            return False

if __name__ == '__main__':
    import sys
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--clear':
            print("Clearing existing data...")
            clear_existing_data()
        elif sys.argv[1] == '--fresh':
            print("Clearing existing data and importing fresh...")
            clear_existing_data()
            import_bom_from_csv()
        else:
            # Custom CSV file path
            csv_file = sys.argv[1]
            import_bom_from_csv(csv_file)
    else:
        # Default: import from bom_seed.csv
        print("Importing from bom_seed.csv...")
        import_bom_from_csv()
