#!/usr/bin/env python3
"""
Simple Material Delivery Log Import Script
Imports delivery log data from Excel files into the existing SQLite database
Works with the original Phase 1 DeliveryLog model
"""
import pandas as pd
import os
from datetime import datetime
from app import create_app, db
from app.models import MainBOMStorage, DeliveryLog

def import_delivery_log_from_excel(excel_file_path, sheet_name='Sheet1'):
    """Import delivery log data from Excel file"""
    app = create_app()
    
    with app.app_context():
        try:
            print(f"Reading Excel file: {excel_file_path}, Sheet: {sheet_name}")
            
            # Read the Excel file
            df = pd.read_excel(excel_file_path, sheet_name=sheet_name)
            print(f"Found {len(df)} rows in Excel sheet")
            
            # Expected column mapping (adjust based on your Excel structure)
            column_mapping = {
                'Date': 'date_received',
                'Part Number': 'part_number', 
                'Description': 'part_name',
                'Qty': 'quantity_received',
                'Vendor': 'supplier'
            }
            
            # Rename columns to match our database model
            df_renamed = df.rename(columns=column_mapping)
            
            imported_count = 0
            updated_stock_count = 0
            error_count = 0
            
            for index, row in df_renamed.iterrows():
                try:
                    # Skip rows without essential data
                    if (pd.isna(row.get('part_number')) or 
                        pd.isna(row.get('quantity_received')) or 
                        pd.isna(row.get('date_received'))):
                        continue
                    
                    # Clean and validate data
                    part_number = str(row['part_number']).strip()
                    if not part_number or part_number.lower() in ['nan', 'none', '']:
                        continue
                        
                    # Handle quantity - make sure it's numeric
                    try:
                        quantity_str = str(row['quantity_received']).strip()
                        # Handle cases like "12758.928 ft" - extract just the number
                        if ' ' in quantity_str:
                            quantity_str = quantity_str.split(' ')[0]
                        quantity = float(quantity_str)
                        if quantity <= 0:
                            print(f"Skipping row {index}: Invalid quantity {quantity}")
                            continue
                    except (ValueError, TypeError):
                        print(f"Skipping row {index}: Could not convert quantity '{row.get('quantity_received')}' to number")
                        continue
                    
                    # Handle date
                    date_received = None
                    if pd.notna(row.get('date_received')):
                        if isinstance(row['date_received'], str):
                            # Try to parse different date formats
                            try:
                                # Try format like "13-May" - add year 2024
                                date_str = row['date_received'].strip()
                                if len(date_str.split('-')) == 2:
                                    # Add current year if not specified
                                    date_str = f"{date_str}-2024"  # Assuming 2024
                                date_received = pd.to_datetime(date_str).date()
                            except:
                                try:
                                    date_received = pd.to_datetime(row['date_received']).date()
                                except:
                                    print(f"Warning: Could not parse date '{row['date_received']}' for row {index}, using today's date")
                                    date_received = datetime.now().date()
                        else:
                            try:
                                date_received = pd.to_datetime(row['date_received']).date()
                            except:
                                date_received = datetime.now().date()
                    else:
                        date_received = datetime.now().date()
                    
                    # Clean other fields
                    part_name = str(row.get('part_name', part_number)).strip() if pd.notna(row.get('part_name')) else part_number
                    supplier = str(row.get('supplier', '')).strip() if pd.notna(row.get('supplier')) else 'Unknown'
                    
                    # Use simpler duplicate check - just check part number and date
                    existing_delivery = DeliveryLog.query.filter_by(
                        part_number=part_number,
                        date_received=date_received
                    ).first()
                    
                    if existing_delivery:
                        print(f"Skipping potential duplicate delivery: {part_number} on {date_received}")
                        continue
                    
                    # Create new delivery log entry (using only the fields that exist in Phase 1 model)
                    delivery = DeliveryLog(
                        part_number=part_number,
                        part_name=part_name,
                        supplier=supplier,
                        quantity_received=quantity,
                        date_received=date_received,
                        notes=f"Imported from Excel on {datetime.now().strftime('%Y-%m-%d')}"
                    )
                    
                    # Try to find matching BOM item and update stock
                    bom_item = MainBOMStorage.query.filter_by(part_number=part_number).first()
                    if bom_item:
                        delivery.bom_item = bom_item
                        # Update the BOM stock
                        bom_item.qty_current_stock += quantity
                        bom_item.calculate_lrv_coverage()
                        updated_stock_count += 1
                        print(f"Updated stock for {part_number}: +{quantity} (new total: {bom_item.qty_current_stock})")
                    else:
                        print(f"Warning: Part {part_number} not found in main BOM, delivery logged but stock not updated")
                    
                    db.session.add(delivery)
                    imported_count += 1
                    
                    # Commit every 10 records to avoid issues
                    if imported_count % 10 == 0:
                        db.session.commit()
                        print(f"Committed {imported_count} records so far...")
                
                except Exception as e:
                    print(f"Error processing row {index}: {e}")
                    error_count += 1
                    continue
            
            # Final commit
            db.session.commit()
            
            print(f"\nDelivery log import completed!")
            print(f"New deliveries imported: {imported_count}")
            print(f"BOM items with updated stock: {updated_stock_count}")
            print(f"Errors encountered: {error_count}")
            print(f"Total deliveries in database: {DeliveryLog.query.count()}")
            
            return True
            
        except Exception as e:
            print(f"Error importing Excel file: {e}")
            db.session.rollback()
            return False

def create_sample_delivery_data():
    """Create sample delivery data for testing"""
    app = create_app()
    
    with app.app_context():
        print("Creating sample delivery data...")
        
        sample_deliveries = [
            {
                'date_received': datetime(2024, 5, 14).date(),
                'part_number': '10006853',
                'part_name': 'Violet antenna with cables',
                'quantity_received': 5.0,
                'supplier': 'WTX-Test Rack'
            },
            {
                'date_received': datetime(2024, 5, 15).date(),
                'part_number': 'A6X30251563',
                'part_name': 'Wifi Mounting Brackets',
                'quantity_received': 10.0,
                'supplier': 'Peacock'
            },
            {
                'date_received': datetime(2024, 5, 20).date(),
                'part_number': '100007184',
                'part_name': 'WTX - Cable assembly Ethernet cordset',
                'quantity_received': 62.0,
                'supplier': 'Wi-Tronix'
            }
        ]
        
        imported_count = 0
        for delivery_data in sample_deliveries:
            # Check if delivery already exists
            existing = DeliveryLog.query.filter_by(
                part_number=delivery_data['part_number'],
                date_received=delivery_data['date_received']
            ).first()
            
            if not existing:
                delivery = DeliveryLog(
                    part_number=delivery_data['part_number'],
                    part_name=delivery_data['part_name'],
                    supplier=delivery_data['supplier'],
                    quantity_received=delivery_data['quantity_received'],
                    date_received=delivery_data['date_received'],
                    notes='Sample data'
                )
                
                # Try to update BOM stock
                bom_item = MainBOMStorage.query.filter_by(part_number=delivery_data['part_number']).first()
                if bom_item:
                    delivery.bom_item = bom_item
                    bom_item.qty_current_stock += delivery_data['quantity_received']
                    bom_item.calculate_lrv_coverage()
                
                db.session.add(delivery)
                imported_count += 1
        
        if imported_count > 0:
            db.session.commit()
            print(f"Created {imported_count} sample deliveries")
        else:
            print("Sample delivery data already exists")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        excel_file = sys.argv[1]
        sheet_name = sys.argv[2] if len(sys.argv) > 2 else 'Sheet1'
        
        if os.path.exists(excel_file):
            import_delivery_log_from_excel(excel_file, sheet_name)
        else:
            print(f"Excel file not found: {excel_file}")
            print("Usage: python import_delivery_log_simple.py <excel_file> [sheet_name]")
    else:
        print("Creating sample delivery data for testing...")
        create_sample_delivery_data()
        print("\nTo import from Excel file, run:")
        print("python import_delivery_log_simple.py /path/to/your/delivery_log.xlsx [sheet_name]")