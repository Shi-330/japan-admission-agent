"""
Hybrid school search (V2.4): vector + BM25 + metadata filters.

Leverages the existing VectorStoreService hybrid_search infrastructure
by indexing school descriptions as documents with metadata tags.
"""
from typing import Optional
from demo.school_database import School, get_all_schools, _row_to_school
from rag.vector_store import VectorStoreService, get_vector_store
from utils.supabase_client import supabase


SCHOOL_DOC_TYPE = "school_profile"


def _school_to_text(s: School) -> str:
    """Build a searchable text representation of a school for embedding."""
    parts = [s.name]
    if s.majors:
        parts.append("专业: " + ", ".join(s.majors))
    if s.tags:
        parts.append("标签: " + ", ".join(s.tags))
    if s.exam:
        parts.append("考试: " + s.exam)
    if s.notes:
        parts.append("备注: " + s.notes)
    return "\n".join(parts)


def index_schools(clear_first: bool = True):
    """Embed all schools into the documents table using batched upload (V2.4)."""
    import uuid, time
    from model.factory import embed_model

    schools = get_all_schools()
    if not schools:
        print("No schools found in database.")
        return

    vs = get_vector_store()

    if clear_first:
        try:
            supabase.table("documents").delete() \
                .filter("metadata->>type", "eq", SCHOOL_DOC_TYPE) \
                .execute()
            print("Cleared old school documents")
        except Exception:
            pass

    from langchain_core.documents import Document
    docs = []
    for s in schools:
        text = _school_to_text(s)
        docs.append(Document(page_content=text, metadata={
            "type": SCHOOL_DOC_TYPE,
            "school_name": s.name,
            "jlpt_min": s.jlpt_min or "",
            "degree": s.degree,
        }))

    split_docs = vs.spliter.split_documents(docs)
    batch_size = 5
    success = 0
    for i in range(0, len(split_docs), batch_size):
        batch = split_docs[i:i + batch_size]
        rows = []
        for doc in batch:
            try:
                emb = embed_model.embed_query(doc.page_content)
                rows.append({
                    "id": str(uuid.uuid4()),
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "embedding": emb,
                })
            except Exception as e:
                print(f"  Embed error: {e}")
        if rows:
            try:
                supabase.table("documents").upsert(rows).execute()
                success += len(rows)
            except Exception as e:
                print(f"  Batch failed: {e}")
                for row in rows:
                    try:
                        supabase.table("documents").upsert([row]).execute()
                        success += 1
                    except Exception:
                        pass
        time.sleep(0.3)
    print(f"Indexed {len(schools)} schools ({success}/{len(split_docs)} chunks).")


def _get_school_by_name(name: str) -> Optional[School]:
    """Fetch a single school from Supabase by name."""
    try:
        res = supabase.table("schools").select("*").eq("name", name).execute()
        if res.data:
            return _row_to_school(res.data[0])
    except Exception:
        pass
    return None


def hybrid_search_schools(
    query: str,
    k: int = 10,
    jlpt_min: str = "",
    degree: str = "",
    english_required: Optional[bool] = None,
) -> list[dict]:
    """
    Hybrid search schools: vector + BM25 with RRF fusion + metadata post-filters.

    Returns [{school_name, similarity, school}].
    """
    vs = get_vector_store()
    filter_meta = {"type": SCHOOL_DOC_TYPE}
    if degree:
        filter_meta["degree"] = degree

    # Hybrid search (falls back to vector-only if BM25 index not built)
    try:
        results = vs.hybrid_search(query, k=k * 2, filter_metadata=filter_meta)
    except Exception:
        results = vs.similarity_search(query, k=k * 2, filter_metadata=filter_meta)

    # Batch-load all schools once (avoid N+1 queries)
    all_schools = {s.name: s for s in get_all_schools()}

    # Deduplicate by school name + post-filter
    seen = set()
    output = []
    for doc in results:
        school_name = doc.metadata.get("school_name", "")
        if not school_name or school_name in seen:
            continue
        seen.add(school_name)

        school = all_schools.get(school_name)
        if not school:
            continue

        # JLPT post-filter (pgvector metadata can only do equality, not range)
        if jlpt_min and school.jlpt_min:
            jlpt_order = ["N5", "N4", "N3", "N2", "N1"]
            try:
                req_idx = jlpt_order.index(school.jlpt_min)
                want_idx = jlpt_order.index(jlpt_min)
                if req_idx > want_idx:  # school requires higher than user has
                    continue
            except ValueError:
                pass

        # English post-filter
        if english_required is not None:
            req = school.english_req or {}
            has_english = req.get("required", False)
            if english_required and not has_english:
                continue
            if not english_required and has_english:
                continue

        output.append({
            "school_name": school_name,
            "similarity": round(doc.metadata.get("similarity", 0), 4),
            "school": school.model_dump(),
        })

        if len(output) >= k:
            break

    return output

