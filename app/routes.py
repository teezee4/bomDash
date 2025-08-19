from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from app.models import MainBOMStorage, DeliveryLog, InventoryDivision, StockAdjustment, DivisionPartInventory, DefectedPart
from app.forms import DeliveryForm, StockAdjustmentForm, BOMItemForm, SearchForm, TrainCalculatorForm, DivisionKitsForm, DefectedPartForm
from sqlalchemy import or_
import json
from datetime import datetime, date, timedelta


main = Blueprint('main', __name__)


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
    
    # Calculate total stock items - Fixed: Use correct field name
    total_stock_items = db.session.query(
        db.func.sum(MainBOMStorage.qty_current_stock)
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
        
        # Apply stock level filters
        if low_stock_only == 'low':
            query = query.filter(
                db.and_(
                    MainBOMStorage.lrv_coverage < 10,
                    MainBOMStorage.qty_current_stock > 0
                )
            )
        elif low_stock_only == 'out':
            query = query.filter(MainBOMStorage.qty_current_stock <= 0)
        
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
            # Fixed: Update the correct database field
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
                # Fixed: Use correct field name
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
                # Fixed: Use correct field name
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


# Additional routes for enhanced functionality


@main.route('/edit_part/<int:part_id>', methods=['GET', 'POST'])
def edit_part(part_id):
    """Edit a specific BOM item"""
    bom_item = MainBOMStorage.query.get_or_404(part_id)
    form = BOMItemForm(obj=bom_item)
    
    if form.validate_on_submit():
        # Update all the fields
        form.populate_obj(bom_item)
        
        # Recalculate dependent fields
        bom_item.total_needed_233_lrv = bom_item.qty_per_lrv * 233
        bom_item.calculate_lrv_coverage()
        bom_item.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash(f'Part {bom_item.part_number} updated successfully!', 'success')
        return redirect(url_for('main.parts_list'))
    
    return render_template('edit_part.html', form=form, part=bom_item)


@main.route('/add_part', methods=['GET', 'POST'])
def add_part():
    """Add a new BOM item"""
    form = BOMItemForm()
    
    if form.validate_on_submit():
        # Check if part number already exists
        existing_part = MainBOMStorage.query.filter_by(part_number=form.part_number.data).first()
        if existing_part:
            flash(f'Part number {form.part_number.data} already exists!', 'error')
            return render_template('add_part.html', form=form)
        
        # Create new part
        new_part = MainBOMStorage(
            part_number=form.part_number.data,
            part_name=form.part_name.data,
            description=form.description.data,
            supplier=form.supplier.data,
            component=form.component.data,
            qty_per_lrv=form.qty_per_lrv.data,
            qty_on_site=form.qty_on_site.data,
            qty_current_stock=form.qty_current_stock.data,
            consumable_or_essential=form.consumable_or_essential.data,
            notes=form.notes.data,
            total_needed_233_lrv=form.qty_per_lrv.data * 233
        )
        
        # Calculate LRV coverage
        new_part.calculate_lrv_coverage()
        
        db.session.add(new_part)
        db.session.commit()
        
        flash(f'Part {new_part.part_number} added successfully!', 'success')
        return redirect(url_for('main.parts_list'))
    
    return render_template('add_part.html', form=form)


@main.route('/export_shipment', methods=['GET', 'POST'])
def export_shipment():
    """Export/ship parts to divisions and deduct from stock"""
    if request.method == 'POST':
        division_name = request.form.get('division_name')
        shipment_data = request.form.get('shipment_data')  # JSON data of parts and quantities
        
        try:
            shipments = json.loads(shipment_data)
            total_shipped = 0
            
            division = InventoryDivision.query.filter_by(division_name=division_name).first()
            if not division:
                division = InventoryDivision(division_name=division_name)
                db.session.add(division)
                db.session.flush()  # Get the division ID

            # Process each shipment item
            for item in shipments:
                part_number = item.get('part_number')
                quantity = float(item.get('quantity', 0))
                
                if quantity <= 0:
                    continue
                
                # Find the BOM item
                bom_item = MainBOMStorage.query.filter_by(part_number=part_number).first()
                if bom_item and bom_item.qty_current_stock >= quantity:
                    # Deduct from current stock
                    bom_item.qty_current_stock -= quantity
                    bom_item.qty_shipped_out += quantity
                    bom_item.calculate_lrv_coverage()

                    # Update division part inventory
                    div_part_inv = DivisionPartInventory.query.filter_by(
                        part_id=bom_item.id,
                        division_id=division.id
                    ).first()

                    if div_part_inv:
                        div_part_inv.qty_sent_to_site += quantity
                        div_part_inv.qty_remaining += quantity
                    else:
                        div_part_inv = DivisionPartInventory(
                            part_id=bom_item.id,
                            division_id=division.id,
                            qty_sent_to_site=quantity,
                            qty_remaining=quantity
                        )
                        db.session.add(div_part_inv)

                    total_shipped += 1
                else:
                    flash(f'Insufficient stock for part {part_number}', 'warning')
            
            division.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash(f'Shipment to {division_name} completed. {total_shipped} items shipped.', 'success')
            
        except (json.JSONDecodeError, ValueError) as e:
            flash('Invalid shipment data format', 'error')
        except Exception as e:
            flash(f'Error processing shipment: {str(e)}', 'error')
            db.session.rollback()
    
    # Get all parts for shipment form
    all_parts = MainBOMStorage.query.filter(MainBOMStorage.qty_current_stock > 0).all()
    divisions = InventoryDivision.query.all()
    
    return render_template('export_shipment.html', parts=all_parts, divisions=divisions)


@main.route('/division/<int:division_id>', methods=['GET', 'POST'])
def division_inventory(division_id):
    """Display and manage inventory for a specific division"""
    division = InventoryDivision.query.get_or_404(division_id)
    form = DivisionKitsForm(obj=division)

    if form.validate_on_submit():
        new_kits_sent = form.kits_sent_to_site.data
        new_trains_completed = form.trains_completed_count.data

        # Calculate diffs
        kits_diff = new_kits_sent - (division.kits_sent_to_site or 0)
        trains_diff = new_trains_completed - (division.trains_completed_count or 0)

        if kits_diff > 0:
            # Update qty_sent_to_site for all parts in the division
            for part_inv in division.parts:
                qty_to_add = part_inv.part.qty_per_lrv * kits_diff
                part_inv.qty_sent_to_site += qty_to_add
                part_inv.qty_remaining += qty_to_add

        if trains_diff > 0:
            # Update qty_used_on_site for all parts in the division
            for part_inv in division.parts:
                qty_to_use = part_inv.part.qty_per_lrv * trains_diff
                part_inv.qty_used_on_site += qty_to_use
                part_inv.qty_remaining -= qty_to_use

        # Update division counters
        division.kits_sent_to_site = new_kits_sent
        division.trains_completed_count = new_trains_completed

        db.session.commit()
        flash(f'Inventory for {division.division_name} updated.', 'success')
        return redirect(url_for('main.division_inventory', division_id=division_id))

    parts_inventory = DivisionPartInventory.query.filter_by(division_id=division_id).all()

    return render_template('division_inventory.html',
                         division=division,
                         parts_inventory=parts_inventory,
                         form=form)


@main.route('/defected_parts', methods=['GET', 'POST'])
def defected_parts():
    """Report and view defected parts"""
    form = DefectedPartForm()
    form.division_id.choices = [(d.id, d.division_name) for d in InventoryDivision.query.all()]
    form.division_id.choices.insert(0, ('', 'N/A'))

    if form.validate_on_submit():
        delected_part = DefectedPart(
            part_number=form.part_number.data,
            part_name=form.part_name.data,
            quantity=form.quantity.data,
            division_id=form.division_id.data if form.division_id.data else None,
            notes=form.notes.data
        )
        db.session.add(delected_part)
        db.session.commit()
        flash('Defected part reported successfully.', 'success')
        return redirect(url_for('main.defected_parts'))

    defected_parts_list = DefectedPart.query.order_by(DefectedPart.reported_at.desc()).all()
    return render_template('delected_parts.html', form=form, defected_parts=defected_parts_list)


@main.route('/inventory_report')
def inventory_report():
    """Generate comprehensive inventory report"""
    # Low stock items (less than 10 trains worth)
    low_stock_items = MainBOMStorage.query.filter(MainBOMStorage.lrv_coverage < 10).all()
    
    # Out of stock items
    out_of_stock_items = MainBOMStorage.query.filter(MainBOMStorage.qty_current_stock <= 0).all()
    
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
    low_stock_parts = MainBOMStorage.query.filter(MainBOMStorage.lrv_coverage < 10).count()
    out_of_stock_parts = MainBOMStorage.query.filter(MainBOMStorage.qty_current_stock <= 0).count()
    total_stock_items = db.session.query(db.func.sum(MainBOMStorage.qty_current_stock)).scalar() or 0
    
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


@main.route('/stock_overview')
def stock_overview():
    """Display stock overview across all locations"""
    parts = MainBOMStorage.query.order_by(MainBOMStorage.part_number).all()
    divisions = InventoryDivision.query.order_by(InventoryDivision.division_name).all()

    stock_data = []
    for part in parts:
        part_data = {
            'part_number': part.part_number,
            'part_name': part.part_name,
            'qty_current_stock': part.qty_current_stock,
            'qty_shipped_out': part.qty_shipped_out,
            'divisions': []
        }
        for division in divisions:
            div_part_inv = DivisionPartInventory.query.filter_by(
                part_id=part.id,
                division_id=division.id
            ).first()

            if div_part_inv:
                part_data['divisions'].append(div_part_inv.qty_remaining)
            else:
                part_data['divisions'].append(0)
        stock_data.append(part_data)

    return render_template('stock_overview.html',
                         stock_data=stock_data,
                         divisions=divisions)