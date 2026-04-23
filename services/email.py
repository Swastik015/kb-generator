import smtplib
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import GMAIL_USER, MAILTRAP_USER, MAILTRAP_PASSWORD, KM_EMAIL


def _build_html(package: dict) -> str:
    flags_html = "".join([
        f"""<tr>
              <td style='padding:6px 12px;color:#b91c1c;font-weight:600;
                         text-transform:uppercase;font-size:12px;width:120px'>
                {f['type']}
              </td>
              <td style='padding:6px 12px;color:#374151;font-size:13px'>
                {f['description']}
              </td>
            </tr>"""
        for f in package.get("flags", [])
    ]) or "<tr><td colspan='2' style='padding:6px 12px;color:#6b7280'>No flags raised</td></tr>"

    tickets_html = ", ".join(package["source_ticket_ids"])
    article_html = package["article_content"].replace("\n", "<br>")

    return f"""
    <html><body style='font-family:Arial,sans-serif;max-width:800px;margin:0 auto;color:#111'>
      <div style='background:#1e3a5f;padding:24px 32px;border-radius:8px 8px 0 0'>
        <p style='color:#93c5fd;font-size:11px;letter-spacing:3px;
                  text-transform:uppercase;margin:0 0 6px'>KB Draft Ready for Review</p>
        <h1 style='color:#fff;font-size:22px;margin:0'>{package['topic']}</h1>
      </div>

      <div style='background:#f0f7ff;padding:16px 32px;border:1px solid #bfdbfe'>
        <table style='width:100%'><tr>
          <td><p style='font-size:11px;color:#6b7280;margin:0'>CATEGORY</p>
              <p style='font-size:14px;font-weight:600;margin:2px 0'>
                {package['category']} / {package['subcategory']}</p></td>
          <td><p style='font-size:11px;color:#6b7280;margin:0'>TICKETS</p>
              <p style='font-size:14px;font-weight:600;margin:2px 0'>
                {package['ticket_count']}</p></td>
          <td><p style='font-size:11px;color:#6b7280;margin:0'>CONFIDENCE</p>
              <p style='font-size:14px;font-weight:600;margin:2px 0;color:#059669'>
                {package['confidence_score']}/100</p></td>
          <td><p style='font-size:11px;color:#6b7280;margin:0'>EST. DEFLECTION</p>
              <p style='font-size:14px;font-weight:600;margin:2px 0;color:#059669'>
                ~{package['estimated_deflection_pct']}%</p></td>
          <td><p style='font-size:11px;color:#6b7280;margin:0'>AVG RESOLUTION</p>
              <p style='font-size:14px;font-weight:600;margin:2px 0'>
                {package['avg_resolution_hrs']} hrs</p></td>
        </tr></table>
      </div>

      <div style='padding:24px 32px;border:1px solid #e5e7eb;border-top:none'>
        <h2 style='font-size:15px;color:#1e3a5f;margin:0 0 16px'>Draft KB Article</h2>
        <div style='background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;
                    padding:20px 24px;font-size:14px;line-height:1.7;color:#374151'>
          {article_html}
        </div>
      </div>

      <div style='padding:16px 32px;background:#f0fdf4;border:1px solid #bbf7d0;
                  border-top:none'>
        <h2 style='font-size:13px;color:#065f46;margin:0 0 8px;
                   text-transform:uppercase;letter-spacing:2px'>Suggested SME Reviewer</h2>
        <p style='font-size:15px;font-weight:600;color:#065f46;margin:0'>
          {package['sme_assignee']}
          <span style='font-weight:400;color:#6b7280'>({package['sme_team']})</span>
        </p>
      </div>

      <div style='padding:16px 32px;border:1px solid #e5e7eb;border-top:none'>
        <h2 style='font-size:13px;color:#7f1d1d;margin:0 0 8px;
                   text-transform:uppercase;letter-spacing:2px'>
          Review Flags ({len(package.get('flags', []))})
        </h2>
        <table style='width:100%;border-collapse:collapse'>{flags_html}</table>
        <p style='font-size:12px;color:#6b7280;margin:12px 0 0'>
          {package.get('deflection_reasoning', '')}
        </p>
      </div>

      <div style='padding:16px 32px;background:#f9fafb;border:1px solid #e5e7eb;
                  border-top:none;border-radius:0 0 8px 8px'>
        <h2 style='font-size:13px;color:#374151;margin:0 0 8px;
                   text-transform:uppercase;letter-spacing:2px'>Source Tickets</h2>
        <p style='font-size:13px;color:#6b7280;margin:0;
                  font-family:monospace;line-height:1.8'>{tickets_html}</p>
      </div>
    </body></html>
    """


def send(package: dict):
    """Send ReviewPackage as formatted HTML email via Mailtrap."""
    print(f"\n[Email] Sending draft for: {package['topic']} ...")

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"[KB Draft] {package['topic']} · "
        f"Confidence {package['confidence_score']}/100 · "
        f"~{package['estimated_deflection_pct']}% deflection"
    )
    msg["From"]    = GMAIL_USER
    msg["To"]      = KM_EMAIL

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

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(_build_html(package), "html"))

    with smtplib.SMTP("sandbox.smtp.mailtrap.io", 2525) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(MAILTRAP_USER, MAILTRAP_PASSWORD)
        smtp.sendmail(GMAIL_USER, KM_EMAIL, msg.as_string())
    time.sleep(2)
    print(f"[Email] ✓ Sent successfully")
    print(f"[Email]   Check: https://mailtrap.io/inboxes")
    print(f"[Email]   Subject: {msg['Subject']}")


if __name__ == "__main__":
    import os
    from config import OUTPUT_DIR

    review_path = os.path.join(OUTPUT_DIR, "review_CLU-00_vpn.json")
    if not os.path.exists(review_path):
        raise FileNotFoundError("Run agent3_review.py first.")

    with open(review_path) as f:
        package = json.load(f)

    send(package)