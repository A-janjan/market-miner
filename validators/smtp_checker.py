"""Async email validator with DNS MX checks and optional SMTP handshake.

The SMTP probe does not send email DATA. It opens a connection, performs HELO,
MAIL FROM, and RCPT TO, then quits. Many enterprise servers use catch-all,
greylisting, or anti-enumeration protections, so results should be interpreted as
signals rather than guarantees.
"""
from __future__ import annotations

import asyncio
import smtplib
from dataclasses import dataclass
from email_validator import EmailNotValidError, validate_email

import dns.resolver


@dataclass
class EmailCheckResult:
    email: str
    syntax_valid: bool
    domain: str | None = None
    mx_records: list[str] | None = None
    status: str = "Unverified"
    detail: str = ""


async def lookup_mx(domain: str, timeout: float = 5.0) -> list[str]:
    def _lookup() -> list[str]:
        resolver = dns.resolver.Resolver()
        resolver.lifetime = timeout
        answers = resolver.resolve(domain, "MX")
        return [str(r.exchange).rstrip(".") for r in sorted(answers, key=lambda r: r.preference)]

    return await asyncio.to_thread(_lookup)


async def smtp_handshake(email: str, mx_host: str, timeout: float = 8.0) -> tuple[str, str]:
    """Perform a non-sending SMTP RCPT probe."""
    def _probe() -> tuple[str, str]:
        with smtplib.SMTP(mx_host, 25, timeout=timeout) as smtp:
            smtp.helo("marketminer.local")
            smtp.mail("probe@marketminer.local")
            code, msg = smtp.rcpt(email)
            smtp.quit()
            if 200 <= code < 300:
                return "SMTP_handshake_accepted", msg.decode(errors="ignore") if isinstance(msg, bytes) else str(msg)
            return "SMTP_rejected", f"{code} {msg!r}"

    return await asyncio.to_thread(_probe)


async def check_email(email: str, do_smtp: bool = False, timeout: float = 8.0) -> EmailCheckResult:
    try:
        valid = validate_email(email, check_deliverability=False)
    except EmailNotValidError as exc:
        return EmailCheckResult(email=email, syntax_valid=False, status="Unverified", detail=str(exc))

    normalized = valid.normalized
    domain = normalized.split("@", 1)[1]
    result = EmailCheckResult(email=normalized, syntax_valid=True, domain=domain, status="Syntax_Validated")

    try:
        mx_records = await lookup_mx(domain, timeout=timeout)
        result.mx_records = mx_records
        result.status = "MX_record_exists"
    except Exception as exc:  # DNS timeout/NXDOMAIN/etc.
        result.status = "Domain_has_no_MX"
        result.detail = str(exc)
        return result

    if do_smtp and result.mx_records:
        try:
            status, detail = await asyncio.wait_for(smtp_handshake(normalized, result.mx_records[0], timeout), timeout + 2)
            result.status = status
            result.detail = detail
        except asyncio.TimeoutError:
            result.status = "Timeout"
            result.detail = "SMTP handshake timed out"
        except Exception as exc:
            result.status = "Unverified"
            result.detail = f"SMTP probe failed: {exc}"

    return result


async def check_many(emails: list[str], do_smtp: bool = False) -> list[EmailCheckResult]:
    return await asyncio.gather(*(check_email(email, do_smtp=do_smtp) for email in emails))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate email syntax, MX, and optional SMTP RCPT handshake.")
    parser.add_argument("emails", nargs="+")
    parser.add_argument("--smtp", action="store_true", help="Attempt non-sending SMTP RCPT handshake")
    args = parser.parse_args()

    for item in asyncio.run(check_many(args.emails, do_smtp=args.smtp)):
        print(item)
