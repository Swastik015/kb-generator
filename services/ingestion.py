import os
import sqlite3
import pandas as pd
from datetime import datetime
from config import CSV_PATH, DB_PATH

REQUIRED_COLUMNS = [
    "ticket_id", "title", "description", "resolution",
    "category", "subcategory", "priority", "status",
    "assignee", "assignee_team", "created_at", "resolved_at",
    "resolution_time_hrs", "tags"
]

VALID_STATUSES = {"closed", "resolved"}


def _ensure_dirs():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def _validate(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.lower().str.replace(" ", "_")

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing columns: {missing}")

    n = len(df)
    df = df[df["status"].str.lower().isin(VALID_STATUSES)].copy()
    print(f"  Status filter     : {n} -> {len(df)} rows")

    df = df[df["resolution"].notna() & (df["resolution"].str.strip() != "")].copy()
    print(f"  Resolution filter : {len(df)} rows")

    df = df[df["title"].notna() & df["description"].notna()].copy()
    print(f"  Title/desc filter : {len(df)} rows")

    return df.reset_index(drop=True)


def _to_dicts(df: pd.DataFrame) -> list[dict]:
    tickets = []
    for _, row in df.iterrows():
        tickets.append({
            "ticket_id"           : str(row["ticket_id"]).strip(),
            "title"               : str(row["title"]).strip(),
            "description"         : str(row["description"]).strip(),
            "resolution"          : str(row["resolution"]).strip(),
            "category"            : str(row["category"]).strip(),
            "subcategory"         : str(row["subcategory"]).strip(),
            "priority"            : str(row["priority"]).strip(),
            "status"              : str(row["status"]).strip().lower(),
            "assignee"            : str(row["assignee"]).strip(),
            "assignee_team"       : str(row["assignee_team"]).strip(),
            "created_at"          : str(row["created_at"]).strip(),
            "resolved_at"         : str(row["resolved_at"]).strip(),
            "resolution_time_hrs" : float(row["resolution_time_hrs"]),
            "tags"                : str(row["tags"]).strip(),
            # composite string Agent 1 embeds into a vector
            "embed_text"          : (
                f"{row['title']}. "
                f"{row['description']} "
                f"Resolution: {row['resolution']}"
            ).strip()
        })
    return tickets


def _save_to_db(tickets: list[dict]):
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id            TEXT PRIMARY KEY,
            title                TEXT,
            description          TEXT,
            resolution           TEXT,
            category             TEXT,
            subcategory          TEXT,
            priority             TEXT,
            status               TEXT,
            assignee             TEXT,
            assignee_team        TEXT,
            created_at           TEXT,
            resolved_at          TEXT,
            resolution_time_hrs  REAL,
            tags                 TEXT,
            embed_text           TEXT,
            ingested_at          TEXT
        )
    """)
    now = datetime.utcnow().isoformat()
    for t in tickets:
        cur.execute("""
            INSERT OR REPLACE INTO tickets VALUES (
                :ticket_id, :title, :description, :resolution,
                :category, :subcategory, :priority, :status,
                :assignee, :assignee_team, :created_at, :resolved_at,
                :resolution_time_hrs, :tags, :embed_text, :ingested_at
            )
        """, {**t, "ingested_at": now})
    conn.commit()
    conn.close()
    print(f"  SQLite saved      : {len(tickets)} tickets -> {DB_PATH}")


# ── public API ─────────────────────────────────────────────

def load_tickets(csv_path: str = CSV_PATH) -> list[dict]:
    """
    Read CSV -> validate -> normalise -> save to SQLite -> return list of dicts.
    Each dict contains 'embed_text' ready for Agent 1 to embed.
    """
    print(f"\n[Ingestion] Reading {csv_path} ...")
    _ensure_dirs()
    df      = pd.read_csv(csv_path, dtype=str).fillna("")
    df      = _validate(df)
    tickets = _to_dicts(df)
    _save_to_db(tickets)
    print(f"[Ingestion] done - {len(tickets)} clean tickets ready\n")
    return tickets


def get_tickets_by_ids(ticket_ids: list[str]) -> list[dict]:
    """
    Fetch specific tickets from SQLite by ID.
    Used by Agent 2 for RAG retrieval.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()
    placeholders = ",".join("?" * len(ticket_ids))
    rows = cur.execute(
        f"SELECT * FROM tickets WHERE ticket_id IN ({placeholders})",
        ticket_ids
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    tickets = load_tickets()
    t = tickets[0]
    print(f"  ID         : {t['ticket_id']}")
    print(f"  Title      : {t['title']}")
    print(f"  Category   : {t['category']} / {t['subcategory']}")
    print(f"  Assignee   : {t['assignee']} ({t['assignee_team']})")
    print(f"  Embed text : {t['embed_text'][:100]}...")