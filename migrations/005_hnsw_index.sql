-- Enable pgvector HNSW index for faster vector search.
-- HNSW is ~10-100x faster than IVFFlat for ANN queries.
-- Parameters tuned for ~200 documents (110 knowledge + ~90 schools).
CREATE INDEX IF NOT EXISTS documents_embedding_hnsw_idx
  ON documents
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 200);
