"""
Email notification for Lattice — sends a transactional alert
to the founder/sovrano whenever a new lead is captured.

Configuration via .env:
    LATTICE_SMTP_HOST       (default: smtps.aruba.it)
    LATTICE_SMTP_PORT       (default: 587, STARTTLS)
    LATTICE_SMTP_USER       (e.g. info@lattice-network.it)
    LATTICE_SMTP_PASS       (mailbox password)
    LATTICE_SMTP_FROM       (default: same as USER)
    LATTICE_SMTP_TO         (comma-separated recipients)
    LATTICE_SMTP_ENABLED    (0 to disable globally)

Failure is non-blocking: if SMTP is unreachable, the lead is still saved
and the user still receives a success response. Errors are logged.
"""
import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Optional

log = logging.getLogger("lattice.mailer")


def _bool_env(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip() not in ("0", "false", "False", "")


def send_lead_notification_email(lead: dict) -> Optional[str]:
    """Send a transactional email about a freshly captured lead.

    Returns the SMTP server response on success, None on (logged) failure.
    """
    if not _bool_env("LATTICE_SMTP_ENABLED"):
        log.debug("SMTP disabled by env, skipping notification")
        return None

    host = os.environ.get("LATTICE_SMTP_HOST", "smtps.aruba.it")
    port = int(os.environ.get("LATTICE_SMTP_PORT", "587"))
    user = os.environ.get("LATTICE_SMTP_USER")
    pwd = os.environ.get("LATTICE_SMTP_PASS")
    sender = os.environ.get("LATTICE_SMTP_FROM", user)
    recipients_raw = os.environ.get("LATTICE_SMTP_TO", user or "")

    if not (user and pwd and recipients_raw):
        log.warning("SMTP env vars missing (LATTICE_SMTP_USER/PASS/TO); skipping")
        return None

    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    role_hint = ""
    notes = (lead.get("notes") or "").strip()
    if notes.startswith("[ruolo:"):
        end = notes.find("]")
        if end > 0:
            role_hint = f" · {notes[1:end]}"

    subject = f"🔔 Nuova richiesta demo — {lead.get('company_name', 'N/A')}{role_hint}"

    plain = f"""Nuova richiesta demo ricevuta su lattice-network.it

Azienda:      {lead.get('company_name', '-')}
Contatto:     {lead.get('contact_name', '-')}
Email:        {lead.get('email', '-')}
Telefono:     {lead.get('phone') or '-'}
Dipendenti:   {lead.get('employees_range', '-')}
Settore:      {lead.get('industry', '-')}

Note:
{notes or '(nessuna)'}

Metadata:
  Lead ID:    {lead.get('lead_id', '-')}
  Ricevuto:   {lead.get('received_at', '-')}
  On-chain:   {f"block #{lead['block_index']} · {lead.get('tx_id','')[:16]}…" if lead.get('block_index') is not None else 'NON notarizzato (cap giornaliero)'}

Apri la dashboard:
  https://lattice-network.it/leads

— Sistema Lattice Network
"""

    html = f"""<!DOCTYPE html>
<html><body style="font-family:-apple-system,system-ui,sans-serif;background:#0a1020;color:#e8eaf0;padding:24px;">
<table cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background:#0f1626;border:1px solid rgba(212,175,95,0.3);">
  <tr><td style="background:linear-gradient(90deg,transparent,#d4af5f,transparent);height:2px;"></td></tr>
  <tr><td style="padding:24px;">
    <div style="font-family:monospace;font-size:10px;color:#d4af5f;letter-spacing:0.3em;">LATTICE NETWORK · NUOVO LEAD</div>
    <h1 style="font-size:24px;color:#fff;margin:8px 0 16px 0;">🔔 Nuova richiesta demo</h1>
    <p style="color:#a0a8b8;font-size:14px;margin:0 0 20px 0;"><strong style="color:#fff;">{lead.get('company_name','-')}</strong> ha richiesto una demo.</p>
    <table cellpadding="6" cellspacing="0" style="width:100%;font-size:13px;border-collapse:collapse;">
      <tr><td style="color:#a0a8b8;width:120px;">Contatto</td><td style="color:#fff;"><strong>{lead.get('contact_name','-')}</strong></td></tr>
      <tr><td style="color:#a0a8b8;">Email</td><td><a href="mailto:{lead.get('email','')}" style="color:#d4af5f;">{lead.get('email','-')}</a></td></tr>
      <tr><td style="color:#a0a8b8;">Telefono</td><td style="color:#fff;">{lead.get('phone') or '-'}</td></tr>
      <tr><td style="color:#a0a8b8;">Dipendenti</td><td style="color:#fff;">{lead.get('employees_range','-')}</td></tr>
      <tr><td style="color:#a0a8b8;">Settore</td><td style="color:#fff;">{lead.get('industry','-')}</td></tr>
    </table>
    {f'<div style="margin-top:16px;padding:12px;border-left:2px solid #d4af5f;background:rgba(212,175,95,0.05);font-size:13px;color:#e8eaf0;">{notes}</div>' if notes else ''}
    <div style="margin-top:24px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.08);font-family:monospace;font-size:11px;color:#6b7080;">
      Lead ID: {lead.get('lead_id','-')}<br>
      {f"On-chain: block #{lead['block_index']} · tx {lead.get('tx_id','')[:24]}…" if lead.get('block_index') is not None else "On-chain: non notarizzato (cap)"}
    </div>
    <div style="margin-top:24px;text-align:center;">
      <a href="https://lattice-network.it/leads" style="display:inline-block;background:#d4af5f;color:#0a1020;text-decoration:none;padding:12px 24px;font-weight:600;font-size:13px;letter-spacing:0.05em;text-transform:uppercase;">Apri Dashboard →</a>
    </div>
  </td></tr>
</table>
<div style="text-align:center;font-family:monospace;font-size:10px;color:#6b7080;margin-top:16px;">
  LATTICE NETWORK · CORPORATE COMMUNICATION CONTROL LAYER
</div>
</body></html>
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Reply-To"] = lead.get("email") or sender
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15) as s:
                s.login(user, pwd)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as s:
                s.starttls()
                s.login(user, pwd)
                s.send_message(msg)
        log.info("lead notification email sent for %s to %s", lead.get("lead_id"), recipients)
        return "ok"
    except Exception as e:
        log.warning("lead notification email FAILED for %s: %s", lead.get("lead_id"), e)
        return None
