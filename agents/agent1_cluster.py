import os
import json
import numpy as np
from collections import Counter
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import normalize
from config import CLUSTER_THRESHOLD, OUTPUT_DIR, TOP_K_RAG, DBSCAN_EPS, DBSCAN_MIN_SAMPLES
from services.ingestion import load_tickets
from services.vector_store import store_tickets, get_all_embeddings, find_similar


def _get_dominant(values: list[str]) -> str:
    return Counter(values).most_common(1)[0][0]


def _avg_resolution_time(ticket_ids: list[str], all_tickets: list[dict]) -> float:
    cluster_tickets = [t for t in all_tickets if t["ticket_id"] in ticket_ids]
    times = [t["resolution_time_hrs"] for t in cluster_tickets]
    return round(sum(times) / len(times), 1) if times else 0.0


def run(tickets: list[dict]) -> list[dict]:
    """
    Agent 1 — Clusterer + Summarizer.

    1. Fetch all ticket embeddings from ChromaDB
    2. Run DBSCAN with tuned eps from .env
    3. Filter clusters below threshold
    4. Build ClusterSummary for each valid cluster
    5. Save to outputs/cluster_summaries.json
    """
    print("\n[Agent 1] Starting clustering ...")
    print(f"[Agent 1] DBSCAN params: eps={DBSCAN_EPS}, min_samples={DBSCAN_MIN_SAMPLES}")

    # ── 1. get embeddings ──────────────────────────────────
    ids, embeddings = get_all_embeddings()
    if not ids:
        raise ValueError("No embeddings found. Run store_tickets() first.")

    vectors = normalize(np.array(embeddings))   # L2 normalise for cosine

    # ── 2. run DBSCAN ──────────────────────────────────────
    db            = DBSCAN(
                        eps         = DBSCAN_EPS,
                        min_samples = DBSCAN_MIN_SAMPLES,
                        metric      = "cosine"
                    ).fit(vectors)

    labels        = db.labels_
    unique_labels = set(labels) - {-1}
    noise_count   = list(labels).count(-1)

    print(f"[Agent 1] {len(unique_labels)} raw clusters found "
          f"(+ {noise_count} noise tickets)")

    # ── 3. build cluster summaries ─────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cluster_summaries = []

    for idx, label in enumerate(sorted(unique_labels)):
        cluster_ids = [ids[i] for i, l in enumerate(labels) if l == label]

        # skip below threshold
        if len(cluster_ids) < CLUSTER_THRESHOLD:
            print(f"  Cluster {label}: {len(cluster_ids)} tickets "
                  f"— below threshold ({CLUSTER_THRESHOLD}), skipping")
            continue

        # get full ticket data for this cluster
        cluster_tickets = [t for t in tickets if t["ticket_id"] in cluster_ids]

        category     = _get_dominant([t["category"]      for t in cluster_tickets])
        subcategory  = _get_dominant([t["subcategory"]   for t in cluster_tickets])
        sme_assignee = _get_dominant([t["assignee"]      for t in cluster_tickets])
        sme_team     = _get_dominant([t["assignee_team"] for t in cluster_tickets])
        avg_time     = _avg_resolution_time(cluster_ids, tickets)

        # semantic search — most representative tickets for RAG
        query       = f"{category} {subcategory} issue resolution"
        top_tickets = find_similar(query, k=TOP_K_RAG)
        top_tickets = [t for t in top_tickets if t["ticket_id"] in cluster_ids]

        # resolution pattern from top 3
        resolution_pattern = " | ".join(
            t["text"].split("Resolution:")[-1].strip()
            for t in top_tickets[:3]
            if "Resolution:" in t["text"]
        )

        summary = {
            "cluster_id"         : f"CLU-{idx:02d}",
            "topic"              : f"{category} / {subcategory}",
            "category"           : category,
            "subcategory"        : subcategory,
            "ticket_count"       : len(cluster_ids),
            "ticket_ids"         : cluster_ids,
            "resolution_pattern" : resolution_pattern,
            "avg_resolution_hrs" : avg_time,
            "sme_assignee"       : sme_assignee,
            "sme_team"           : sme_team,
            "sample_texts"       : [t["text"] for t in top_tickets[:3]],
        }

        cluster_summaries.append(summary)
        print(f"  Cluster {label}: [{summary['cluster_id']}] "
              f"{summary['topic']} — {len(cluster_ids)} tickets "
              f"| SME: {sme_assignee}")

    # ── 4. save ────────────────────────────────────────────
    out_path = os.path.join(OUTPUT_DIR, "cluster_summaries.json")
    with open(out_path, "w") as f:
        json.dump(cluster_summaries, f, indent=2)

    print(f"\n[Agent 1] {len(cluster_summaries)} clusters saved -> {out_path}\n")
    return cluster_summaries


if __name__ == "__main__":
    tickets  = load_tickets()
    store_tickets(tickets)
    clusters = run(tickets)

    print("=" * 60)
    for c in clusters:
        print(f"\nCluster  : {c['cluster_id']}")
        print(f"Topic    : {c['topic']}")
        print(f"Tickets  : {c['ticket_count']} -> {c['ticket_ids']}")
        print(f"SME      : {c['sme_assignee']} ({c['sme_team']})")
        print(f"Avg time : {c['avg_resolution_hrs']} hrs")
        print(f"Pattern  : {c['resolution_pattern'][:100]}...")