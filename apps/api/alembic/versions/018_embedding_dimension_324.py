"""Change embedding columns from vector(1024) to vector(324).

Revision ID: 018
Revises: 017
Create Date: 2026-02-09

"""
from typing import Sequence, Union

from alembic import op


revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # experience_cards: drop HNSW index, replace embedding column with vector(324)
    op.execute("DROP INDEX IF EXISTS ix_experience_cards_embedding_hnsw")
    op.execute("ALTER TABLE experience_cards ADD COLUMN embedding_new vector(324)")
    op.execute("ALTER TABLE experience_cards DROP COLUMN embedding")
    op.execute("ALTER TABLE experience_cards RENAME COLUMN embedding_new TO embedding")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_experience_cards_embedding_hnsw ON experience_cards "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # experience_card_children: same
    op.execute("DROP INDEX IF EXISTS ix_experience_card_children_embedding_hnsw")
    op.execute("ALTER TABLE experience_card_children ADD COLUMN embedding_new vector(324)")
    op.execute("ALTER TABLE experience_card_children DROP COLUMN embedding")
    op.execute("ALTER TABLE experience_card_children RENAME COLUMN embedding_new TO embedding")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_experience_card_children_embedding_hnsw "
        "ON experience_card_children USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_experience_card_children_embedding_hnsw")
    op.execute("ALTER TABLE experience_card_children ADD COLUMN embedding_old vector(1024)")
    op.execute("ALTER TABLE experience_card_children DROP COLUMN embedding")
    op.execute("ALTER TABLE experience_card_children RENAME COLUMN embedding_old TO embedding")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_experience_card_children_embedding_hnsw "
        "ON experience_card_children USING hnsw (embedding vector_cosine_ops)"
    )

    op.execute("DROP INDEX IF EXISTS ix_experience_cards_embedding_hnsw")
    op.execute("ALTER TABLE experience_cards ADD COLUMN embedding_old vector(1024)")
    op.execute("ALTER TABLE experience_cards DROP COLUMN embedding")
    op.execute("ALTER TABLE experience_cards RENAME COLUMN embedding_old TO embedding")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_experience_cards_embedding_hnsw ON experience_cards "
        "USING hnsw (embedding vector_cosine_ops)"
    )
