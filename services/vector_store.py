import os
import chromadb
from sentence_transformers import SentenceTransformer
from config import CHROMA_PATH, EMBED_MODEL, TOP_K_RAG

# ── singletons — loaded once, reused across calls ──────────
_model      = None
_client     = None
_collection = None

COLLECTION_NAME = "tickets"


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"[VectorStore] Loading embedding model: {EMBED_MODEL} ...")
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def _get_collection():
    global _client, _collection
    if _collection is None:
        os.makedirs(CHROMA_PATH, exist_ok=True)
        _client     = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _client.get_or_create_collection(
            name     = COLLECTION_NAME,
            metadata = {"hnsw:space": "cosine"}
        )
    return _collection


# ── public API ─────────────────────────────────────────────

def store_tickets(tickets: list[dict]):
    """Embed every ticket and store vectors in ChromaDB."""
    collection = _get_collection()
    model      = _get_model()

    texts     = [t["embed_text"] for t in tickets]
    ids       = [t["ticket_id"]  for t in tickets]
    metadatas = [{
        "category"     : t["category"],
        "subcategory"  : t["subcategory"],
        "assignee"     : t["assignee"],
        "assignee_team": t["assignee_team"],
        "priority"     : t["priority"],
        "tags"         : t["tags"],
    } for t in tickets]

    print(f"[VectorStore] Embedding {len(texts)} tickets ...")
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    collection.upsert(
        ids        = ids,
        embeddings = embeddings,
        documents  = texts,
        metadatas  = metadatas
    )
    print(f"[VectorStore] {len(ids)} vectors stored -> {CHROMA_PATH}\n")


def find_similar(query_text: str, k: int = TOP_K_RAG) -> list[dict]:
    """
    Semantic search — find top-K tickets closest in meaning to query_text.
    Used by Agent 1 (clustering) and Agent 2 (RAG retrieval).
    """
    collection   = _get_collection()
    model        = _get_model()
    query_vector = model.encode([query_text]).tolist()

    results = collection.query(
        query_embeddings = query_vector,
        n_results        = k,
        include          = ["documents", "metadatas", "distances"]
    )

    hits = []
    for i in range(len(results["ids"][0])):
        hits.append({
            "ticket_id": results["ids"][0][i],
            "text"     : results["documents"][0][i],
            "metadata" : results["metadatas"][0][i],
            "score"    : round(1 - results["distances"][0][i], 4)
        })
    return hits


def get_all_embeddings() -> tuple[list[str], list[list[float]]]:
    """
    Return all ticket IDs and their raw vectors.
    Used by Agent 1 for DBSCAN clustering.
    """
    result = _get_collection().get(include=["embeddings"])
    return result["ids"], result["embeddings"]


def count() -> int:
    """Number of vectors currently stored."""
    return _get_collection().count()


# ── quick test ─────────────────────────────────────────────
if __name__ == "__main__":
    from services.ingestion import load_tickets

    tickets = load_tickets()
    store_tickets(tickets)

    print(f"Total vectors stored: {count()}\n")

    query   = "VPN not connecting after Windows update"
    print(f"Semantic search: '{query}'\n")
    results = find_similar(query, k=3)
    for r in results:
        print(f"  [{r['score']:.3f}] {r['ticket_id']} — {r['text'][:80]}...")