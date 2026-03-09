"""Email alerts via Resend."""
import resend
from app.config import settings

resend.api_key = settings.resend_api_key

async def send_alert(to_email: str, user_name: str, new_calls: list[dict], source_label: str):
    calls_html = "".join([
        f"""<li style="margin-bottom:12px">
            <strong><a href="{c['url']}">{c['title']}</a></strong>
            {f"<br><small>Deadline: {c['deadline']}</small>" if c.get('deadline') else ""}
            {f"<br>{c['summary']}" if c.get('summary') else ""}
        </li>"""
        for c in new_calls
    ])

    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
        <h2 style="color:#1a1a2e">🔔 New funding calls — {source_label}</h2>
        <p>Hi {user_name or 'there'},</p>
        <p>We found <strong>{len(new_calls)} new call(s)</strong> matching your monitored source:</p>
        <ul style="padding-left:20px">{calls_html}</ul>
        <hr>
        <p style="color:#888;font-size:12px">
            FundWatch by <a href="https://sustainovate.com">Sustainovate AS</a> ·
            <a href="#">Manage sources</a> · <a href="#">Unsubscribe</a>
        </p>
    </div>
    """

    resend.Emails.send({
        "from": settings.email_from,
        "to": [to_email],
        "subject": f"[FundWatch] {len(new_calls)} new call(s) from {source_label}",
        "html": html,
    })
