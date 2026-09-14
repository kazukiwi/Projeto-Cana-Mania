"""merge heads

Revision ID: c819000494c6
Revises: 69d59e5ed316, c8cc98ddfbe6
Create Date: 2026-06-02 11:00:34.223701

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c819000494c6'
down_revision: Union[str, Sequence[str], None] = ('69d59e5ed316', 'c8cc98ddfbe6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
