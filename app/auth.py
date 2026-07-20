"""Single-user passcode gate for the dashboard.

This is intentionally lightweight: there are no user accounts, just one shared
passcode that unlocks the whole site. Authentication state lives in Flask's
signed session cookie, so it works across multiple gunicorn workers as long as
every worker shares the same ``SECRET_KEY``.

Configuration (environment variables):

* ``APP_PASSCODE_HASH`` — a Werkzeug password hash of the passcode (preferred).
  Generate one with ``python -m app.auth``.
* ``APP_PASSCODE`` — a plaintext passcode (convenient for local dev only).
* ``SECRET_KEY`` — signs the session cookie. **Required in production** so the
  two gunicorn workers agree on cookie signatures and logins survive restarts.
* ``APP_SESSION_DAYS`` — how long a login lasts (default 30).

If neither passcode variable is set, the gate is disabled and the site is open
(handy for local development); a warning is logged so this is never a surprise
in production.
"""

from __future__ import annotations

import hmac
import logging
import os
import secrets
import time
from datetime import timedelta
from urllib.parse import urlsplit

from flask import Flask, Response, redirect, request, session

logger = logging.getLogger(__name__)

SESSION_KEY = "authenticated"

# Paths reachable without a session: the login flow, health check, and the
# static assets the login page itself needs (logo/css).
_ALLOWLIST_PREFIXES = ("/login", "/logout", "/healthz", "/assets/", "/favicon")

# Basic brute-force protection (in-memory, per worker).
_MAX_FAILURES = 5
_LOCKOUT_SECONDS = 60
_failures: dict[str, tuple[int, float]] = {}


def _configured_hash() -> str | None:
    value = os.getenv("APP_PASSCODE_HASH")
    return value.strip() if value else None


def _configured_plain() -> str | None:
    value = os.getenv("APP_PASSCODE")
    return value if value else None


def auth_enabled() -> bool:
    """True when a passcode (hash or plaintext) is configured."""
    return bool(_configured_hash() or _configured_plain())


def verify_passcode(candidate: str) -> bool:
    """Constant-time check of a submitted passcode against configuration."""
    if not candidate:
        return False
    hashed = _configured_hash()
    if hashed:
        # Imported lazily so environments without Werkzeug can still import this
        # module (Werkzeug ships with Flask, so this is normally always present).
        from werkzeug.security import check_password_hash

        return check_password_hash(hashed, candidate)
    plain = _configured_plain()
    if plain:
        return hmac.compare_digest(plain, candidate)
    return False


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _locked_out(ip: str) -> bool:
    count, until = _failures.get(ip, (0, 0.0))
    return count >= _MAX_FAILURES and time.time() < until


def _record_failure(ip: str) -> None:
    count, _ = _failures.get(ip, (0, 0.0))
    _failures[ip] = (count + 1, time.time() + _LOCKOUT_SECONDS)


def _clear_failures(ip: str) -> None:
    _failures.pop(ip, None)


def _safe_next(target: str | None) -> str:
    """Only allow same-site, path-only redirect targets (no open redirects)."""
    if not target:
        return "/"
    split = urlsplit(target)
    if split.scheme or split.netloc or not target.startswith("/") or target.startswith("//"):
        return "/"
    return target


def _login_page(message: str = "", next_target: str = "/", status: int = 200) -> Response:
    banner = (
        f'<p class="err" role="alert">{message}</p>' if message else ""
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow">
  <title>Enduralytics — Sign in</title>
  <style>
    :root {{ color-scheme: dark; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; min-height: 100vh; display: grid; place-items: center;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: radial-gradient(1200px 600px at 50% -10%, #16303a 0%, #0f1417 55%);
      color: #e8eef0;
    }}
    .card {{
      width: min(92vw, 360px); padding: 32px 28px; border-radius: 16px;
      background: rgba(20, 27, 31, 0.85); border: 1px solid rgba(162, 228, 54, 0.15);
      box-shadow: 0 20px 60px rgba(0,0,0,0.45); text-align: center;
    }}
    .brand {{ display:flex; align-items:center; justify-content:center; gap:10px; margin-bottom: 22px; }}
    .brand img {{ width: 40px; height: 40px; }}
    .brand span {{ font-size: 1.4rem; font-weight: 700; letter-spacing: .2px; }}
    .brand .a {{ color: #a2e436; }}
    label {{ display:block; text-align:left; font-size:.85rem; margin-bottom:6px; color:#aeb9bd; }}
    input[type=password] {{
      width: 100%; padding: 12px 14px; border-radius: 10px; font-size: 1rem;
      border: 1px solid #33424a; background: #0f1417; color: #e8eef0; margin-bottom: 16px;
    }}
    input:focus {{ outline: 2px solid #2ed3be; border-color: transparent; }}
    button {{
      width: 100%; padding: 12px 14px; border: 0; border-radius: 10px; cursor: pointer;
      font-size: 1rem; font-weight: 600; color: #0f1417;
      background: linear-gradient(120deg, #a2e436, #2ed3be);
    }}
    .err {{ color: #ff8f8f; font-size: .85rem; margin: 0 0 14px; }}
  </style>
</head>
<body>
  <form class="card" method="post" action="/login">
    <div class="brand">
      <img src="/assets/logo.svg" alt="">
      <span><span class="a">Endura</span>lytics</span>
    </div>
    {banner}
    <label for="passcode">Passcode</label>
    <input id="passcode" name="passcode" type="password" autocomplete="current-password"
           autofocus required>
    <input type="hidden" name="next" value="{next_target}">
    <button type="submit">Sign in</button>
  </form>
</body>
</html>"""
    return Response(html, status=status, mimetype="text/html")


def configure_auth(server: Flask) -> None:
    """Attach the passcode gate to the Dash Flask server."""
    server.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    if not os.getenv("SECRET_KEY"):
        logger.warning(
            "SECRET_KEY is not set; using an ephemeral key. Logins will not "
            "persist across restarts and will break with multiple workers. "
            "Set SECRET_KEY in the environment for production."
        )

    # On Render (which terminates TLS in front of the app) require HTTPS cookies.
    on_render = bool(os.getenv("RENDER"))
    secure_cookie = os.getenv("SESSION_COOKIE_SECURE")
    server.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=(
            secure_cookie.lower() in ("1", "true", "yes")
            if secure_cookie is not None
            else on_render
        ),
        PERMANENT_SESSION_LIFETIME=timedelta(days=int(os.getenv("APP_SESSION_DAYS", "30"))),
    )

    if not auth_enabled():
        logger.warning(
            "No APP_PASSCODE_HASH or APP_PASSCODE set; the dashboard is PUBLIC. "
            "Set a passcode to require login."
        )

    @server.route("/healthz")
    def healthz() -> Response:
        return Response("ok", mimetype="text/plain")

    @server.route("/login", methods=["GET", "POST"])
    def login() -> Response:
        if not auth_enabled():
            return redirect("/")

        next_target = _safe_next(request.values.get("next"))

        if session.get(SESSION_KEY):
            return redirect(next_target)

        if request.method == "GET":
            return _login_page(next_target=next_target)

        ip = _client_ip()
        if _locked_out(ip):
            return _login_page(
                "Too many attempts. Wait a minute and try again.",
                next_target,
                status=429,
            )

        if verify_passcode(request.form.get("passcode", "")):
            _clear_failures(ip)
            session.clear()
            session[SESSION_KEY] = True
            session.permanent = True
            return redirect(next_target)

        _record_failure(ip)
        return _login_page("Incorrect passcode.", next_target, status=401)

    @server.route("/logout")
    def logout() -> Response:
        session.clear()
        return redirect("/login")

    @server.before_request
    def require_login() -> Response | None:
        if not auth_enabled():
            return None
        if session.get(SESSION_KEY):
            return None
        path = request.path or "/"
        if any(path.startswith(prefix) for prefix in _ALLOWLIST_PREFIXES):
            return None
        # Preserve where the user was headed so we can return them after login.
        return redirect("/login?next=" + _safe_next(path))


def _generate_hash_cli() -> None:
    """`python -m app.auth` — turn a typed passcode into an APP_PASSCODE_HASH."""
    import getpass

    from werkzeug.security import generate_password_hash

    first = getpass.getpass("New passcode: ")
    second = getpass.getpass("Confirm passcode: ")
    if first != second:
        raise SystemExit("Passcodes do not match.")
    if len(first) < 6:
        raise SystemExit("Use at least 6 characters.")
    print("\nAdd this to your environment (Render env var):\n")
    print("APP_PASSCODE_HASH=" + generate_password_hash(first))


if __name__ == "__main__":
    _generate_hash_cli()
