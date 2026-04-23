import os
import json
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, OUTPUT_DIR, TOP_K_RAG
from services.vector_store import find_similar

client = OpenAI(api_key=OPENAI_API_KEY)


def _build_prompt(cluster: dict, rag_tickets: list[dict]) -> str:
    """Build the prompt — ClusterSummary + RAG tickets as grounding context."""

    rag_context = "\n\n".join([
        f"Ticket {i+1} [{t['ticket_id']}]:\n{t['text']}"
        for i, t in enumerate(rag_tickets)
    ])

    return f"""You are a technical knowledge base writer for an IT/HR help desk.

Your job is to write a clear, structured KB article based ONLY on the real ticket evidence provided below.
Do NOT invent steps or causes that are not supported by the tickets.

## Cluster Information
- Topic       : {cluster['topic']}
- Category    : {cluster['category']}
- Subcategory : {cluster['subcategory']}
- Ticket Count: {cluster['ticket_count']} tickets
- Avg Resolution Time: {cluster['avg_resolution_hrs']} hours
- Resolution Pattern: {cluster['resolution_pattern']}

## Source Tickets (use these as grounding evidence)
{rag_context}

## Instructions
Write a KB article with EXACTLY these four sections:

**Problem**
Describe what the user experiences. Use specific error messages or symptoms from the tickets.

**Cause**
Explain why this happens. Be specific — refer to system components, updates, or configurations mentioned in tickets.

**Resolution**
Provide numbered step-by-step fix instructions. Be precise — exact commands, menu paths, or registry keys if mentioned.

**Escalation Path**
When should the user escalate? Who do they contact? What information should they provide?

Keep the tone professional and concise. Write for a non-technical employee who can follow steps.
Return ONLY the article content — no preamble, no commentary."""


def run(cluster: dict) -> dict:
    """
    Agent 2 — Article Drafter.

    1. Semantic search for top-K most relevant tickets (RAG)
    2. Build prompt with cluster summary + RAG tickets
    3. Call OpenAI API to draft structured KB article
    4. Return ArticleDraft dict
    """
    print(f"\n[Agent 2] Drafting article for: {cluster['topic']} ...")

    # ── RAG retrieval ──────────────────────────────────────
    query       = f"{cluster['topic']} {cluster['resolution_pattern'][:100]}"
    rag_tickets = find_similar(query, k=TOP_K_RAG)
    rag_tickets = [t for t in rag_tickets if t["ticket_id"] in cluster["ticket_ids"]]

    print(f"[Agent 2] RAG retrieved {len(rag_tickets)} tickets as context")

    # ── call OpenAI ────────────────────────────────────────
    prompt   = _build_prompt(cluster, rag_tickets)
    response = client.chat.completions.create(
        model    = OPENAI_MODEL,
        messages = [
            {"role": "system", "content": "You are a technical KB article writer."},
            {"role": "user",   "content": prompt}
        ],
        max_tokens  = 1500,
        temperature = 0.3,
    )

    article_content = response.choices[0].message.content.strip()
    tokens_used     = response.usage.total_tokens

    print(f"[Agent 2] Article drafted ({tokens_used} tokens used)")

    # ── build ArticleDraft ─────────────────────────────────
    draft = {
        "cluster_id"        : cluster["cluster_id"],
        "topic"             : cluster["topic"],
        "category"          : cluster["category"],
        "subcategory"       : cluster["subcategory"],
        "article_content"   : article_content,
        "source_ticket_ids" : cluster["ticket_ids"],
        "rag_ticket_ids"    : [t["ticket_id"] for t in rag_tickets],
        "sme_assignee"      : cluster["sme_assignee"],
        "sme_team"          : cluster["sme_team"],
        "avg_resolution_hrs": cluster["avg_resolution_hrs"],
        "ticket_count"      : cluster["ticket_count"],
        "tokens_used"       : tokens_used,
    }

    # ── save ───────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"draft_{cluster['cluster_id']}_{cluster['subcategory'].lower().replace(' ', '_')}.json"
    out_path = os.path.join(OUTPUT_DIR, filename)
    with open(out_path, "w") as f:
        json.dump(draft, f, indent=2)

    print(f"[Agent 2] Draft saved -> {out_path}")
    return draft


if __name__ == "__main__":
    summaries_path = os.path.join(OUTPUT_DIR, "cluster_summaries.json")
    if not os.path.exists(summaries_path):
        raise FileNotFoundError("Run agent1_cluster.py first.")

    with open(summaries_path) as f:
        clusters = json.load(f)

    # test on first cluster
    test_cluster = clusters[0]
    print(f"Testing Agent 2 on: {test_cluster['topic']}")

    draft = run(test_cluster)

    print("\n" + "=" * 60)
    print(f"Cluster  : {draft['cluster_id']} — {draft['topic']}")
    print(f"Tickets  : {draft['ticket_count']} source tickets")
    print(f"RAG used : {draft['rag_ticket_ids']}")
    print(f"Tokens   : {draft['tokens_used']}")
    print(f"\n--- Article Preview ---\n")
    print(draft["article_content"][:800] + "...")