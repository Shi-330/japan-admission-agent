"""Batch-ingest knowledge base + school documents into Supabase pgvector."""
import sys, os, time, hashlib, uuid
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from model.factory import embed_model
from utils.supabase_client import supabase
from rag.vector_store import VectorStoreService
from langchain_community.document_loaders import TextLoader, PyPDFLoader

BATCH_SIZE = 10  # upload 10 chunks at a time to avoid timeouts
DATA_DIR = "data/external"
MD5_FILE = "md5.txt"

def load_known_hashes():
    hashes = set()
    if os.path.exists(MD5_FILE):
        with open(MD5_FILE) as f:
            for line in f:
                hashes.add(line.strip())
    return hashes

def save_hash(filepath):
    with open(filepath, "rb") as f:
        h = hashlib.md5(f.read()).hexdigest()
    with open(MD5_FILE, "a") as out:
        out.write(h + "\n")
    return h

def chunk_text(text, source, chunk_size=350, overlap=50):
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append({
                "content": chunk.strip(),
                "metadata": {"source": os.path.basename(source), "type": "knowledge_base"}
            })
        start = end - overlap
    return chunks

def ingest():
    known = load_known_hashes()
    vs = VectorStoreService()
    all_chunks = []

    # Scan data/external for txt and pdf files
    for fname in sorted(os.listdir(DATA_DIR)):
        fpath = os.path.join(DATA_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            save_hash(fpath)
        except Exception:
            pass  # already processed or md5 error

        ext = os.path.splitext(fname)[1].lower()
        text = ""
        if ext == ".txt":
            with open(fpath, encoding="utf-8") as f:
                text = f.read()
        elif ext == ".pdf":
            try:
                loader = PyPDFLoader(fpath)
                pages = loader.load()
                text = "\n".join(p.page_content for p in pages)
            except Exception as e:
                print(f"  SKIP {fname}: PDF read error ({e})")
                continue
        else:
            continue

        if not text.strip():
            print(f"  SKIP {fname}: empty")
            continue

        chunks = chunk_text(text, fname)
        all_chunks.extend(chunks)
        print(f"  {fname}: {len(text)} chars -> {len(chunks)} chunks")

    print(f"\nTotal chunks: {len(all_chunks)}")

    # Clear old documents
    try:
        supabase.table("documents").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        print("Cleared old documents")
    except Exception as e:
        print(f"Clear warning (may be OK): {e}")

    # Upload in batches
    total = len(all_chunks)
    success = 0
    for i in range(0, total, BATCH_SIZE):
        batch = all_chunks[i:i + BATCH_SIZE]
        rows = []
        for chunk in batch:
            try:
                emb = embed_model.embed_query(chunk["content"])
                rows.append({
                    "id": str(uuid.uuid4()),
                    "content": chunk["content"],
                    "metadata": chunk["metadata"],
                    "embedding": emb,
                })
            except Exception as e:
                print(f"  Embed error: {e}")
                continue

        if rows:
            try:
                supabase.table("documents").upsert(rows).execute()
                success += len(rows)
            except Exception as e:
                print(f"  Upload batch {i}-{i + BATCH_SIZE} failed: {e}")
                # Retry one by one
                for row in rows:
                    try:
                        supabase.table("documents").upsert([row]).execute()
                        success += 1
                    except Exception as e2:
                        print(f"    Single row failed: {e2}")

        print(f"  Progress: {min(i + BATCH_SIZE, total)}/{total} ({success} OK)")
        time.sleep(0.5)  # rate limit

    print(f"\nDone. {success}/{total} documents ingested.")


if __name__ == "__main__":
    ingest()
