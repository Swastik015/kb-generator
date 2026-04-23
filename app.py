import streamlit as st
import json
import os
import pandas as pd
import time
from config import OUTPUT_DIR

st.set_page_config(
    page_title  = "KB Article Generator",
    page_icon   = "🧠",
    layout      = "wide",
    initial_sidebar_state = "collapsed"
)

# ── custom CSS ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'JetBrains Mono', monospace;
    background-color: #0c0e14;
    color: #e2e8f0;
}
.main { background-color: #0c0e14; }

h1, h2, h3 { font-family: 'Syne', sans-serif; }

.stButton > button {
    background: linear-gradient(135deg, #3b82f6, #1d4ed8);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 12px 32px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 1px;
    width: 100%;
    transition: all 0.2s;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #2563eb, #1e40af);
    transform: translateY(-1px);
}

.metric-card {
    background: #12151e;
    border: 1px solid #1e2333;
    border-radius: 10px;
    padding: 16px 20px;
    margin: 6px 0;
}
.metric-label {
    font-size: 10px;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #475569;
    margin-bottom: 4px;
}
.metric-value {
    font-family: 'Syne', sans-serif;
    font-size: 22px;
    font-weight: 700;
    color: #e2e8f0;
}
.cluster-card {
    background: #12151e;
    border: 1px solid #1e2333;
    border-left: 3px solid #3b82f6;
    border-radius: 10px;
    padding: 20px 24px;
    margin: 12px 0;
}
.agent-step {
    background: #0f1219;
    border: 1px solid #1e2333;
    border-radius: 8px;
    padding: 10px 16px;
    margin: 4px 0;
    font-size: 13px;
}
.flag-item {
    background: #1a0b0e;
    border: 1px solid #3a1520;
    border-radius: 6px;
    padding: 8px 12px;
    margin: 4px 0;
    font-size: 12px;
    color: #fca5a5;
}
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
}
.badge-blue   { background:#1e3a5f; color:#60a5fa; }
.badge-green  { background:#052e16; color:#4ade80; }
.badge-amber  { background:#1a1200; color:#fbbf24; }
.badge-red    { background:#1a0b0e; color:#f87171; }
</style>
""", unsafe_allow_html=True)


# ── header ─────────────────────────────────────────────────
st.markdown("""
<div style='padding:32px 0 24px'>
  <div style='font-size:10px;letter-spacing:4px;text-transform:uppercase;
              color:#3b82f6;margin-bottom:8px'>Multi-Agent Pipeline</div>
  <h1 style='font-family:Syne,sans-serif;font-size:36px;font-weight:800;
             color:#f0f4ff;margin:0 0 8px'>KB Article Generator</h1>
  <p style='color:#475569;font-size:13px;margin:0'>
    Upload closed tickets → clusters detected → articles drafted → emailed to Knowledge Manager
  </p>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── sidebar — pipeline steps ────────────────────────────────
with st.sidebar:
    st.markdown("### Pipeline Steps")
    steps = [
        ("1", "Ingest + Embed",    "Read CSV, normalise, embed into vectors"),
        ("2", "Agent 1 — Cluster", "DBSCAN clustering, threshold check"),
        ("3", "Agent 2 — Draft",   "RAG retrieval + article generation"),
        ("4", "Agent 3 — Review",  "QA, flags, SME, deflection estimate"),
        ("5", "Email",             "Send ReviewPackage to Knowledge Manager"),
    ]
    for num, name, desc in steps:
        st.markdown(f"""
        <div class='agent-step'>
          <span style='color:#3b82f6;font-weight:600'>{num}.</span>
          <span style='color:#e2e8f0;font-weight:600'> {name}</span><br>
          <span style='color:#475569;font-size:11px'>{desc}</span>
        </div>
        """, unsafe_allow_html=True)

# ── main layout ─────────────────────────────────────────────
col_left, col_right = st.columns([1, 2], gap="large")

with col_left:
    st.markdown("#### Upload Tickets")
    uploaded = st.file_uploader(
        "Drop your tickets CSV here",
        type=["csv"],
        help="Must have columns: ticket_id, title, description, resolution, category, subcategory, priority, status, assignee, assignee_team, created_at, resolved_at, resolution_time_hrs, tags"
    )

    if uploaded:
        df = pd.read_csv(uploaded)
        st.markdown(f"""
        <div class='metric-card'>
          <div class='metric-label'>File loaded</div>
          <div class='metric-value'>{len(df)} tickets</div>
        </div>
        """, unsafe_allow_html=True)

        with open("tickets_upload.csv", "wb") as f:
            f.write(uploaded.getbuffer())

        with st.expander("Preview data"):
            st.dataframe(
                df[["ticket_id","title","category","subcategory","status"]].head(8),
                use_container_width=True
            )

    st.markdown("#### Or use sample data")
    use_sample = st.button("▶  Run with tickets.csv", use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    run_button = st.button(
        "🚀  Generate KB Articles",
        use_container_width=True,
        disabled=not (uploaded or use_sample)
    ) if (uploaded or use_sample) else st.button(
        "🚀  Generate KB Articles",
        use_container_width=True,
        disabled=True
    )

with col_right:
    st.markdown("#### Pipeline Output")

    if run_button or use_sample:
        csv_path = "tickets_upload.csv" if (uploaded and not use_sample) else "tickets.csv"

        progress = st.progress(0, text="Starting pipeline...")
        log_area = st.empty()
        logs     = []

        def log(msg):
            logs.append(msg)
            log_area.markdown(
                "<div style='background:#0f1219;border:1px solid #1e2333;"
                "border-radius:8px;padding:12px 16px;font-size:12px;"
                "color:#475569;max-height:180px;overflow-y:auto'>" +
                "<br>".join(logs[-12:]) +
                "</div>",
                unsafe_allow_html=True
            )

        try:
            log("📂 Loading tickets...")
            progress.progress(10, text="Ingesting tickets...")

            from services.ingestion    import load_tickets
            from services.vector_store import store_tickets
            from agents.agent1_cluster import run as run_agent1
            from agents.agent2_draft   import run as run_agent2
            from agents.agent3_review  import run as run_agent3
            from services.email        import send

            tickets = load_tickets(csv_path)
            log(f"✓ {len(tickets)} tickets loaded")
            progress.progress(20, text="Embedding tickets...")

            store_tickets(tickets)
            log("✓ Vectors stored in ChromaDB")
            progress.progress(35, text="Clustering...")

            clusters = run_agent1(tickets)
            log(f"✓ {len(clusters)} clusters found above threshold")
            progress.progress(50, text="Drafting articles...")

            results = []
            for i, cluster in enumerate(clusters):
                pct = 50 + int((i / len(clusters)) * 40)
                progress.progress(pct, text=f"Processing {cluster['topic']}...")
                log(f"→ Agent 2: Drafting [{cluster['cluster_id']}] {cluster['topic']}")

                draft   = run_agent2(cluster)
                log(f"→ Agent 3: Reviewing [{cluster['cluster_id']}]")

                package = run_agent3(draft)
                send(package)
                log(f"✓ Email sent for {cluster['topic']}")
                results.append(package)

            progress.progress(100, text="Pipeline complete!")
            time.sleep(0.5)
            progress.empty()
            log_area.empty()

            st.success(f"✅ Pipeline complete — {len(results)} articles generated and emailed")

            m1, m2, m3, m4 = st.columns(4)
            avg_conf = round(sum(r['confidence_score'] for r in results) / len(results))
            avg_defl = round(sum(r['estimated_deflection_pct'] for r in results) / len(results))
            total_tickets = sum(r['ticket_count'] for r in results)

            m1.metric("Clusters",    len(results))
            m2.metric("Avg Confidence", f"{avg_conf}/100")
            m3.metric("Avg Deflection", f"~{avg_defl}%")
            m4.metric("Tickets Used",  total_tickets)

            st.markdown("---")

            for r in results:
                color = "#22c55e" if r['confidence_score'] >= 80 else \
                        "#f59e0b" if r['confidence_score'] >= 60 else "#ef4444"

                st.markdown(f"""
                <div class='cluster-card' style='border-left-color:{color}'>
                  <div style='display:flex;justify-content:space-between;align-items:center'>
                    <div>
                      <span style='font-size:10px;letter-spacing:3px;
                                   text-transform:uppercase;color:#475569'>
                        {r['cluster_id']}
                      </span>
                      <h3 style='font-family:Syne,sans-serif;font-size:18px;
                                 color:#f0f4ff;margin:4px 0'>{r['topic']}</h3>
                    </div>
                    <div style='text-align:right'>
                      <div style='font-size:24px;font-weight:800;
                                  color:{color}'>{r['confidence_score']}/100</div>
                      <div style='font-size:11px;color:#475569'>confidence</div>
                    </div>
                  </div>
                  <div style='display:flex;gap:12px;margin:12px 0;flex-wrap:wrap'>
                    <span class='badge badge-blue'>{r['ticket_count']} tickets</span>
                    <span class='badge badge-green'>~{r['estimated_deflection_pct']}% deflection</span>
                    <span class='badge badge-amber'>SME: {r['sme_assignee']}</span>
                    <span class='badge badge-blue'>{r['avg_resolution_hrs']} hrs avg</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                if r.get("flags"):
                    with st.expander(f"⚠️  {len(r['flags'])} flag(s) — {r['cluster_id']}"):
                        for flag in r["flags"]:
                            st.markdown(f"""
                            <div class='flag-item'>
                              <strong>[{flag['type'].upper()}]</strong> {flag['description']}
                            </div>
                            """, unsafe_allow_html=True)

                with st.expander(f"📄  Article preview — {r['topic']}"):
                    st.markdown(r["article_content"])

            st.markdown("""
            <div style='margin-top:24px;padding:16px 20px;background:#0a1a0a;
                        border:1px solid #14532d;border-radius:8px;font-size:13px'>
              📬 <strong style='color:#4ade80'>Emails sent to Knowledge Manager</strong>
              <span style='color:#475569'> — check
                <a href='https://mailtrap.io/inboxes' target='_blank'
                   style='color:#3b82f6'>mailtrap.io/inboxes</a>
              </span>
            </div>
            """, unsafe_allow_html=True)

        except Exception as e:
            progress.empty()
            st.error(f"Pipeline error: {e}")
            st.exception(e)

    else:
        st.markdown("""
        <div style='text-align:center;padding:60px 20px;color:#1e2333'>
          <div style='font-size:48px;margin-bottom:16px'>🧠</div>
          <div style='font-family:Syne,sans-serif;font-size:18px;
                      color:#1e2a40;margin-bottom:8px'>
            Upload a CSV or click Run with sample data
          </div>
          <div style='font-size:12px;color:#1a2030'>
            Pipeline will cluster tickets, draft KB articles,<br>
            review them and email to Knowledge Manager
          </div>
        </div>
        """, unsafe_allow_html=True)