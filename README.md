# URL Shortener

A small, containerized URL shortener built with Flask and PostgreSQL, served behind nginx with automatic HTTPS (Let's Encrypt). Pasting a long link will return a short one, which will redirect to the original.

## Features

- Shortens any `http`/`https` link to a random 7-character token
- Input validation (scheme, hostname, port, length) with clear error messages
- Redirects with proper status codes (`302` for links, `404` for unknown codes)
- `/health` endpoint that checks database connectivity
- Production setup with HTTPS, automatic certificate renewal, and rate limiting on link creation

## Quick start (local)

Requires Docker with Compose.

```bash
git clone https://github.com/chromatic0/url-shortener-docker.git
cd url-shortener-docker

cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD and SECRET_KEY. To generate a secret key:
#   python3 -c "import secrets; print(secrets.token_hex(32))"

docker compose up --build
```

Then visit <http://localhost:8080>.

## Production deployment

Requires a server with Docker, a domain pointing at it, and ports 80 and 443 open.

1. Set `DOMAIN` (and the other values) in `.env`.
2. **First-time certificate** (nginx can't serve HTTPS until a certificate exists, so a temporary HTTP-only nginx answers Let's Encrypt's challenge):

   ```bash
   COMPOSE="docker compose -f compose.yaml -f compose.prod.yaml"

   $COMPOSE --profile bootstrap up -d nginx-bootstrap
   $COMPOSE run --rm --entrypoint certbot certbot certonly \
     --webroot -w /var/www/certbot \
     -d your.domain.com --email you@example.com --agree-tos
   $COMPOSE --profile bootstrap down
   ```

3. Start everything:

   ```bash
   $COMPOSE up -d --build
   ```

Certificates renew automatically (certbot checks every 12 hours, and nginx reloads every 6 hours to pick up renewed certificates).

## Project layout

```
.
├── compose.yaml            # postgres + app (shared)
├── compose.override.yaml   # local dev: publishes the app on :8080
├── compose.prod.yaml       # production: nginx, certbot, certificate bootstrap
├── .env.example            # copy to .env and fill in
├── nginx/
│   ├── prod.conf.template  # HTTPS config, rate limiting ($DOMAIN is substituted)
│   └── acme-bootstrap.conf # HTTP-only config for first certificate
├── src/
│   ├── app.py              # Flask app
│   ├── templates/index.html
│   ├── Dockerfile
│   └── requirements*.txt
└── .github/workflows/ci.yml
```