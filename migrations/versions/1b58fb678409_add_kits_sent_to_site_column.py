"""Add kits_sent_to_site column

Revision ID: 1b58fb678409
Revises: 
Create Date: 2025-08-19 17:02:36.384534

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1b58fb678409'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add kits_sent_to_site column to inventory_division."""
    with op.batch_alter_table('inventory_division') as batch_op:
        batch_op.add_column(sa.Column('kits_sent_to_site', sa.Integer(), nullable=False, server_default='0'))

    # remove server default after data migration
    with op.batch_alter_table('inventory_division') as batch_op:
        batch_op.alter_column('kits_sent_to_site', server_default=None)


def downgrade():
    """Remove kits_sent_to_site column from inventory_division."""
    with op.batch_alter_table('inventory_division') as batch_op:
        batch_op.drop_column('kits_sent_to_site')
