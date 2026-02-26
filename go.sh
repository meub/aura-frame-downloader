#!/bin/bash -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$SCRIPT_DIR"

. ./venv/bin/activate
python download-aura-photos.py --year --config config.ini --save-assets /tmp/overlook_assets.json Overlook
