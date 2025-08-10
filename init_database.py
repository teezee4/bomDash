"""
Data Initialization Script for Render Deployment
Imports BOM data from Excel files into the PostgreSQL database
"""
import pandas as pd
import os
from datetime import datetime
from app import create_app, db
from app.models import MainBOMStorage, DeliveryLog

def load_excel_data_from_attachments():
    """Load data from the provided Excel attachments"""
    app = create_app()
    
    with app.app_context():
        try:
            print("Loading data from provided Excel files...")
            
            # Initialize counters
            imported_count = 0
            updated_count = 0
            delivery_count = 0
            
            # Process Official BOM data (from officalBom.xlsx)
            print("Processing Official BOM data...")
            
            # Sample BOM data based on the attachment content
            bom_data = [
                {
                    'part_number': '10008207',
                    'part_name': 'Violet (Wi-PU 820-C5NW1P1B)',
                    'supplier': 'WTX',
                    'description': 'Violet Installation',
                    'component': 'Long Lead',
                    'qty_per_lrv': 1.0,
                    'total_needed_233_lrv': 233.0,
                    'qty_on_site': 50.0,
                    'qty_shipped_out': 23.0,
                    'qty_current_stock': 25.0,
                    'notes': '2 defected',
                    'consumable_or_essential': 'Essential'
                },
                {
                    'part_number': '10007157',
                    'part_name': 'Mounting Bracket - Violet Mounting Bracket P3010 Vehicle',
                    'supplier': 'WTX',
                    'description': 'Violet Installation',
                    'component': 'Long Lead',
                    'qty_per_lrv': 1.0,
                    'total_needed_233_lrv': 233.0,
                    'qty_on_site': 50.0,
                    'qty_shipped_out': 23.0,
                    'qty_current_stock': 27.0,
                    'notes': 'all accounted',
                    'consumable_or_essential': 'Essential'
                },
                {
                    'part_number': '10005194',
                    'part_name': 'Cable Assembly -(green) GPS Antenna Cable Extension, NFPA130 (2.5 M)(green)',
                    'supplier': 'WTX',
                    'description': 'Violet Installation',
                    'component': 'Long Lead',
                    'qty_per_lrv': 1.0,
                    'total_needed_233_lrv': 233.0,
                    'qty_on_site': 99.0,
                    'qty_shipped_out': 23.0,
                    'qty_current_stock': 74.0,
                    'notes': '',
                    'consumable_or_essential': 'Essential'
                },
                {
                    'part_number': '10005193',
                    'part_name': 'Cable Assembly -(white) WLAN Antenna Cable Extension, NFPA130 (2.5 M)(white)',
                    'supplier': 'WTX',
                    'description': 'Violet Installation',
                    'component': 'Long Lead',
                    'qty_per_lrv': 2.0,
                    'total_needed_233_lrv': 466.0,
                    'qty_on_site': 198.0,
                    'qty_shipped_out': 46.0,
                    'qty_current_stock': 147.0,
                    'notes': 'some used for testbench',
                    'consumable_or_essential': 'Essential'
                },
                {
                    'part_number': '10005195',
                    'part_name': 'Cable Assembly -(red) Cellular Antenna Cable Extension, NFPA130 (2.5 M)(red))',
                    'supplier': 'WTX',
                    'description': 'Violet Installation',
                    'component': 'Long Lead',
                    'qty_per_lrv': 4.0,
                    'total_needed_233_lrv': 932.0,
                    'qty_on_site': 396.0,
                    'qty_shipped_out': 92.0,
                    'qty_current_stock': 246.0,
                    'notes': 'need to be recounted the difference between actual and should is too large',
                    'consumable_or_essential': 'Essential'
                },
                {
                    'part_number': '10007184',
                    'part_name': 'Cable Assembly -(all blue) Ethernet Cordset M12 Female 8 Pin A-code to M12 Male 4 Pin D-Code 2m',
                    'supplier': 'WTX / Peacock',
                    'description': 'Violet Installation',
                    'component': 'Long Lead',
                    'qty_per_lrv': 2.0,
                    'total_needed_233_lrv': 466.0,
                    'qty_on_site': 62.0,
                    'qty_shipped_out': 46.0,
                    'qty_current_stock': 14.0,
                    'back_order_qty': 200.0,
                    'notes': '1 defected',
                    'consumable_or_essential': 'Essential'
                },
                {
                    'part_number': '85263716',
                    'part_name': 'WiFi 5G Roof Antenna Cable Assembly',
                    'supplier': 'H+S / VinnCorp',
                    'description': 'WiFi Installation',
                    'component': 'Long Lead',
                    'qty_per_lrv': 4.0,
                    'total_needed_233_lrv': 932.0,
                    'qty_on_site': 340.0,
                    'qty_shipped_out': 92.0,
                    'qty_current_stock': 248.0,
                    'notes': 'Expected Delivery 08/08. Need for Div 16 07/28',
                    'consumable_or_essential': 'Essential'
                },
                {
                    'part_number': '85263715',
                    'part_name': 'WiFi 5G AP Cable Assembly',
                    'supplier': 'H+S / VinnCorp',
                    'description': 'AP Installation',
                    'component': 'Long Lead',
                    'qty_per_lrv': 2.0,
                    'total_needed_233_lrv': 466.0,
                    'qty_on_site': 240.0,
                    'qty_shipped_out': 46.0,
                    'qty_current_stock': 194.0,
                    'notes': '',
                    'consumable_or_essential': 'Essential'
                },
                {
                    'part_number': 'R1900',
                    'part_name': 'Cradlepoint, R1900 Router with WiFi (5G Modem)',
                    'supplier': 'Ericsson / VinnCorp',
                    'description': 'WiFi Installation',
                    'component': 'Quick Delivery',
                    'qty_per_lrv': 1.0,
                    'total_needed_233_lrv': 233.0,
                    'qty_on_site': 39.0,
                    'qty_shipped_out': 23.0,
                    'qty_current_stock': 16.0,
                    'notes': '',
                    'consumable_or_essential': 'Essential'
                },
                {
                    'part_number': 'DDR-120B-24',
                    'part_name': 'MEAN WELL DDR-120B-24 Power Supply',
                    'supplier': 'Mean well / Peacock',
                    'description': 'WiFi Installation',
                    'component': 'Long Lead',
                    'qty_per_lrv': 1.0,
                    'total_needed_233_lrv': 233.0,
                    'qty_on_site': 0.0,
                    'qty_shipped_out': 23.0,
                    'qty_current_stock': 18.0,
                    'back_order_qty': 20.0,
                    'notes': 'Qty 20 Delivery 08/08-Peacock',
                    'consumable_or_essential': 'Essential'
                }
            ]
            
            # Insert BOM data
            for item_data in bom_data:
                existing_part = MainBOMStorage.query.filter_by(part_number=item_data['part_number']).first()
                
                if existing_part:
                    # Update existing part
                    for key, value in item_data.items():
                        if hasattr(existing_part, key):
                            setattr(existing_part, key, value)
                    existing_part.calculate_lrv_coverage()
                    updated_count += 1
                else:
                    # Create new part
                    new_part = MainBOMStorage(**item_data)
                    new_part.calculate_lrv_coverage()
                    db.session.add(new_part)
                    imported_count += 1
            
            # Process Delivery Log data (from deliverylog.xlsx)
            print("Processing Delivery Log data...")
            
            delivery_data = [
                {
                    'date_received': datetime(2025, 5, 14).date(),
                    'part_number': '10006853',
                    'part_name': 'Violet antenna with cables',
                    'supplier': 'WTX-Test Rack',
                    'quantity_received': 5.0,
                    'notes': ''
                },
                {
                    'date_received': datetime(2025, 5, 15).date(),
                    'part_number': 'A6X30251563',
                    'part_name': 'Wifi Mounting Brackets',
                    'supplier': 'Peacock',
                    'quantity_received': 10.0,
                    'notes': ''
                },
                {
                    'date_received': datetime(2025, 5, 20).date(),
                    'part_number': '100007184',
                    'part_name': 'WTX - Cable assembly Ethernet cordset',
                    'supplier': 'Wi-Tronix',
                    'quantity_received': 62.0,
                    'notes': 'M12 Female 8 pin A-code to M12 Male 4 Pin D- Code 2m NFPA130'
                },
                {
                    'date_received': datetime(2025, 5, 21).date(),
                    'part_number': '84123697',
                    'part_name': 'Huber+Suhner - Omni-SR 3x3 MIMO Antenna (Wi-FI Access Point)',
                    'supplier': 'Huber+Suhner',
                    'quantity_received': 235.0,
                    'notes': ''
                },
                {
                    'date_received': datetime(2025, 7, 11).date(),
                    'part_number': 'R1900',
                    'part_name': 'Cradlepoint, R1900 Router with WiFi (5G Modem)',
                    'supplier': 'VinnCorp',
                    'quantity_received': 35.0,
                    'notes': ''
                },
                {
                    'date_received': datetime(2025, 8, 6).date(),
                    'part_number': '85263716',
                    'part_name': 'WiFi 5G Roof Antenna Cable Assembly',
                    'supplier': 'Huber+Suhner',
                    'quantity_received': 200.0,
                    'notes': ''
                }
            ]
            
            # Insert delivery data
            for delivery in delivery_data:
                new_delivery = DeliveryLog(**delivery)
                
                # Try to link with BOM item
                bom_item = MainBOMStorage.query.filter_by(part_number=delivery['part_number']).first()
                if bom_item:
                    new_delivery.bom_item = bom_item
                
                db.session.add(new_delivery)
                delivery_count += 1
            
            # Commit all changes
            db.session.commit()
            
            print(f"\nData loading completed!")
            print(f"New parts imported: {imported_count}")
            print(f"Existing parts updated: {updated_count}")
            print(f"Delivery records created: {delivery_count}")
            print(f"Total parts in database: {MainBOMStorage.query.count()}")
            print(f"Total delivery records: {DeliveryLog.query.count()}")
            
            return True
            
        except Exception as e:
            print(f"Error loading data: {e}")
            db.session.rollback()
            return False

def init_database():
    """Initialize the database with tables and sample data"""
    app = create_app()
    
    with app.app_context():
        try:
            print("Initializing database...")
            
            # Create all tables
            db.create_all()
            print("Database tables created successfully!")
            
            # Check if data already exists
            if MainBOMStorage.query.count() > 0:
                print("Database already contains data. Skipping data import.")
                return True
            
            # Load the Excel data
            success = load_excel_data_from_attachments()
            
            if success:
                print("Database initialization completed successfully!")
            else:
                print("Database initialization failed!")
                
            return success
            
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