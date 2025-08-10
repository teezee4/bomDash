from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from app.models import MainBOMStorage, DeliveryLog, InventoryDivision, StockAdjustment
from app.forms import DeliveryForm, StockAdjustmentForm, BOMItemForm, SearchForm, TrainCalculatorForm
from sqlalchemy import or_
import json

main = Blueprint('main', __name__)

@main.route('/')
def dashboard():
    """Main dashboard showing key metrics and alerts"""
    # Key metrics
    total_parts = MainBOMStorage.query.count()
    
    # Use the property method for lrv_coverage calculation
    low_stock_parts = MainBOMStorage.query.filter(
        MainBOMStorage.coverage_lrvs < 10
    ).count()
    
    out_of_stock_parts = MainBOMStorage.query.filter(
        MainBOMStorage.quantity_currently_in_stock_at_store <= 0
    ).count()
    
    # Recent deliveries (last 10)
    recent_deliveries = DeliveryLog.query.order_by(DeliveryLog.created_at.desc()).limit(10).all()
    
    # Low stock items for alerts
    low_stock_items = MainBOMStorage.query.filter(
        MainBOMStorage.coverage_lrvs < 10
    ).limit(15).all()
    
    # Calculate total stock items
    total_stock_items = db.session.query(
        db.func.sum(MainBOMStorage.quantity_currently_in_stock_at_store)
    ).scalar() or 0
    
    return render_template('dashboard.html', 
                         total_parts=total_parts,
                         low_stock_parts=low_stock_parts,
                         out_of_stock_parts=out_of_stock_parts,
                         total_stock_items=int(total_stock_items),
                         recent_deliveries=recent_deliveries,
                         low_stock_items=low_stock_items)

@main.route('/parts_list')
def parts_list():
    """Parts listing with search and filter functionality"""
    form = SearchForm()
    
    # Base query
    query = MainBOMStorage.query
    
    # Handle search
    search_term = request.args.get('search_term', '').strip()
    if search_term:
        query = query.filter(or_(
            MainBOMStorage.part_number.contains(search_term),
            MainBOMStorage.part_name.contains(search_term),
            MainBOMStorage.description.contains(search_term),
            MainBOMStorage.supplier.contains(search_term)
        ))
    
    # Handle filters
    supplier_filter = request.args.get('supplier_filter', '')
    if supplier_filter:
        query = query.filter(MainBOMStorage.supplier == supplier_filter)
    
    component_filter = request.args.get('component_filter', '')
    if component_filter:
        query = query.filter(MainBOMStorage.description == component_filter)
    
    low_stock_only = request.args.get('low_stock_only', '')
    if low_stock_only == 'low':
        query = query.filter(MainBOMStorage.coverage_lrvs < 10)
    elif low_stock_only == 'out':
        query = query.filter(MainBOMStorage.quantity_currently_in_stock_at_store <= 0)
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    parts = query.paginate(page=page, per_page=50, error_out=False)
    
    # Get unique suppliers and components for filter dropdowns
    suppliers = db.session.query(MainBOMStorage.supplier.distinct()).filter(
        MainBOMStorage.supplier.isnot(None)
    ).all()
    components = db.session.query(MainBOMStorage.description.distinct()).filter(
        MainBOMStorage.description.isnot(None)
    ).all()
    
    form.supplier_filter.choices = [('', 'All Suppliers')] + [(s[0], s[0]) for s in suppliers]
    form.component_filter.choices = [('', 'All Components')] + [(c[0], c[0]) for c in components]
    
    return render_template('parts_list.html', 
                         parts=parts,
                         form=form,
                         search_term=search_term,
                         supplier_filter=supplier_filter,
                         component_filter=component_filter,
                         low_stock_only=low_stock_only)

@main.route('/delivery_log', methods=['GET', 'POST'])
def delivery_log():
    """Log new deliveries and view delivery history"""
    form = DeliveryForm()
    
    if form.validate_on_submit():
        # Create new delivery log entry
        delivery = DeliveryLog(
            part_number=form.part_number.data,
            part_name=form.part_name.data,
            supplier=form.supplier.data,
            quantity_received=form.quantity_received.data,
            date_received=form.date_received.data,
            date_expected=form.date_expected.data,
            notes=form.notes.data
        )
        
        # Try to find matching BOM item and update stock
        bom_item = MainBOMStorage.query.filter_by(part_number=form.part_number.data).first()
        if bom_item:
            delivery.bom_item = bom_item
            # Update the actual database field
            current_stock = bom_item.quantity_currently_in_stock_at_store or 0.0
            bom_item.quantity_currently_in_stock_at_store = current_stock + form.quantity_received.data
            bom_item.calculate_lrv_coverage()
        
        db.session.add(delivery)
        db.session.commit()
        
        flash(f'Delivery logged successfully! Added {form.quantity_received.data} units of {form.part_number.data}', 'success')
        return redirect(url_for('main.delivery_log'))
    
    # Get recent deliveries
    recent_deliveries = DeliveryLog.query.order_by(DeliveryLog.created_at.desc()).limit(20).all()
    
    return render_template('delivery_form.html', form=form, recent_deliveries=recent_deliveries)

@main.route('/stock_adjustment', methods=['GET', 'POST'])
def stock_adjustment():
    """Manual stock adjustments"""
    form = StockAdjustmentForm()
    
    if form.validate_on_submit():
        # Find the BOM item
        bom_item = MainBOMStorage.query.filter_by(part_number=form.part_number.data).first()
        if not bom_item:
            flash(f'Part number {form.part_number.data} not found in BOM!', 'error')
            return render_template('stock_adjust.html', form=form)
        
        # Create adjustment record
        adjustment = StockAdjustment(
            part_number=form.part_number.data,
            adjustment_type=form.adjustment_type.data,
            quantity_adjusted=form.quantity_adjusted.data,
            reason=form.reason.data,
            notes=form.notes.data,
            user_name=form.user_name.data,
            bom_item=bom_item
        )
        
        # Apply the adjustment to the correct field
        current_stock = bom_item.quantity_currently_in_stock_at_store or 0.0
        if form.adjustment_type.data == 'increase':
            bom_item.quantity_currently_in_stock_at_store = current_stock + form.quantity_adjusted.data
        else:
            bom_item.quantity_currently_in_stock_at_store = max(0.0, current_stock - form.quantity_adjusted.data)
        
        # Recalculate LRV coverage
        bom_item.calculate_lrv_coverage()
        
        db.session.add(adjustment)
        db.session.commit()
        
        flash(f'Stock adjustment applied to {form.part_number.data}', 'success')
        return redirect(url_for('main.stock_adjustment'))
    
    return render_template('stock_adjust.html', form=form)

@main.route('/train_calculator', methods=['GET', 'POST'])
def train_calculator():
    """Calculate parts needed for specific number of trains"""
    form = TrainCalculatorForm()
    results = []
    
    if form.validate_on_submit():
        num_trains = form.num_trains.data
        part_number = form.part_number.data.strip() if form.part_number.data else None
        
        if part_number:
            # Calculate for specific part
            bom_item = MainBOMStorage.query.filter_by(part_number=part_number).first()
            if bom_item:
                needed = bom_item.calculate_needed_for_trains(num_trains)
                shortage = max(0, needed - bom_item.qty_current_stock)
                results = [{
                    'part_number': bom_item.part_number,
                    'part_name': bom_item.part_name,
                    'qty_per_lrv': bom_item.qty_per_lrv,
                    'needed': needed,
                    'current_stock': bom_item.qty_current_stock,
                    'shortage': shortage
                }]
            else:
                flash(f'Part number {part_number} not found!', 'error')
        else:
            # Calculate for all parts
            all_parts = MainBOMStorage.query.all()
            for bom_item in all_parts:
                needed = bom_item.calculate_needed_for_trains(num_trains)
                shortage = max(0, needed - bom_item.qty_current_stock)
                results.append({
                    'part_number': bom_item.part_number,
                    'part_name': bom_item.part_name,
                    'qty_per_lrv': bom_item.qty_per_lrv,
                    'needed': needed,
                    'current_stock': bom_item.qty_current_stock,
                    'shortage': shortage
                })
            
            # Sort by shortage (highest first)
            results.sort(key=lambda x: x['shortage'], reverse=True)
    
    return render_template('dashboard.html', form=form, results=results, show_calculator=True)

@main.route('/api/part_autocomplete')
def part_autocomplete():
    """API endpoint for part number autocomplete"""
    q = request.args.get('q', '')
    if len(q) < 2:
        return jsonify([])
    
    parts = MainBOMStorage.query.filter(
        or_(MainBOMStorage.part_number.contains(q), MainBOMStorage.part_name.contains(q))
    ).limit(10).all()
    
    results = [{'part_number': p.part_number, 'part_name': p.part_name or ''} for p in parts]
    return jsonify(results)