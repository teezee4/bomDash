from app import db
from datetime import datetime
from sqlalchemy import func, Index

class MainBOMStorage(db.Model):
    """Main BOM storage table - core inventory data optimized for PostgreSQL"""
    __tablename__ = 'main_bom_storage'
    
    id = db.Column(db.Integer, primary_key=True)
    part_number = db.Column(db.String(100), nullable=False, unique=True, index=True)
    part_name = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text)
    supplier = db.Column(db.String(100), nullable=False, index=True)
    component = db.Column(db.String(100), index=True)  # Which part of installation
    
    # Quantity fields
    qty_per_lrv = db.Column(db.Float, nullable=False, default=0.0)
    total_needed_233_lrv = db.Column(db.Float, nullable=False, default=0.0)
    qty_on_site = db.Column(db.Float, nullable=False, default=0.0)
    qty_shipped_out = db.Column(db.Float, nullable=False, default=0.0)
    qty_current_stock = db.Column(db.Float, nullable=False, default=0.0, index=True)
    qty_ordered = db.Column(db.Float, nullable=False, default=0.0)
    back_order_qty = db.Column(db.Float, nullable=False, default=0.0)
    
    # Classification
    consumable_or_essential = db.Column(db.String(20), default='Essential', index=True)
    order_status = db.Column(db.String(50))
    
    # Notes and calculations
    notes = db.Column(db.Text)
    lrv_coverage = db.Column(db.Float, nullable=False, default=0.0, index=True)  # How many LRVs current stock covers
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<BOMItem {self.part_number}: {self.part_name}>'
    
    def calculate_lrv_coverage(self):
        """Calculate how many LRVs the current stock will cover"""
        if self.qty_per_lrv > 0:
            self.lrv_coverage = self.qty_current_stock / self.qty_per_lrv
        else:
            self.lrv_coverage = 0.0
        return self.lrv_coverage
    
    def calculate_needed_for_trains(self, num_trains):
        """Calculate quantity needed for specific number of trains"""
        return self.qty_per_lrv * num_trains
    
    def is_low_stock(self, threshold_trains=10):
        """Check if stock is low (less than threshold trains worth)"""
        return self.lrv_coverage < threshold_trains
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'part_number': self.part_number,
            'part_name': self.part_name,
            'description': self.description,
            'supplier': self.supplier,
            'component': self.component,
            'qty_per_lrv': self.qty_per_lrv,
            'qty_current_stock': self.qty_current_stock,
            'lrv_coverage': self.lrv_coverage,
            'consumable_or_essential': self.consumable_or_essential,
            'notes': self.notes
        }

class DeliveryLog(db.Model):
    """Material delivery log - tracks all incoming deliveries"""
    __tablename__ = 'delivery_log'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Delivery information
    date_received = db.Column(db.Date, nullable=False, default=datetime.utcnow().date, index=True)
    part_number = db.Column(db.String(100), nullable=False, index=True)
    part_name = db.Column(db.String(200), nullable=False)
    supplier = db.Column(db.String(100), nullable=False, index=True)
    quantity_received = db.Column(db.Float, nullable=False)
    
    # Future delivery tracking
    date_expected = db.Column(db.Date, index=True)  # For expected future deliveries
    
    # Reference to main BOM
    bom_item_id = db.Column(db.Integer, db.ForeignKey('main_bom_storage.id', ondelete='SET NULL'))
    bom_item = db.relationship('MainBOMStorage', backref='deliveries')
    
    # Notes
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<Delivery {self.part_number}: {self.quantity_received} on {self.date_received}>'

class InventoryDivision(db.Model):
    """Track inventory by division (Division 21, Division 16, etc.)"""
    __tablename__ = 'inventory_division'
    
    id = db.Column(db.Integer, primary_key=True)
    division_name = db.Column(db.String(50), nullable=False, unique=True, index=True)  # e.g., "Division 21"
    location = db.Column(db.String(100), nullable=True, index=True)  # e.g., "Site A"
    kits_sent_to_site = db.Column(db.Integer, nullable=False, default=0)
    trains_completed = db.Column(db.Integer, nullable=False, default=0)
    full_installation_kits = db.Column(db.Integer, nullable=False, default=0)
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    parts = db.relationship('DivisionInventory', back_populates='division', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<InventoryDivision {self.division_name}: {self.trains_completed} trains>'


class DivisionInventory(db.Model):
    """Detailed part tracking for each division"""
    __tablename__ = 'division_inventory'

    id = db.Column(db.Integer, primary_key=True)

    # Foreign Keys
    division_id = db.Column(db.Integer, db.ForeignKey('inventory_division.id'), nullable=False)
    part_id = db.Column(db.Integer, db.ForeignKey('main_bom_storage.id'), nullable=False)

    # Quantity tracking
    qty_sent_to_site = db.Column(db.Float, nullable=False, default=0.0)
    qty_used_on_site = db.Column(db.Float, nullable=False, default=0.0)

    # Notes
    notes = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    division = db.relationship('InventoryDivision', back_populates='parts')
    part = db.relationship('MainBOMStorage')

    @property
    def qty_remaining(self):
        """Calculated property for remaining quantity"""
        return self.qty_sent_to_site - self.qty_used_on_site

    def __repr__(self):
        return f'<DivisionInventory part={self.part.part_number} division={self.division.division_name}>'


class DefectedPart(db.Model):
    """Log for defected parts"""
    __tablename__ = 'defected_parts'

    id = db.Column(db.Integer, primary_key=True)
    part_number = db.Column(db.String(100), nullable=False, index=True)
    part_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Float, nullable=False)

    # Foreign Key to Division
    division_id = db.Column(db.Integer, db.ForeignKey('inventory_division.id'), nullable=True)
    division = db.relationship('InventoryDivision', backref='defected_parts')

    date_reported = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    notes = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<DefectedPart {self.part_number}: {self.quantity}>'

class ToolsDeliveryLog(db.Model):
    """Tools delivery log - separate from materials"""
    __tablename__ = 'tools_delivery_log'
    
    id = db.Column(db.Integer, primary_key=True)
    date_received = db.Column(db.Date, nullable=False, default=datetime.utcnow().date, index=True)
    part_number = db.Column(db.String(100), nullable=False, index=True)
    part_name = db.Column(db.String(200), nullable=False)
    quantity_received = db.Column(db.Float, nullable=False)
    supplier = db.Column(db.String(100), nullable=False, index=True)
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ToolDelivery {self.part_number}: {self.quantity_received}>'

class StockAdjustment(db.Model):
    """Track manual stock adjustments with reasons"""
    __tablename__ = 'stock_adjustments'
    
    id = db.Column(db.Integer, primary_key=True)
    part_number = db.Column(db.String(100), nullable=False, index=True)
    adjustment_type = db.Column(db.String(20), nullable=False, index=True)  # 'increase' or 'decrease'
    quantity_adjusted = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(200), nullable=False, index=True)
    notes = db.Column(db.Text)
    
    # Reference to main BOM
    bom_item_id = db.Column(db.Integer, db.ForeignKey('main_bom_storage.id', ondelete='SET NULL'))
    bom_item = db.relationship('MainBOMStorage', backref='adjustments')
    
    # User tracking
    user_name = db.Column(db.String(100), index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<StockAdjustment {self.part_number}: {self.adjustment_type} {self.quantity_adjusted}>'

# Create composite indexes for better query performance
Index('idx_bom_stock_coverage', MainBOMStorage.qty_current_stock, MainBOMStorage.lrv_coverage)
Index('idx_bom_supplier_component', MainBOMStorage.supplier, MainBOMStorage.component)
Index('idx_delivery_date_part', DeliveryLog.date_received, DeliveryLog.part_number)
Index('idx_adjustment_date_type', StockAdjustment.created_at, StockAdjustment.adjustment_type)