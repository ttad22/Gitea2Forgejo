#!/usr/bin/env bash
set -euo pipefail

echo "Smoke plan for git-ops"
echo "== service_app =="
systemctl is-active gitea
echo "== service_proxy =="
systemctl is-active nginx
echo "== service_db =="
systemctl is-active postgresql
echo "== web_health =="
curl -fsS http://127.0.0.1:3000/api/health
echo "== root_ui =="
curl -fsSI http://127.0.0.1:80/ | head -n 1
echo "== https_root =="
curl -fsSI https://git.tttmsp.com/ | head -n 1
echo "== https_repo_browse =="
curl -fsSI https://git.tttmsp.com/explore/repos | head -n 1
echo "== ssh_port =="
ss -ltn | grep -q ':22 '
echo "smoke-plan-complete"
