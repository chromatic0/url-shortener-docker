import logging
import os
import re
import secrets
import string
from contextlib import contextmanager
from urllib.parse import urlparse

from flask import (
    Flask,
    flash,
    get_flashed_messages,
    redirect,
    render_template,
    request,
    url_for,
)
from psycopg2 import pool
from werkzeug.middleware.proxy_fix import ProxyFix

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("shortener")

ALPHABET = string.ascii_letters + string.digits
TOKEN_LENGTH = 7
MAX_TOKEN_ATTEMPTS = 5

CODE_PATTERN = re.compile(r"^[A-Za-z0-9]{1,16}$")

MAX_URL_LENGTH = 2048


def generate_token(length=TOKEN_LENGTH):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))

def normalize_url(raw):
    """Return a cleaned-up http(s) URL, or raise ValueError if it's not usable.

    FIX: the original accepted any string and only prepended https://. Now we
    reject empty/oversized input, whitespace, non-http(s) schemes, bad ports,
    and hostnames without a dot (e.g. "asdf").
    """
    raw = (raw or "").strip()
    if not raw or len(raw) > MAX_URL_LENGTH:
        raise ValueError("URL is empty or too long")
    if any(ch.isspace() for ch in raw):
        raise ValueError("URL contains whitespace")

    if "://" not in raw:
        raw = "https://" + raw

    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https links are supported")
    try:
        parsed.port
    except ValueError:
        raise ValueError("Invalid port")
    if not parsed.hostname or "." not in parsed.hostname:
        raise ValueError("URL needs a valid domain name")
    return raw


_pool = None

def get_pool():
    """Create the connection pool lazily (once per process).

    FIX: the original opened and closed a brand-new database connection on
    every request. A small pool reuses connections instead. It is created
    lazily so each gunicorn worker builds its own after forking.
    """
    global _pool
    if _pool is None:
        _pool = pool.ThreadedConnectionPool(
            1,
            5,
            dbname=os.environ.get("POSTGRES_DB"),
            user=os.environ.get("POSTGRES_USER"),
            password=os.environ.get("POSTGRES_PASSWORD"),
            host=os.environ.get("POSTGRES_HOST", "postgres"),
        )
    return _pool


def close_pool():
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


@contextmanager
def db_cursor():
    """Yield a cursor; commit on success, roll back on error, always return the
    connection to the pool.

    FIX: replaces the hand-written try/finally/close boilerplate that was
    copy-pasted into every function in the original.
    """
    conn = get_pool().getconn()
    try:
        with conn:
            with conn.cursor() as cur:
                yield cur
    finally:
        get_pool().putconn(conn)


def init_db():
    with db_cursor() as cur:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS url (
                id SERIAL PRIMARY KEY,
                token text NOT NULL UNIQUE,
                redirect text NOT NULL
            );"""
        )


def create_short_url(target_url):
    """Insert target_url under a fresh random token and return the token."""
    with db_cursor() as cur:
        for _ in range(MAX_TOKEN_ATTEMPTS):
            token = generate_token()
            cur.execute(
                """INSERT INTO url (token, redirect) VALUES (%s, %s)
                   ON CONFLICT (token) DO NOTHING RETURNING token;""",
                (token, target_url),
            )
            if cur.fetchone() is not None:
                return token
    raise RuntimeError("Could not generate a unique token")


def lookup_url(code):
    """Return the target URL for a token, or None if it doesn't exist."""
    with db_cursor() as cur:
        cur.execute("SELECT redirect FROM url WHERE token = %s;", (code,))
        row = cur.fetchone()
    return row[0] if row else None

def create_app():
    app = Flask(__name__)

    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SECRET_KEY environment variable is not set")
    app.secret_key = secret_key

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    @app.route("/", methods=["GET", "POST"])
    def generate_url():
        if request.method == "POST":
            try:
                target = normalize_url(request.form.get("url"))
            except ValueError as exc:
                flash(str(exc), "error")
                return redirect(url_for("generate_url"))

            try:
                token = create_short_url(target)
                flash(token, "short_url")
            except Exception:
                log.exception("Failed to create short URL")
                flash("Something went wrong. Please try again.", "error")
            return redirect(url_for("generate_url"))

        short_url = None
        error = None
        for category, msg in get_flashed_messages(with_categories=True):
            if category == "error":
                error = msg
            elif category == "short_url":
                short_url = url_for("redirect_to_url", code=msg, _external=True)
        return render_template("index.html", short_url=short_url, error=error)

    @app.route("/health")
    def health():
        try:
            with db_cursor() as cur:
                cur.execute("SELECT 1;")
        except Exception:
            log.exception("Health check failed")
            return {"status": "unhealthy"}, 503
        return {"status": "ok"}

    @app.route("/<code>")
    def redirect_to_url(code):
        if not CODE_PATTERN.match(code):
            return render_template("index.html", error="Redirect not found."), 404

        try:
            target = lookup_url(code)
        except Exception:
            log.exception("Lookup failed for code %s", code)
            return render_template("index.html", error="Something went wrong."), 500

        if target is None:
            return render_template("index.html", error="Redirect not found."), 404
        return redirect(target, code=302)

    return app

def create_app_with_db():
    app = create_app()
    init_db()
    close_pool()
    return app


if __name__ == "__main__":
    dev_app = create_app_with_db()
    dev_app.run(
        host="127.0.0.1",
        port=4242,
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )