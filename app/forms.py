from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, TextAreaField, SelectField, DateField, IntegerField
from wtforms.validators import DataRequired, NumberRange, Length, Optional
from datetime import datetime


class DeliveryForm(FlaskForm):
    """Form for logging new deliveries"""
    part_number = StringField('Part Number', validators=[DataRequired(), Length(max=100)])
    part_name = StringField('Part Name', validators=[DataRequired(), Length(max=200)])
    supplier = StringField('Supplier', validators=[DataRequired(), Length(max=100)])
    quantity_received = FloatField('Quantity Received', validators=[DataRequired(), NumberRange(min=0.01)])
    date_received = DateField('Date Received', validators=[DataRequired()], default=datetime.today)
    date_expected = DateField('Expected Date (Future Deliveries)', validators=[Optional()])
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=500)])


class StockAdjustmentForm(FlaskForm):
    """Form for manual stock adjustments"""
    part_number = StringField('Part Number', validators=[DataRequired(), Length(max=100)])
    adjustment_type = SelectField('Adjustment Type', 
                                choices=[('increase', 'Increase Stock'), ('decrease', 'Decrease Stock')],
                                validators=[DataRequired()])
    quantity_adjusted = FloatField('Quantity', validators=[DataRequired(), NumberRange(min=0.01)])
    reason = SelectField('Reason', 
                        choices=[
                            ('damage', 'Damaged Items'),
                            ('lost', 'Lost Items'),
                            ('found', 'Found Items'),
                            ('correction', 'Inventory Correction'),
                            ('other', 'Other (specify in notes)')
                        ],
                        validators=[DataRequired()])
    notes = TextAreaField('Notes/Details', validators=[Optional(), Length(max=500)])
    user_name = StringField('Your Name', validators=[DataRequired(), Length(max=100)])


class BOMItemForm(FlaskForm):
    """Form for editing BOM items"""
    part_number = StringField('Part Number', validators=[DataRequired(), Length(max=100)])
    part_name = StringField('Part Name', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    supplier = StringField('Supplier', validators=[DataRequired(), Length(max=100)])
    component = StringField('Component', validators=[Optional(), Length(max=100)])
    qty_per_lrv = FloatField('Quantity per LRV', validators=[DataRequired(), NumberRange(min=0)])
    qty_on_site = FloatField('Quantity On Site', validators=[NumberRange(min=0)], default=0.0)
    qty_current_stock = FloatField('Current Stock', validators=[NumberRange(min=0)], default=0.0)
    back_order_qty = FloatField('Back Ordered Quantity', validators=[NumberRange(min=0)], default=0.0)
    consumable_or_essential = SelectField('Type',
                                        choices=[('Essential', 'Essential'), ('Consumables', 'Consumables')],
                                        validators=[Optional()])
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=500)])


class SearchForm(FlaskForm):
    """Search form for parts list"""
    search_term = StringField('Search Parts', validators=[Optional(), Length(max=100)])
    description_filter = SelectField('Filter by Description', validators=[Optional()], choices=[])
    type_filter = SelectField('Filter by Type', 
                            choices=[('', 'All Types'), 
                                   ('Long Lead', 'Long Lead'), 
                                   ('Consumables', 'Consumables'),
                                   ('Quick Delivery', 'Quick Delivery')], 
                            validators=[Optional()])
    low_stock_only = SelectField('Stock Level', 
                                choices=[('', 'All Items'), ('low', 'Low Stock Only'), ('out', 'Out of Stock Only')],
                                validators=[Optional()])


class TrainCalculatorForm(FlaskForm):
    """Form for calculating parts needed for specific number of trains"""
    num_trains = IntegerField('Number of Trains', validators=[DataRequired(), NumberRange(min=1, max=1000)])
    part_number = StringField('Specific Part Number (optional)', validators=[Optional(), Length(max=100)])


class UpdateInventoryForm(FlaskForm):
    """Form for updating inventory levels from Excel"""
    excel_file = StringField('Excel File Path', validators=[DataRequired()])
    sheet_name = StringField('Sheet Name', validators=[Optional()], default='BOM')
    dry_run = SelectField('Mode', 
                         choices=[('yes', 'Preview Changes Only'), ('no', 'Apply Changes')],
                         default='yes',
                         validators=[DataRequired()])
