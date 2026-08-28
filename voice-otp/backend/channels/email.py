import os
import smtplib
import ssl
from email.message import EmailMessage


def _settings():
    host = os.getenv("SMTP_HOST", "")
    port = os.getenv("SMTP_PORT", "")
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASS", "")
    sender = os.getenv("SMTP_FROM", "")

    try:
        import smtp_config as cfg

        host = host or getattr(cfg, "SMTP_HOST", "")
        port = port or str(getattr(cfg, "SMTP_PORT", 587))
        user = user or getattr(cfg, "SMTP_USER", "")
        password = password or getattr(cfg, "SMTP_PASS", "")
        sender = sender or getattr(cfg, "SMTP_FROM", "") or user
    except Exception:
        port = port or "587"
        sender = sender or user

    return {
        "host": (host or "").strip(),
        "port": int(port or 587),
        "user": (user or "").strip(),
        "password": (password or "").replace(" ", "").strip(),
        "sender": (sender or user or "").strip(),
    }


def send_email(to_address, otp_code):
    to_address = (to_address or "").strip()
    if not to_address or "@" not in to_address:
        return False, "Adresse e-mail destinataire invalide."

    cfg = _settings()
    if not cfg["host"] or not cfg["user"] or not cfg["password"]:
        return False, (
            "Le compte d'envoi n'est pas configuré. "
            "Remplis SMTP_USER et SMTP_PASS dans backend/.env "
            "(Gmail + mot de passe d'application)."
        )

    msg = EmailMessage()
    msg["Subject"] = "Votre code de vérification"
    msg["From"] = cfg["sender"]
    msg["To"] = to_address
    msg.set_content(
        f"Votre code de vérification est : {otp_code}\n"
        "Il expire dans 3 minutes.\n"
    )
    msg.add_alternative(
        f"""
        <html>
          <body style="font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;padding:24px;">
            <div style="max-width:420px;margin:auto;background:#1e293b;border-radius:12px;padding:28px;">
              <p style="margin:0 0 12px;">Votre code de vérification :</p>
              <p style="margin:0;font-size:32px;letter-spacing:10px;font-weight:bold;color:#38bdf8;">{otp_code}</p>
              <p style="margin:16px 0 0;color:#94a3b8;font-size:13px;">Ce code expire dans 3 minutes.</p>
            </div>
          </body>
        </html>
        """,
        subtype="html",
    )

    try:
        context = ssl.create_default_context()
        if cfg["port"] == 465:
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=20, context=context) as smtp:
                smtp.login(cfg["user"], cfg["password"])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
                smtp.login(cfg["user"], cfg["password"])
                smtp.send_message(msg)
        print("[EMAIL] message délivré à la boîte du destinataire")
        return True, "sent"
    except smtplib.SMTPAuthenticationError:
        return False, (
            "Authentification SMTP refusée. Vérifiez SMTP_USER et SMTP_PASS dans backend/.env."
        )
    except Exception as e:
        print(f"[EMAIL] échec d'envoi: {type(e).__name__}")
        return False, "Impossible d'envoyer l'e-mail. Vérifiez la configuration SMTP et le réseau."
