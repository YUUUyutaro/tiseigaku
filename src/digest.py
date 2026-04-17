"""日次ダイジェストメールを組み立てて SMTP で送るスタンドアロン CLI。

使い方:
    python -m src.digest --manifest docs/reports/2026-04-17.json \
                         --site-url https://example.github.io/tiseigaku/ \
                         [--dry-run]

SMTP 情報と宛先は環境変数から取る(リポジトリに値を書かない設計):
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
    MAIL_TO   (カンマ区切りの宛先リスト; 必須)
    MAIL_FROM (任意; 未指定なら SMTP_USER を流用)

--dry-run を付けると、件名・本文を stdout に書き出すだけで送信しない。
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path
from typing import List, Tuple

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "templates"

log = logging.getLogger("digest")


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "htm", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def build_digest(manifest: dict, site_url: str) -> Tuple[str, str, str]:
    """manifest と site_url から (subject, html_body, text_body) を組み立てる。"""
    slug = manifest.get("slug", "unknown")
    count = manifest.get("count", len(manifest.get("headlines", [])))
    headlines = manifest.get("headlines", [])

    site_url = site_url.rstrip("/") + "/"
    report_url = f"{site_url}reports/{slug}.html"

    subject = f"地政学ニュース図解 {slug} 号 ({count}本)"
    ctx = {
        "subject": subject,
        "date_label": slug,
        "headlines": headlines,
        "report_url": report_url,
        "site_url": site_url,
    }
    env = _env()
    html_body = env.get_template("digest.html.j2").render(**ctx)
    text_body = env.get_template("digest.txt.j2").render(**ctx)
    return subject, html_body, text_body


def _parse_recipients(raw: str) -> List[str]:
    return [addr.strip() for addr in raw.replace(";", ",").split(",") if addr.strip()]


def send_email(
    *,
    subject: str,
    html_body: str,
    text_body: str,
    mail_from: str,
    recipients: List[str],
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = ", ".join(recipients)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as s:
            s.login(smtp_user, smtp_password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.ehlo()
            s.starttls(context=context)
            s.ehlo()
            s.login(smtp_user, smtp_password)
            s.send_message(msg)


def run(argv: List[str]) -> int:
    p = argparse.ArgumentParser(description="地政学ニュース図解 日次ダイジェストメーラ")
    p.add_argument("--manifest", type=Path, required=True, help="対象号の manifest JSON")
    p.add_argument(
        "--site-url",
        default=os.environ.get("SITE_URL", ""),
        help="サイトのベース URL (env SITE_URL でも可)",
    )
    p.add_argument("--dry-run", action="store_true", help="送信せず本文を表示")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    if not args.manifest.exists():
        log.error("manifest not found: %s", args.manifest)
        return 2
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))

    site_url = args.site_url or "https://example.invalid/"
    if not args.site_url:
        log.warning("--site-url / SITE_URL 未設定。プレースホルダ URL を使用します。")

    subject, html_body, text_body = build_digest(manifest, site_url)

    if args.dry_run:
        sys.stdout.write(f"[DRY RUN]\nSubject: {subject}\n\n--- text ---\n{text_body}\n")
        sys.stdout.write(f"\n--- html ({len(html_body)} bytes) ---\n")
        sys.stdout.write(html_body[:500] + ("…\n" if len(html_body) > 500 else "\n"))
        return 0

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    mail_from = os.environ.get("MAIL_FROM") or smtp_user or ""
    recipients = _parse_recipients(os.environ.get("MAIL_TO", ""))

    missing = [
        name
        for name, val in [
            ("SMTP_HOST", smtp_host),
            ("SMTP_USER", smtp_user),
            ("SMTP_PASSWORD", smtp_password),
            ("MAIL_TO", recipients),
        ]
        if not val
    ]
    if missing:
        log.error("必須の環境変数が未設定: %s", ", ".join(missing))
        return 2

    log.info(
        "Sending digest '%s' via %s:%d to %d recipient(s)",
        subject,
        smtp_host,
        smtp_port,
        len(recipients),
    )
    send_email(
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        mail_from=mail_from,
        recipients=recipients,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
    )
    log.info("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
