import json
import os
from config import OUTPUT_DIR
from services.ingestion   import load_tickets
from services.vector_store import store_tickets
from agents.agent1_cluster import run as run_agent1
from agents.agent2_draft   import run as run_agent2
from agents.agent3_review  import run as run_agent3
from services.email        import send


def run_pipeline(csv_path: str = None) -> list[dict]:
    """
    Full KB article generation pipeline.

    Steps:
      1. Ingest tickets from CSV
      2. Embed + store in ChromaDB
      3. Agent 1 — cluster + summarize
      4. Agent 2 — draft article (with RAG)
      5. Agent 3 — review + package
      6. Email ReviewPackage to Knowledge Manager

    Returns:
        List of ReviewPackage dicts — one per cluster
    """
    from config import CSV_PATH
    csv = csv_path or CSV_PATH

    print("\n" + "=" * 60)
    print("  KB ARTICLE GENERATOR — PIPELINE START")
    print("=" * 60)

    # ── Step 1 + 2: ingest + embed ─────────────────────────
    print("\n[Pipeline] Step 1/4 — Ingestion + Embedding")
    tickets = load_tickets(csv)
    store_tickets(tickets)

    # ── Step 3: Agent 1 ────────────────────────────────────
    print("\n[Pipeline] Step 2/4 — Agent 1: Clustering")
    clusters = run_agent1(tickets)

    if not clusters:
        print("[Pipeline] No clusters above threshold. Exiting.")
        return []

    # ── Step 4 + 5 + 6: Agent 2 → Agent 3 → Email ─────────
    review_packages = []
    total = len(clusters)

    for i, cluster in enumerate(clusters, 1):
        print(f"\n[Pipeline] Processing cluster {i}/{total}: {cluster['topic']}")

        # Agent 2 — draft
        print(f"[Pipeline] Step 3/4 — Agent 2: Drafting article")
        draft = run_agent2(cluster)

        # Agent 3 — review
        print(f"[Pipeline] Step 4/4 — Agent 3: Reviewing draft")
        package = run_agent3(draft)

        # Email
        send(package)

        review_packages.append(package)

    # ── Summary ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)
    print(f"\n  Clusters processed : {len(review_packages)}")
    print(f"  Emails sent        : {len(review_packages)}")
    print(f"  Output folder      : {OUTPUT_DIR}/")
    print()

    for p in review_packages:
        print(f"  {p['cluster_id']} | {p['topic']:<25} | "
              f"Confidence: {p['confidence_score']}/100 | "
              f"Deflection: ~{p['estimated_deflection_pct']}%")

    print("\n  Check emails at: https://mailtrap.io/inboxes")
    print("=" * 60 + "\n")

    return review_packages


if __name__ == "__main__":
    results = run_pipeline()