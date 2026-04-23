import os
import json
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, OUTPUT_DIR

client = OpenAI(api_key=OPENAI_API_KEY)


def _build_review_prompt(draft: dict) -> str:
    return f"""You are a senior knowledge base editor reviewing a draft KB article.

## Draft Article
Topic    : {draft['topic']}
Category : {draft['category']}
Tickets  : {draft['ticket_count']} source tickets
Avg Resolution Time: {draft['avg_resolution_hrs']} hours

Article Content:
{draft['article_content']}

## Your Task
Review this article and respond in valid JSON with exactly this structure:

{{
  "confidence_score": <number 0-100>,
  "flags": [
    {{"type": "ambiguity" | "missing_info" | "contradiction", "description": "<what is unclear or missing>"}}
  ],
  "estimated_deflection_pct": <number 0-100>,
  "deflection_reasoning": "<why you estimated this deflection %>"
}}

## Scoring Guide

confidence_score:
- 90-100: Article is clear, complete, specific steps, no gaps
- 70-89 : Minor gaps or slightly vague steps
- 50-69 : Missing key information, vague resolution
- Below 50: Major issues, needs significant rework

flags (add only real issues found):
- ambiguity    : steps that are unclear or could be interpreted multiple ways
- missing_info : important information that is absent (e.g. missing prerequisites)
- contradiction: conflicting information within the article

estimated_deflection_pct:
- Estimate what % of future similar tickets this article would prevent
- Base it on: clarity of resolution, specificity of steps, how common the issue is

Return ONLY valid JSON — no markdown, no commentary."""


def run(draft: dict) -> dict:
    """
    Agent 3 — Review Packager.

    1. Send article draft to OpenAI for QA review
    2. Parse flags, confidence score, deflection estimate
    3. Build final ReviewPackage dict
    4. Save to outputs/
    """
    print(f"\n[Agent 3] Reviewing draft for: {draft['topic']} ...")

    # call OpenAI for review
    prompt   = _build_review_prompt(draft)
    response = client.chat.completions.create(
        model       = OPENAI_MODEL,
        messages    = [
            {"role": "system", "content": "You are a senior KB editor. Always respond with valid JSON only."},
            {"role": "user",   "content": prompt}
        ],
        max_tokens  = 600,
        temperature = 0.1,
    )

    raw         = response.choices[0].message.content.strip()
    tokens_used = response.usage.total_tokens

    # parse JSON response
    try:
        review = json.loads(raw)
    except json.JSONDecodeError:
        # fallback if model adds markdown fences
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        review = json.loads(match.group()) if match else {}

    print(f"[Agent 3] Review complete ({tokens_used} tokens used)")
    print(f"[Agent 3] Confidence : {review.get('confidence_score', 'N/A')}/100")
    print(f"[Agent 3] Flags      : {len(review.get('flags', []))} issue(s) found")
    print(f"[Agent 3] Deflection : ~{review.get('estimated_deflection_pct', 'N/A')}%")

    # build ReviewPackage
    package = {
        # from Agent 2
        "cluster_id"            : draft["cluster_id"],
        "topic"                 : draft["topic"],
        "category"              : draft["category"],
        "subcategory"           : draft["subcategory"],
        "article_content"       : draft["article_content"],
        "source_ticket_ids"     : draft["source_ticket_ids"],
        "rag_ticket_ids"        : draft["rag_ticket_ids"],
        "ticket_count"          : draft["ticket_count"],
        "avg_resolution_hrs"    : draft["avg_resolution_hrs"],

        # SME recommendation
        "sme_assignee"          : draft["sme_assignee"],
        "sme_team"              : draft["sme_team"],

        # from Agent 3 review
        "confidence_score"      : review.get("confidence_score", 0),
        "flags"                 : review.get("flags", []),
        "estimated_deflection_pct": review.get("estimated_deflection_pct", 0),
        "deflection_reasoning"  : review.get("deflection_reasoning", ""),

        # token tracking
        "tokens_used_draft"     : draft.get("tokens_used", 0),
        "tokens_used_review"    : tokens_used,
    }

    # save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"review_{draft['cluster_id']}_{draft['subcategory'].lower().replace(' ', '_')}.json"
    out_path = os.path.join(OUTPUT_DIR, filename)
    with open(out_path, "w") as f:
        json.dump(package, f, indent=2)

    print(f"[Agent 3] ReviewPackage saved -> {out_path}")
    return package


if __name__ == "__main__":
    # load draft from Agent 2 output
    draft_path = os.path.join(OUTPUT_DIR, "draft_CLU-00_vpn.json")
    if not os.path.exists(draft_path):
        raise FileNotFoundError("Run agent2_draft.py first.")

    with open(draft_path) as f:
        draft = json.load(f)

    package = run(draft)

    print("\n" + "=" * 60)
    print(f"Topic      : {package['topic']}")
    print(f"Confidence : {package['confidence_score']}/100")
    print(f"Deflection : ~{package['estimated_deflection_pct']}%")
    print(f"SME        : {package['sme_assignee']} ({package['sme_team']})")
    print(f"Flags ({len(package['flags'])}):")
    for flag in package["flags"]:
        print(f"  [{flag['type'].upper()}] {flag['description']}")
    print(f"\nReasoning  : {package['deflection_reasoning']}")