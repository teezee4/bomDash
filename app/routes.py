from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app import db
from app.models import MainBOMStorage, DeliveryLog, InventoryDivision, StockAdjustment, DivisionInventory, DefectedPart
from app.forms import DeliveryForm, StockAdjustmentForm, BOMItemForm, SearchForm, TrainCalculatorForm, DivisionForm, KitsSentForm, TrainsCompletedForm, DefectedPartForm, LoginForm
from sqlalchemy import or_
from sqlalchemy.orm import aliased
import json
from datetime import datetime, date, timedelta
from functools import wraps

main = Blueprint('main', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@main.route('/login')
def login():
    return render_template('auth/landing.html')

@main.route('/login_viewer')
def login_viewer():
    session['role'] = 'viewer'
    flash('Viewer login successful!', 'success')
    return redirect(url_for('main.dashboard'))

@main.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    form = LoginForm()
    if form.validate_on_submit():
        if form.password.data == 'sga2':
            session['role'] = 'admin'
            flash('Admin login successful!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid password for admin login.', 'error')
            return redirect(url_for('main.admin_login'))
    return render_template('auth/admin_login.html', form=form)

@main.route('/logout')
def logout():
    session.pop('role', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.login'))

@main.before_request
def require_login():
    # Allow access to login pages and static files without being logged in
    allowed_endpoints = ['main.login', 'main.admin_login', 'main.login_viewer', 'static']
    if 'role' not in session and request.endpoint not in allowed_endpoints:
        return redirect(url_for('main.login'))

@main.route('/')
def dashboard():
    """Main dashboard showing key metrics and alerts"""
    # Key metrics
    total_parts = MainBOMStorage.query.count()
    
    # Fixed: Use correct field name lrv_coverage
    low_stock_parts = MainBOMStorage.query.filter(
        MainBOMStorage.lrv_coverage < 10
    ).count()
    
    # Fixed: Use correct field name qty_current_stock
    out_of_stock_parts = MainBOMStorage.query.filter(
        MainBOMStorage.qty_current_stock <= 0
    ).count()
    
    # Recent deliveries (last 10)
    recent_deliveries = DeliveryLog.query.order_by(DeliveryLog.created_at.desc()).limit(10).all()
    
    # Low stock items for alerts
    low_stock_items = MainBOMStorage.query.filter(
        MainBOMStorage.lrv_coverage < 10
    ).limit(15).all()
    
    # Calculate total stock items - Fixed: Use correct field name with safe arithmetic
    total_stock_items = db.session.query(
        db.func.sum(db.func.coalesce(MainBOMStorage.qty_current_stock, 0.0))
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
    """Display paginated list of parts with search and filtering"""
    try:
        form = SearchForm()
        
        # Get search and filter parameters
        search_term = request.args.get('search_term', '').strip()
        description_filter = request.args.get('description_filter', '').strip()
        type_filter = request.args.get('type_filter', '')
        low_stock_only = request.args.get('low_stock_only', '')
        page = request.args.get('page', 1, type=int)
        
        # Populate description filter choices
        descriptions = db.session.query(MainBOMStorage.part_name).distinct().order_by(MainBOMStorage.part_name).all()
        form.description_filter.choices = [('', 'All Descriptions')] + [(d[0], d[0]) for d in descriptions]
        # Start with base query
        query = MainBOMStorage.query
        
        # Apply search term filter (searches part number, name, and supplier)
        if search_term:
            query = query.filter(
                db.or_(
                    MainBOMStorage.part_number.ilike(f'%{search_term}%'),
                    MainBOMStorage.part_name.ilike(f'%{search_term}%'),
                    MainBOMStorage.component.ilike(f'%{search_term}%')
                )
            )
        
        # Apply description filter
        if description_filter:
            query = query.filter(MainBOMStorage.part_name == description_filter)
        
        # Apply type filter
        if type_filter:
            query = query.filter(MainBOMStorage.consumable_or_essential == type_filter)
        
        # Apply stock level filters with safe comparison
        if low_stock_only == 'low':
            query = query.filter(
                db.and_(
                    db.func.coalesce(MainBOMStorage.lrv_coverage, 0) < 10,
                    db.func.coalesce(MainBOMStorage.qty_current_stock, 0) > 0
                )
            )
        elif low_stock_only == 'out':
            query = query.filter(db.func.coalesce(MainBOMStorage.qty_current_stock, 0) <= 0)
        
        # Order by part number
        query = query.order_by(MainBOMStorage.part_number)
        
        # Paginate results
        per_page = 20  # Adjust as needed
        parts = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return render_template('parts_list.html',
                             parts=parts,
                             form=form,
                             search_term=search_term,
                             description_filter=description_filter,
                             type_filter=type_filter,
                             low_stock_only=low_stock_only)
        
    except Exception as e:
        current_app.logger.error(f'Error in parts_list: {str(e)}')
        flash('Error loading parts list. Please try again.', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/delivery_log', methods=['GET', 'POST'])
@admin_required
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
            # Fixed: Safe arithmetic for updating stock
            current_stock = bom_item.qty_current_stock or 0.0
            bom_item.qty_current_stock = current_stock + form.quantity_received.data
            bom_item.calculate_lrv_coverage()
        
        db.session.add(delivery)
        db.session.commit()
        
        flash(f'Delivery logged successfully! Added {form.quantity_received.data} units of {form.part_number.data}', 'success')
        return redirect(url_for('main.delivery_log'))
    
    # Get recent deliveries
    recent_deliveries = DeliveryLog.query.order_by(DeliveryLog.created_at.desc()).limit(20).all()
    
    return render_template('delivery_form.html', form=form, recent_deliveries=recent_deliveries)

@main.route('/stock_adjustment', methods=['GET', 'POST'])
@admin_required
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
        
        # Apply the adjustment to the correct field with safe arithmetic
        current_stock = bom_item.qty_current_stock or 0.0
        if form.adjustment_type.data == 'increase':
            bom_item.qty_current_stock = current_stock + form.quantity_adjusted.data
        else:
            bom_item.qty_current_stock = max(0.0, current_stock - form.quantity_adjusted.data)
        
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
                # Fixed: Safe arithmetic with None handling
                current_stock = bom_item.qty_current_stock or 0.0
                shortage = max(0, needed - current_stock)
                results = [{
                    'part_number': bom_item.part_number,
                    'part_name': bom_item.part_name,
                    'qty_per_lrv': bom_item.qty_per_lrv,
                    'needed': needed,
                    'current_stock': current_stock,
                    'shortage': shortage
                }]
            else:
                flash(f'Part number {part_number} not found!', 'error')
        else:
            # Calculate for all parts
            all_parts = MainBOMStorage.query.all()
            for bom_item in all_parts:
                needed = bom_item.calculate_needed_for_trains(num_trains)
                # Fixed: Safe arithmetic with None handling
                current_stock = bom_item.qty_current_stock or 0.0
                shortage = max(0, needed - current_stock)
                results.append({
                    'part_number': bom_item.part_number,
                    'part_name': bom_item.part_name,
                    'qty_per_lrv': bom_item.qty_per_lrv,
                    'needed': needed,
                    'current_stock': current_stock,
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

# Additional routes for enhanced functionality
@main.route('/edit_part/<int:part_id>', methods=['GET', 'POST'])
@admin_required
def edit_part(part_id):
    """Edit a specific BOM item"""
    bom_item = MainBOMStorage.query.get_or_404(part_id)
    form = BOMItemForm(obj=bom_item)
    
    if form.validate_on_submit():
        # Update all the fields
        form.populate_obj(bom_item)
        
        # Recalculate dependent fields with safe arithmetic
        qty_per_lrv = bom_item.qty_per_lrv or 0.0
        bom_item.total_needed_233_lrv = qty_per_lrv * 233
        bom_item.calculate_lrv_coverage()
        bom_item.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash(f'Part {bom_item.part_number} updated successfully!', 'success')
        return redirect(url_for('main.parts_list'))
    
    return render_template('edit_part.html', form=form, part=bom_item)

@main.route('/delete_part/<int:part_id>', methods=['POST'])
@admin_required
def delete_part(part_id):
    """Delete a specific BOM item and its related division inventory."""
    bom_item = MainBOMStorage.query.get_or_404(part_id)
    
    try:
        # Before deleting the part, delete its inventory records from all divisions
        DivisionInventory.query.filter_by(part_id=part_id).delete()

        # Now, delete the part itself
        db.session.delete(bom_item)
        db.session.commit()

        flash(f'Part {bom_item.part_number} and all its division inventory records have been permanently deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting part {bom_item.part_number}: {str(e)}', 'error')
        
    return redirect(url_for('main.parts_list'))

@main.route('/add_part', methods=['GET', 'POST'])
@admin_required
def add_part():
    """Add a new BOM item"""
    form = BOMItemForm()
    
    if form.validate_on_submit():
        # Check if part number already exists
        existing_part = MainBOMStorage.query.filter_by(part_number=form.part_number.data).first()
        if existing_part:
            flash(f'Part number {form.part_number.data} already exists!', 'error')
            return render_template('add_part.html', form=form)
        
        # Create new part with safe defaults
        qty_per_lrv = form.qty_per_lrv.data or 0.0
        new_part = MainBOMStorage(
            part_number=form.part_number.data,
            part_name=form.part_name.data,
            description=form.description.data,
            supplier=form.supplier.data,
            component=form.component.data,
            qty_per_lrv=qty_per_lrv,
            qty_on_site=form.qty_on_site.data or 0.0,
            qty_current_stock=form.qty_current_stock.data or 0.0,
            consumable_or_essential=form.consumable_or_essential.data,
            notes=form.notes.data,
            total_needed_233_lrv=qty_per_lrv * 233
        )
        
        # Calculate LRV coverage
        new_part.calculate_lrv_coverage()
        
        db.session.add(new_part)
        db.session.commit()
        
        flash(f'Part {new_part.part_number} added successfully!', 'success')
        return redirect(url_for('main.parts_list'))
    
    return render_template('add_part.html', form=form)

@main.route('/export_shipment', methods=['GET', 'POST'])
@admin_required
def export_shipment():
    """Export/ship parts to divisions and deduct from stock"""
    if request.method == 'POST':
        division_name = request.form.get('division_name')
        shipment_data = request.form.get('shipment_data')  # JSON data of parts and quantities
        
        try:
            shipments = json.loads(shipment_data)
            total_shipped = 0
            
            # Process each shipment item
            for item in shipments:
                part_number = item.get('part_number')
                quantity = float(item.get('quantity', 0))
                
                if quantity <= 0:
                    continue
                
                # Find the BOM item
                bom_item = MainBOMStorage.query.filter_by(part_number=part_number).first()
                if bom_item:
                    current_stock = bom_item.qty_current_stock or 0.0
                    if current_stock >= quantity:
                        # Deduct from current stock with safe arithmetic
                        bom_item.qty_current_stock = current_stock - quantity
                        bom_item.qty_shipped_out = (bom_item.qty_shipped_out or 0.0) + quantity
                        bom_item.calculate_lrv_coverage()
                        total_shipped += 1
                    else:
                        flash(f'Insufficient stock for part {part_number}', 'warning')
                else:
                    flash(f'Part {part_number} not found', 'warning')
            
            # Update division inventory if it exists
            division = InventoryDivision.query.filter_by(division_name=division_name).first()
            if not division:
                division = InventoryDivision(division_name=division_name)
                db.session.add(division)
            
            # You might want to add more specific tracking here
            division.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash(f'Shipment to {division_name} completed. {total_shipped} items shipped.', 'success')
            
        except (json.JSONDecodeError, ValueError) as e:
            flash('Invalid shipment data format', 'error')
        except Exception as e:
            flash(f'Error processing shipment: {str(e)}', 'error')
            db.session.rollback()
    
    # Get all parts for shipment form with safe stock check
    all_parts = MainBOMStorage.query.filter(
        db.func.coalesce(MainBOMStorage.qty_current_stock, 0) > 0
    ).all()
    divisions = InventoryDivision.query.all()
    
    return render_template('export_shipment.html', parts=all_parts, divisions=divisions)

@main.route('/inventory_report')
def inventory_report():
    """Generate comprehensive inventory report"""
    # Low stock items (less than 10 trains worth) with safe comparison
    low_stock_items = MainBOMStorage.query.filter(
        db.func.coalesce(MainBOMStorage.lrv_coverage, 0) < 10
    ).all()
    
    # Out of stock items with safe comparison
    out_of_stock_items = MainBOMStorage.query.filter(
        db.func.coalesce(MainBOMStorage.qty_current_stock, 0) <= 0
    ).all()
    
    # High value items (you might want to add a cost field for this)
    all_items = MainBOMStorage.query.all()
    
    # Recent deliveries (last 30 days)
    thirty_days_ago = date.today() - timedelta(days=30)
    recent_deliveries = DeliveryLog.query.filter(
        DeliveryLog.date_received >= thirty_days_ago
    ).order_by(DeliveryLog.date_received.desc()).all()
    
    # Stock adjustments (last 30 days)
    recent_adjustments = StockAdjustment.query.filter(
        StockAdjustment.created_at >= thirty_days_ago
    ).order_by(StockAdjustment.created_at.desc()).all()
    
    return render_template('inventory_report.html',
                         low_stock_items=low_stock_items,
                         out_of_stock_items=out_of_stock_items,
                         all_items=all_items,
                         recent_deliveries=recent_deliveries,
                         recent_adjustments=recent_adjustments)

@main.route('/api/dashboard_data')
def dashboard_data():
    """API endpoint for dashboard data (for AJAX updates)"""
    total_parts = MainBOMStorage.query.count()
    low_stock_parts = MainBOMStorage.query.filter(
        db.func.coalesce(MainBOMStorage.lrv_coverage, 0) < 10
    ).count()
    out_of_stock_parts = MainBOMStorage.query.filter(
        db.func.coalesce(MainBOMStorage.qty_current_stock, 0) <= 0
    ).count()
    total_stock_items = db.session.query(
        db.func.sum(db.func.coalesce(MainBOMStorage.qty_current_stock, 0))
    ).scalar() or 0
    
    return jsonify({
        'total_parts': total_parts,
        'low_stock_parts': low_stock_parts,
        'out_of_stock_parts': out_of_stock_parts,
        'total_stock_items': int(total_stock_items)
    })

@main.route('/split_parts_list')
def split_parts_list():
    """Display parts list split into Essential and Consumables"""
    try:
        essentials = MainBOMStorage.query.filter_by(consumable_or_essential='Essential').order_by(MainBOMStorage.part_number).all()
        consumables = MainBOMStorage.query.filter_by(consumable_or_essential='Consumables').order_by(MainBOMStorage.part_number).all()
        return render_template('split_parts_list.html', essentials=essentials, consumables=consumables)
    except Exception as e:
        current_app.logger.error(f'Error in split_parts_list: {str(e)}')
        flash('Error loading split parts list. Please try again.', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/dynamic_calculator')
def dynamic_calculator():
    """Display a dynamic parts calculator"""
    try:
        parts = MainBOMStorage.query.order_by(MainBOMStorage.part_number).all()
        return render_template('dynamic_calculator.html', parts=parts)
    except Exception as e:
        current_app.logger.error(f'Error in dynamic_calculator: {str(e)}')
        flash('Error loading dynamic calculator. Please try again.', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/divisions', methods=['GET', 'POST'])
@admin_required
def list_divisions():
    """List all inventory divisions and allow creating new ones"""
    form = DivisionForm()
    if form.validate_on_submit():
        # Check if division name already exists
        existing_division = InventoryDivision.query.filter_by(division_name=form.division_name.data).first()
        if existing_division:
            flash('A division with this name already exists.', 'error')
        else:
            new_division = InventoryDivision(
                division_name=form.division_name.data,
                location=form.location.data,
                notes=form.notes.data
            )
            db.session.add(new_division)
            db.session.commit()
            flash(f'Division "{new_division.division_name}" created successfully.', 'success')
            return redirect(url_for('main.list_divisions'))
    divisions = InventoryDivision.query.order_by(InventoryDivision.division_name).all()
    return render_template('divisions.html', divisions=divisions, form=form)

@main.route('/division/<int:division_id>')
def view_division(division_id):
    """View the inventory for a specific division"""
    division = InventoryDivision.query.get_or_404(division_id)
    kits_form = KitsSentForm()
    trains_form = TrainsCompletedForm()
    # Alias for DivisionInventory to make the join explicit
    div_inv_alias = aliased(DivisionInventory)
    # Left outer join from MainBOMStorage to DivisionInventory
    # This ensures all parts are listed, even if they haven't been added to the division yet
    parts_query = db.session.query(
        MainBOMStorage,
        div_inv_alias
    ).outerjoin(
        div_inv_alias,
        (MainBOMStorage.id == div_inv_alias.part_id) & (div_inv_alias.division_id == division_id)
    ).order_by(MainBOMStorage.part_number)
    parts_with_inventory = parts_query.all()
    return render_template('division_inventory.html', division=division, parts_with_inventory=parts_with_inventory, kits_form=kits_form, trains_form=trains_form)

@main.route('/division/<int:division_id>/send_kits', methods=['POST'])
@admin_required
def send_kits(division_id):
    """Handle the logic for sending kits to a division"""
    division = InventoryDivision.query.get_or_404(division_id)
    form = KitsSentForm()
    if form.validate_on_submit():
        num_kits = form.number_of_kits.data
        try:
            # --- Pre-check for stock availability ---
            all_parts = MainBOMStorage.query.all()
            parts_to_ship = []
            for part in all_parts:
                required_qty = (part.qty_per_lrv or 0.0) * num_kits
                current_stock = part.qty_current_stock or 0.0
                if current_stock < required_qty:
                    flash(f'Insufficient stock for part "{part.part_number}". Required: {required_qty}, Available: {current_stock}', 'error')
                    return redirect(url_for('main.view_division', division_id=division_id))
                parts_to_ship.append({'part': part, 'required': required_qty})
            
            # --- If all checks pass, proceed with transaction ---
            with db.session.begin_nested():
                # Update division's kit count with safe arithmetic
                division.kits_sent_to_site = (division.kits_sent_to_site or 0) + num_kits
                db.session.add(division)
                
                # Update individual part quantities
                for item in parts_to_ship:
                    part = item['part']
                    required_qty = item['required']
                    
                    # Deduct from main stock with safe arithmetic
                    current_stock = part.qty_current_stock or 0.0
                    part.qty_current_stock = current_stock - required_qty
                    part.qty_shipped_out = (part.qty_shipped_out or 0.0) + required_qty
                    part.calculate_lrv_coverage()
                    
                    # Update division inventory
                    div_inv = DivisionInventory.query.filter_by(division_id=division.id, part_id=part.id).first()
                    if not div_inv:
                        div_inv = DivisionInventory(
                            division_id=division.id, 
                            part_id=part.id,
                            qty_sent_to_site=0.0,
                            qty_used_on_site=0.0
                        )
                        db.session.add(div_inv)
                    
                    # Safe arithmetic for division inventory
                    div_inv.qty_sent_to_site = (div_inv.qty_sent_to_site or 0.0) + required_qty
                    db.session.add(part)
                    db.session.add(div_inv)
                    
            db.session.commit()
            flash(f'{num_kits} kit(s) successfully sent to {division.division_name}. Stock levels updated.', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while sending kits: {str(e)}', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", "error")
    
    return redirect(url_for('main.view_division', division_id=division_id))

@main.route('/defected_parts', methods=['GET', 'POST'])
@admin_required
def defected_parts():
    """Log and view defected parts"""
    form = DefectedPartForm()
    # Populate division choices, including an option for no specific division
    form.division_id.choices = [(div.id, div.division_name) for div in InventoryDivision.query.order_by('division_name')]
    form.division_id.choices.insert(0, ('', 'N/A - Main Stock or Unspecified'))
    
    if form.validate_on_submit():
        # Find the corresponding BOM item to ensure part number is valid
        bom_item = MainBOMStorage.query.filter_by(part_number=form.part_number.data).first()
        if not bom_item:
            flash(f'Part number "{form.part_number.data}" not found in the main BOM.', 'error')
        else:
            new_defected_part = DefectedPart(
                part_number=form.part_number.data,
                part_name=form.part_name.data,
                quantity=form.quantity.data,
                division_id=form.division_id.data if form.division_id.data else None,
                notes=form.notes.data
            )
            db.session.add(new_defected_part)
            db.session.commit()
            flash(f'Defected part "{new_defected_part.part_number}" logged successfully.', 'success')
            return redirect(url_for('main.defected_parts'))
    
    # Get list of all defected parts for display
    defected_parts_list = DefectedPart.query.order_by(DefectedPart.date_reported.desc()).all()
    return render_template('defected_parts.html', form=form, defected_parts=defected_parts_list)

@main.route('/stock_overview')
def stock_overview():
    """Display a comprehensive stock overview across all divisions"""
    search_term = request.args.get('search', '').strip()
    # Base query for parts
    parts_query = MainBOMStorage.query
    if search_term:
        parts_query = parts_query.filter(
            or_(
                MainBOMStorage.part_number.ilike(f'%{search_term}%'),
                MainBOMStorage.part_name.ilike(f'%{search_term}%')
            )
        )
    parts = parts_query.order_by(MainBOMStorage.part_number).all()
    divisions = InventoryDivision.query.order_by(InventoryDivision.division_name).all()
    
    # Create a lookup for division inventories to avoid N+1 queries
    # { part_id: { division_id: qty_remaining } }
    division_inventory_data = {}
    div_inventories = DivisionInventory.query.all()
    for item in div_inventories:
        if item.part_id not in division_inventory_data:
            division_inventory_data[item.part_id] = {}
        # Safe arithmetic for remaining quantity
        qty_remaining = (item.qty_sent_to_site or 0.0) - (item.qty_used_on_site or 0.0)
        division_inventory_data[item.part_id][item.division_id] = max(0.0, qty_remaining)
    
    # Prepare data for the template
    stock_data = []
    for part in parts:
        part_data = {
            'part': part,
            'division_stock': []
        }
        for division in divisions:
            stock = division_inventory_data.get(part.id, {}).get(division.id, 0)
            part_data['division_stock'].append(stock)
        stock_data.append(part_data)
    
    return render_template('stock_overview.html',
                           stock_data=stock_data,
                           divisions=divisions,
                           search_term=search_term)

@main.route('/division/<int:division_id>/complete_trains', methods=['POST'])
@admin_required
def complete_trains(division_id):
    """Handle the logic for completing trains for a division"""
    division = InventoryDivision.query.get_or_404(division_id)
    form = TrainsCompletedForm()
    if form.validate_on_submit():
        num_trains = form.number_of_trains.data
        try:
            # --- Pre-check for availability of parts on site ---
            all_parts_info = MainBOMStorage.query.all()
            parts_to_consume = []
            for part_info in all_parts_info:
                required_qty = (part_info.qty_per_lrv or 0.0) * num_trains
                div_inv = DivisionInventory.query.filter_by(division_id=division.id, part_id=part_info.id).first()
                
                # Calculate remaining quantity with safe arithmetic
                if div_inv:
                    qty_remaining = (div_inv.qty_sent_to_site or 0.0) - (div_inv.qty_used_on_site or 0.0)
                    qty_remaining = max(0.0, qty_remaining)
                else:
                    qty_remaining = 0.0
                
                # Check if there are enough parts remaining on site
                if qty_remaining < required_qty:
                    flash(f'Insufficient parts on site for "{part_info.part_number}". Required: {required_qty}, Remaining: {qty_remaining}', 'error')
                    return redirect(url_for('main.view_division', division_id=division_id))
                parts_to_consume.append({'div_inv': div_inv, 'required': required_qty})
            
            # --- If all checks pass, proceed with transaction ---
            with db.session.begin_nested():
                # Update division's completed trains count with safe arithmetic
                division.trains_completed = (division.trains_completed or 0) + num_trains
                db.session.add(division)
                
                # Update individual part consumption
                for item in parts_to_consume:
                    div_inv = item['div_inv']
                    required_qty = item['required']
                    
                    # Safe arithmetic for quantity used
                    div_inv.qty_used_on_site = (div_inv.qty_used_on_site or 0.0) + required_qty
                    db.session.add(div_inv)
                    
            db.session.commit()
            flash(f'{num_trains} train(s) marked as completed for {division.division_name}. On-site quantities updated.', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while completing trains: {str(e)}', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", "error")
    
    return redirect(url_for('main.view_division', division_id=division_id))
