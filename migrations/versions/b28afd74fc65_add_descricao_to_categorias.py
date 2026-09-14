"""add descricao to categorias

Revision ID: b28afd74fc65
Revises: bf7f6d3a80f6
Create Date: 2026-06-08 13:38:39.410571

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b28afd74fc65'
down_revision: Union[str, Sequence[str], None] = 'bf7f6d3a80f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('categorias', sa.Column('descricao', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('categorias', 'descricao')
