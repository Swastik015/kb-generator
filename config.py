import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM ─────────────────────────────────────────────────────
OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL        = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ── Paths ────────────────────────────────────────────────────
CSV_PATH            = os.getenv("CSV_PATH",    "tickets.csv")
DB_PATH             = os.getenv("DB_PATH",     "data/tickets.db")
CHROMA_PATH         = os.getenv("CHROMA_PATH", "data/chroma")
OUTPUT_DIR          = os.getenv("OUTPUT_DIR",  "outputs")

# ── Embedding ────────────────────────────────────────────────
EMBED_MODEL         = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")

# ── Pipeline ─────────────────────────────────────────────────
CLUSTER_THRESHOLD   = int(os.getenv("THRESHOLD",         "5"))
TOP_K_RAG           = int(os.getenv("TOP_K_RAG",         "5"))

# ── DBSCAN ───────────────────────────────────────────────────
DBSCAN_EPS          = float(os.getenv("DBSCAN_EPS",       "0.60"))
DBSCAN_MIN_SAMPLES  = int(os.getenv("DBSCAN_MIN_SAMPLES", "2"))

# ── Email — SendGrid ─────────────────────────────────────────
SENDGRID_API_KEY    = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "testingagenticaidemo@gmail.com")
KM_EMAIL            = os.getenv("KM_EMAIL",            "testingagenticaidemo@gmail.com")


if __name__ == "__main__":
    print("✓ Config loaded")
    print(f"  OpenAI model      : {OPENAI_MODEL}")
    print(f"  Embed model       : {EMBED_MODEL}")
    print(f"  Threshold         : {CLUSTER_THRESHOLD}")
    print(f"  DBSCAN eps        : {DBSCAN_EPS}")
    print(f"  SendGrid from     : {SENDGRID_FROM_EMAIL}")
    print(f"  KM email          : {KM_EMAIL}")