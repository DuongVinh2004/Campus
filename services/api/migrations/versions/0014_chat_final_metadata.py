"""Review candidate only: additive durable final chat metadata, head 0013.

Not installed in migrations or authorized by fixture guard. No downgrade is
provided: all evidence and existing message data must be preserved.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("message", sa.Column("finish_status", sa.String(32), nullable=True))
    op.add_column("message", sa.Column("response_class", sa.String(32), nullable=True))
    op.add_column("message", sa.Column("citations", JSONB(), nullable=False,
                                      server_default=sa.text("'[]'::jsonb")))
    op.create_check_constraint("ck_message_final_metadata", "message",
        "(finish_status IS NULL AND response_class IS NULL AND citations = '[]'::jsonb) OR "
        "(finish_status IS NOT NULL AND response_class IS NOT NULL AND sender_type='ASSISTANT' AND ((finish_status='answered' AND response_class IN ('grounded_answer','tool_result')) OR "
        "(finish_status IN ('abstained','cancelled') AND response_class='safe_refusal') OR "
        "(finish_status='completed' AND response_class IN ('action_preview','action_result')) OR "
        "(finish_status='handed_over' AND response_class='handover_notice')))"
    )
    op.create_check_constraint("ck_message_citation_array", "message",
                               "jsonb_typeof(citations)='array' AND jsonb_array_length(citations)<=20")


def downgrade():
    raise RuntimeError("Forward recovery required; chat data and citation evidence must be preserved")
