# Deploying and operating StudEase

This is the runbook for a single Linux server (Debian or Ubuntu) with nginx, PostgreSQL 14+ and
[uv](https://docs.astral.sh/uv/). Everything here is also in code: [deploy/nginx-studease.conf](../deploy/nginx-studease.conf),
[deploy/studease-api.service](../deploy/studease-api.service) and [deploy/deploy.sh](../deploy/deploy.sh). The
application itself runs the same way locally (see the README); deployment only adds TLS, a process manager and a proxy.

## Layout on the server

```
/opt/studease/
  shared/.env            the only place secrets live (mode 600, owner studease); never in git
  releases/<stamp>-<sha>/ one folder per deploy: backend/ database/ data/ reports/ frontend/dist/
  app -> releases/...    symlink to the live release (switched atomically)
```

nginx serves `frontend/dist` and proxies `/api/` to uvicorn on `127.0.0.1:8100`. The API is never exposed directly.

## One-time setup

Run these on the server as an administrator. Placeholders in angle brackets are values you generate; never paste
real ones into the repository.

1. **System user and folders**
   ```bash
   sudo useradd --system --home /opt/studease --shell /usr/sbin/nologin studease
   sudo mkdir -p /opt/studease/shared /opt/studease/releases && sudo chown -R studease: /opt/studease
   ```
2. **Database** (S-13: one role that owns only its own databases; connect rights removed from everyone else)
   ```bash
   sudo -u postgres psql <<'SQL'
   CREATE ROLE studease LOGIN PASSWORD '<generate-a-long-random-password>';
   CREATE DATABASE studease OWNER studease;
   REVOKE CONNECT ON DATABASE studease FROM PUBLIC;
   SQL
   ```
   PostgreSQL must listen on localhost only (`listen_addresses = 'localhost'`, the default).
3. **Environment file** `/opt/studease/shared/.env` (mode 600). Required keys:
   `ENV=prod`, `DATABASE_URL` (the `postgresql+psycopg://` URL for the role above), `JWT_SECRET` (32+ random
   characters), `DEMO_PASSWORD` (12+ characters; the password of the five demo logins), `APP_URL` and `CORS_ORIGINS`
   (both the public https origin). Optional mail: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`.
   Generate secrets with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`. With `ENV=prod` the API
   refuses to start if the secret or demo password is missing, default or short (S-6).
4. **nginx and TLS**
   ```bash
   sudo cp deploy/nginx-studease.conf /etc/nginx/sites-available/studease
   sudo ln -s /etc/nginx/sites-available/studease /etc/nginx/sites-enabled/studease
   sudo nginx -t && sudo systemctl reload nginx
   sudo certbot --nginx -d <your-domain>        # adds the TLS block, redirect and renewal
   ```
   Add `Strict-Transport-Security` once HTTPS works: `add_header Strict-Transport-Security "max-age=31536000" always;`.
5. **Service**
   ```bash
   sudo cp deploy/studease-api.service /etc/systemd/system/ && sudo systemctl daemon-reload
   sudo systemctl enable studease-api
   ```
6. **First deploy and data** (from your machine; see below), then load the data once on the server:
   ```bash
   cd /opt/studease/app/backend && sudo -u studease uv run python -m app.cli load --scale starter
   ```
   `load` replaces every table with the generated dataset and seeds the five demo users. Run it again at any time to
   reset the demo to its seeded state (the public demo accepts writes by design, S-8).

## Deploying a change

```bash
DEPLOY_HOST=<ssh-alias-or-user@host> ./deploy/deploy.sh
```

The script builds the frontend, uploads the committed `HEAD` (`git archive`, so untracked files never ship) into a new
release folder, copies the shared `.env`, installs locked dependencies (`uv sync --frozen`), runs migrations, switches
the `app` symlink and restarts the service, then polls `/api/v1/readyz`. It keeps the last five releases.

If the health check fails, or the release misbehaves:

```bash
DEPLOY_HOST=<ssh-alias-or-user@host> ./deploy/deploy.sh rollback
```

Rollback re-points `app` at the previous release and restarts. Migrations are written to be backwards compatible
for one release, so the previous code still runs against the migrated schema.

## Mail

Mail is sent with SMTP and STARTTLS by `backend/app/mail.py`: a password-reset link, and a receipt when a payment is
recorded for a learner login. It is skipped when `SMTP_HOST` or `MAIL_FROM` is unset, never sent to the synthetic
`@example.edu` addresses unless `MAIL_TEST_TO` names a single inbox to receive them (prefixed with the intended
recipient), and a delivery failure is logged and never fails the request. Use an existing sending account; its credentials
belong in `/opt/studease/shared/.env` only.

## Operations

| Task | Command |
|---|---|
| Logs (one JSON line per request) | `journalctl -u studease-api -f` |
| Liveness and readiness | `curl https://<domain>/api/v1/healthz` and `/readyz` (readiness checks the database) |
| Restart | `sudo systemctl restart studease-api` |
| Reset the demo data | `cd /opt/studease/app/backend && sudo -u studease uv run python -m app.cli load` |
| Database backup | `sudo -u postgres pg_dump studease \| gzip > studease-$(date +%F).sql.gz` |

Logs never contain query strings, headers, bodies, passwords or tokens (S-12). Every error response carries a request id;
ask for it when someone reports a problem and search the log for it.

## What to check after a deploy

1. `readyz` returns `ready`.
2. Sign in as each demo role; the overview loads for finance roles, the student list for the instructor.
3. Open a missing page (`/nope`): the app's own 404 page appears. Stop the service briefly: nginx shows the static
   "Be right back" page instead of a bare gateway error.
4. Response headers include the security headers of S-16 (`curl -sI https://<domain>/`).
5. `curl -s https://<domain>/api/v1/students` answers 401 in the JSON envelope.
