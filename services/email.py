import time
import json
import re
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from config import SENDGRID_API_KEY, SENDGRID_FROM_EMAIL, KM_EMAIL


def _md_to_html(text: str) -> str:
    """Convert basic markdown to HTML for email rendering."""
    # bold **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # line breaks
    text = text.replace('\n', '<br>')
    return text


def _build_html(package: dict) -> str:
    flags_html = "".join([
        f"""<tr>
              <td style='padding:8px 12px;color:#b91c1c;font-weight:700;
                         text-transform:uppercase;font-size:11px;width:130px;
                         vertical-align:top'>
                {f['type']}
              </td>
              <td style='padding:8px 12px;color:#374151;font-size:13px;
                         vertical-align:top;border-left:1px solid #fee2e2'>
                {f['description']}
              </td>
            </tr>"""
        for f in package.get("flags", [])
    ]) or "<tr><td colspan='2' style='padding:8px 12px;color:#6b7280;font-style:italic'>No flags raised ✓</td></tr>"

    tickets_html = "".join([
        f"<span style='display:inline-block;background:#f1f5f9;border:1px solid #e2e8f0;"
        f"border-radius:4px;padding:2px 8px;margin:2px;font-family:monospace;font-size:12px;"
        f"color:#475569'>{tid}</span>"
        for tid in package["source_ticket_ids"]
    ])

    article_html = _md_to_html(package["article_content"])

    return f"""
    <!DOCTYPE html>
    <html>
    <body style='margin:0;padding:20px;background:#f8fafc;font-family:Arial,sans-serif'>
    <div style='max-width:680px;margin:0 auto;background:#ffffff;border-radius:12px;
                overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)'>

      <!-- Header -->
      <div style='background:#1e3a5f;padding:28px 32px'>
        <p style='color:#93c5fd;font-size:10px;letter-spacing:4px;text-transform:uppercase;
                  margin:0 0 8px 0'>KB Draft Ready for Review</p>
        <h1 style='color:#ffffff;font-size:24px;margin:0;font-weight:700'>
          {package['topic']}
        </h1>
      </div>

      <!-- Metrics strip -->
      <div style='background:#f0f7ff;padding:16px 32px;border-bottom:1px solid #bfdbfe'>
        <table style='width:100%;border-collapse:collapse'>
          <tr>
            <td style='padding:0 16px 0 0;border-right:1px solid #bfdbfe'>
              <p style='font-size:10px;color:#6b7280;text-transform:uppercase;
                        letter-spacing:1px;margin:0 0 4px 0'>Category</p>
              <p style='font-size:14px;font-weight:700;color:#1e3a5f;margin:0'>
                {package['category']} / {package['subcategory']}
              </p>
            </td>
            <td style='padding:0 16px;border-right:1px solid #bfdbfe'>
              <p style='font-size:10px;color:#6b7280;text-transform:uppercase;
                        letter-spacing:1px;margin:0 0 4px 0'>Tickets</p>
              <p style='font-size:20px;font-weight:700;color:#1e3a5f;margin:0'>
                {package['ticket_count']}
              </p>
            </td>
            <td style='padding:0 16px;border-right:1px solid #bfdbfe'>
              <p style='font-size:10px;color:#6b7280;text-transform:uppercase;
                        letter-spacing:1px;margin:0 0 4px 0'>Confidence</p>
              <p style='font-size:20px;font-weight:700;color:#059669;margin:0'>
                {package['confidence_score']}/100
              </p>
            </td>
            <td style='padding:0 16px;border-right:1px solid #bfdbfe'>
              <p style='font-size:10px;color:#6b7280;text-transform:uppercase;
                        letter-spacing:1px;margin:0 0 4px 0'>Est. Deflection</p>
              <p style='font-size:20px;font-weight:700;color:#059669;margin:0'>
                ~{package['estimated_deflection_pct']}%
              </p>
            </td>
            <td style='padding:0 0 0 16px'>
              <p style='font-size:10px;color:#6b7280;text-transform:uppercase;
                        letter-spacing:1px;margin:0 0 4px 0'>Avg Resolution</p>
              <p style='font-size:20px;font-weight:700;color:#1e3a5f;margin:0'>
                {package['avg_resolution_hrs']} hrs
              </p>
            </td>
          </tr>
        </table>
      </div>

      <!-- Article -->
      <div style='padding:28px 32px;border-bottom:1px solid #e5e7eb'>
        <h2 style='font-size:13px;color:#1e3a5f;text-transform:uppercase;letter-spacing:2px;
                   margin:0 0 16px 0'>Draft KB Article</h2>
        <div style='background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;
                    padding:24px;font-size:14px;line-height:1.8;color:#374151'>
          {article_html}
        </div>
      </div>

      <!-- SME -->
      <div style='padding:20px 32px;background:#f0fdf4;border-bottom:1px solid #bbf7d0'>
        <h2 style='font-size:11px;color:#065f46;text-transform:uppercase;letter-spacing:2px;
                   margin:0 0 8px 0'>Suggested SME Reviewer</h2>
        <p style='margin:0'>
          <span style='font-size:16px;font-weight:700;color:#065f46'>
            {package['sme_assignee']}
          </span>
          <span style='font-size:13px;color:#6b7280;margin-left:8px'>
            {package['sme_team']}
          </span>
        </p>
        <p style='font-size:12px;color:#6b7280;margin:4px 0 0 0'>
          Most frequent resolver of this issue type
        </p>
      </div>

      <!-- Flags -->
      <div style='padding:20px 32px;border-bottom:1px solid #e5e7eb'>
        <h2 style='font-size:11px;color:#7f1d1d;text-transform:uppercase;letter-spacing:2px;
                   margin:0 0 12px 0'>
          Review Flags ({len(package.get('flags', []))})
        </h2>
        <table style='width:100%;border-collapse:collapse;background:#fff5f5;
                      border:1px solid #fee2e2;border-radius:6px'>
          {flags_html}
        </table>
        <p style='font-size:12px;color:#6b7280;margin:10px 0 0 0;font-style:italic'>
          {package.get('deflection_reasoning', '')}
        </p>
      </div>

      <!-- Source tickets -->
      <div style='padding:20px 32px;background:#f9fafb;border-radius:0 0 12px 12px'>
        <h2 style='font-size:11px;color:#374151;text-transform:uppercase;letter-spacing:2px;
                   margin:0 0 12px 0'>Source Tickets</h2>
        <div>{tickets_html}</div>
      </div>

    </div>
    </body></html>
    """


def send(package: dict):
    """Send ReviewPackage via SendGrid HTTP API."""
    print(f"\n[Email] Sending draft for: {package['topic']} ...")

    subject = (
        f"[KB Draft] {package['topic']} · "
        f"Confidence {package['confidence_score']}/100 · "
        f"~{package['estimated_deflection_pct']}% deflection"
    )

    plain = f"""
KB Draft: {package['topic']}
Confidence : {package['confidence_score']}/100
Deflection : ~{package['estimated_deflection_pct']}%
SME        : {package['sme_assignee']} ({package['sme_team']})
Tickets    : {', '.join(package['source_ticket_ids'])}

Flags:
{chr(10).join(f"  [{f['type'].upper()}] {f['description']}" for f in package.get('flags', []))}

Article:
{package['article_content']}
    """.strip()

    message = Mail(
        from_email         = SENDGRID_FROM_EMAIL,
        to_emails          = KM_EMAIL,
        subject            = subject,
        plain_text_content = plain,
        html_content       = _build_html(package)
    )

    sg = SendGridAPIClient(SENDGRID_API_KEY)
    response = sg.send(message)

    print(f"[Email] ✓ Sent — status: {response.status_code}")
    print(f"[Email]   To: {KM_EMAIL}")
    print(f"[Email]   Subject: {subject}")

    time.sleep(3)   # avoid rate limiting between 4 emails


if __name__ == "__main__":
    import os
    from config import OUTPUT_DIR
    review_path = os.path.join(OUTPUT_DIR, "review_CLU-00_vpn.json")
    if not os.path.exists(review_path):
        raise FileNotFoundError("Run agent3_review.py first.")
    with open(review_path) as f:
        package = json.load(f)
    send(package)