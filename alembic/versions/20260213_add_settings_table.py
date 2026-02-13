"""
Alembic migration for settings table
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260213_add_settings_table'
down_revision = '20260212_add_talents'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'settings',
        sa.Column('id', sa.String(), primary_key=True, default='default'),
        sa.Column('gemini_api_key', sa.Text()),
        sa.Column('anthropic_api_key', sa.Text()),
        sa.Column('supabase_url', sa.Text()),
        sa.Column('supabase_key', sa.Text()),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

def downgrade():
    op.drop_table('settings')
