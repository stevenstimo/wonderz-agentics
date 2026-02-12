
"""
Add growth field to crew_members table

Revision ID: 20260212_add_growth
Revises: 7d3fb229eb8c
Create Date: 2026-02-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260212_add_growth'
down_revision: Union[str, Sequence[str], None] = '7d3fb229eb8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.add_column('crew_members', sa.Column('growth', sa.Text()))

def downgrade():
    op.drop_column('crew_members', 'growth')
