#!/usr/bin/env bash
# Deploy StudEase to the server named by $DEPLOY_HOST (an ssh alias or user@host).
#   DEPLOY_HOST=myserver ./deploy/deploy.sh            deploy the committed HEAD
#   DEPLOY_HOST=myserver ./deploy/deploy.sh rollback   switch back to the previous release
# First-time server setup (database, user, nginx, TLS, .env) is in docs/deploy.md. This script never touches .env.
set -euo pipefail
HOST="${DEPLOY_HOST:?set DEPLOY_HOST to the ssh alias or user@host}"
BASE=/opt/studease
cd "$(dirname "$0")/.."

if [ "${1:-}" = "rollback" ]; then
  ssh "$HOST" "set -e; cd $BASE; prev=\$(ls -1d releases/* | sort | tail -n 2 | head -n 1); ln -sfn \$PWD/\$prev app.new && mv -Tf app.new app && sudo systemctl restart studease-api && echo rolled back to \$prev"
  exit 0
fi

REL="$(date -u +%Y%m%d%H%M%S)-$(git rev-parse --short HEAD)"
echo "building frontend"
(cd frontend && npm ci --no-audit --no-fund && npm run build)

echo "uploading release $REL"
ssh "$HOST" "mkdir -p $BASE/releases/$REL"
git archive HEAD backend database data reports scripts | ssh "$HOST" "tar -x -C $BASE/releases/$REL"
tar -C frontend -c dist | ssh "$HOST" "mkdir -p $BASE/releases/$REL/frontend && tar -x -C $BASE/releases/$REL/frontend"

echo "installing and switching"
ssh "$HOST" "set -e; cd $BASE/releases/$REL/backend
  cp $BASE/shared/.env .env                       # the one place secrets live, outside git
  uv sync --frozen --no-dev
  uv run alembic -c ../database/alembic.ini upgrade head
  cd $BASE && ln -sfn \$PWD/releases/$REL app.new && mv -Tf app.new app
  sudo systemctl restart studease-api
  ls -1d releases/* | sort | head -n -5 | xargs -r rm -rf   # keep the last five releases"

echo "waiting for the API"
for i in 1 2 3 4 5 6 7 8 9 10; do
  curl -fsS "https://studease.is-cool.dev/api/v1/readyz" >/dev/null && { echo "healthy: $REL"; exit 0; }
  sleep 2
done
echo "NOT healthy after deploy; run: DEPLOY_HOST=$HOST ./deploy/deploy.sh rollback" >&2
exit 1
