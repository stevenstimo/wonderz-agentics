
"""
Add talents table for TalentSQL model

Revision ID: 20260212_add_talents
Revises: 20260212_add_growth
Create Date: 2026-02-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision: str = '20260212_add_talents'
down_revision: Union[str, Sequence[str], None] = '20260212_add_growth'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.create_table(
        'talents',
        sa.Column('id', sa.String, primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('persona', sa.Text),
        sa.Column('quality', sa.Text),
        sa.Column('growth', sa.Text),
        sa.Column('skills', sa.Text),
        sa.Column('avatar_url', sa.String(255)),
        sa.Column('created_at', sa.DateTime, default=datetime.utcnow)
    )

def downgrade():
    op.drop_table('talents')
