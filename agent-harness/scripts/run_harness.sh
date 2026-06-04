#!/usr/bin/env bash
set -euo pipefail

site_root="${1:-_site}"

python3 investment-thesis-harness/scripts/validate.py
bash tools/build_pages_site.sh "$site_root"
python3 tools/check_site_links.py --root "$site_root"
python3 agent-harness/scripts/validate.py --site-root "$site_root"
