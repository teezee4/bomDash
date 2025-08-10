from app import db
from datetime import datetime
from sqlalchemy import func

class MainBOMStorage(db.Model):
    """Main BOM storage table - core inventory data"""
    __tablename__ = 'main_bom_storage'
    
    id = db.Column(db.Integer, primary_key=True)
    part_number = db.Column(db.String(128), nullable=False, unique=True, index=True)
    part_name = db.Column(db.Text)
    supplier = db.Column(db.Text)
    description = db.Column(db.Text)
    type = db.Column(db.Text)
    
    # Quantity fields - matching your Excel import script exactly
    qty_needed_per_lrv = db.Column(db.Float)
    total_needed_for_233_lrv = db.Column(db.Float)
    total_quantity_received_by_store = db.Column(db.Float)
    quantity_shipped_out_by_store = db.Column(db.Float)
    quantity_currently_in_stock_at_store = db.Column(db.Float)
    quantity_back_ordered = db.Column(db.Float)
    back_order_delivery_info = db.Column(db.Text)
    notes = db.Column(db.Text)
    
    # Additional tracking fields
    stock_for_number_of_trains = db.Column(db.Float)
    no_of_trains_next_delivery = db.Column(db.Float)
    qty_required_for_more_trains = db.Column(db.Float)
    
    # Calculated fields
    coverage_lrvs = db.Column(db.Integer)
    qty_short_for_233 = db.Column(db.Float)
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<BOMItem {self.part_number}: {self.part_name}>'
    
    # Properties for backward compatibility with existing code
    @property
    def qty_per_lrv(self):
        """Alias for qty_needed_per_lrv"""
        return self.qty_needed_per_lrv or 0.0
    
    @property
    def qty_current_stock(self):
        """Alias for quantity_currently_in_stock_at_store"""
        return self.quantity_currently_in_stock_at_store or 0.0
    
    @property
    def qty_on_site(self):
        """Alias for total_quantity_received_by_store"""
        return self.total_quantity_received_by_store or 0.0
    
    @property
    def qty_shipped_out(self):
        """Alias for quantity_shipped_out_by_store"""
        return self.quantity_shipped_out_by_store or 0.0
    
    @property
    def back_order_qty(self):
        """Alias for quantity_back_ordered"""
        return self.quantity_back_ordered or 0.0
    
    @property
    def lrv_coverage(self):
        """Calculate LRV coverage from current stock"""
        if self.qty_per_lrv and self.qty_per_lrv > 0:
            return (self.qty_current_stock or 0.0) / self.qty_per_lrv
        return 0.0
    
    @property
    def consumable_or_essential(self):
        """Map Type field to consumable_or_essential"""
        return self.type or 'Long Lead'
    
    @property
    def component(self):
        """Use description as component for compatibility"""
        return self.description
    
    def calculate_lrv_coverage(self):
        """Calculate how many LRVs the current stock will cover"""
        if self.qty_per_lrv and self.qty_per_lrv > 0:
            coverage = (self.qty_current_stock or 0.0) / self.qty_per_lrv
            # Update the calculated field in database
            self.coverage_lrvs = int(coverage)
            return coverage
        else:
            self.coverage_lrvs = 0
            return 0.0
    
    def calculate_needed_for_trains(self, num_trains):
        """Calculate quantity needed for specific number of trains"""
        return (self.qty_per_lrv or 0.0) * num_trains
    
    def is_low_stock(self, threshold_trains=10):
        """Check if stock is low (less than threshold trains worth)"""
        return self.lrv_coverage < threshold_trains

class DeliveryLog(db.Model):
    """Material delivery log - tracks all incoming deliveries"""
    __tablename__ = 'delivery_log'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Delivery information - matching your import script
    part_number = db.Column(db.String(128), nullable=False, index=True)
    part_name = db.Column(db.Text)
    supplier = db.Column(db.Text)
    quantity_received = db.Column(db.Float)
    date_received = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
    # Future delivery tracking
    date_expected = db.Column(db.Date)  # For expected future deliveries
    
    # Reference to main BOM (optional since we use part_number)
    bom_item_id = db.Column(db.Integer, db.ForeignKey('main_bom_storage.id'))
    bom_item = db.relationship('MainBOMStorage', backref='deliveries')
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Delivery {self.part_number}: {self.quantity_received} on {self.date_received}>'

class InventoryDivision(db.Model):
    """Track inventory by division (Division 21, Division 16, etc.)"""
    __tablename__ = 'inventory_division'
    
    id = db.Column(db.Integer, primary_key=True)
    division_name = db.Column(db.String(50), nullable=False)  # e.g., "Division 21", "Division 16"
    trains_completed = db.Column(db.Integer, nullable=False, default=0)
    full_installation_kits = db.Column(db.Integer, nullable=False, default=0)
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<InventoryDivision {self.division_name}: {self.trains_completed} trains>'

class ToolsDeliveryLog(db.Model):
    """Tools delivery log - separate from materials"""
    __tablename__ = 'tools_delivery_log'
    
    id = db.Column(db.Integer, primary_key=True)
    date_received = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    part_number = db.Column(db.String(100), nullable=False)
    part_name = db.Column(db.String(200), nullable=False)
    quantity_received = db.Column(db.Float, nullable=False)
    supplier = db.Column(db.String(100))
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ToolDelivery {self.part_number}: {self.quantity_received}>'

class StockAdjustment(db.Model):
    """Track manual stock adjustments with reasons"""
    __tablename__ = 'stock_adjustments'
    
    id = db.Column(db.Integer, primary_key=True)
    part_number = db.Column(db.String(100), nullable=False)
    adjustment_type = db.Column(db.String(20), nullable=False)  # 'increase' or 'decrease'
    quantity_adjusted = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(200), nullable=False)
    notes = db.Column(db.Text)
    
    # Reference to main BOM
    bom_item_id = db.Column(db.Integer, db.ForeignKey('main_bom_storage.id'))
    bom_item = db.relationship('MainBOMStorage', backref='adjustments')
    
    # User tracking (for future implementation)
    user_name = db.Column(db.String(100))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<StockAdjustment {self.part_number}: {self.adjustment_type} {self.quantity_adjusted}>'