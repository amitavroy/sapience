from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

# openai/text-embedding-3-small (via OpenRouter).
# pgvector's HNSW index caps `vector` at 2000 dimensions.
EMBEDDING_DIM = 1536

# JSONB on Postgres, plain JSON elsewhere (SQLite in tests)
JSONType = JSON().with_variant(JSONB(), "postgresql")
