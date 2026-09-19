#!/usr/bin/bash
set -euo pipefail

_self=${BASH_SOURCE[0]}
if [[ $_self != /* ]]; then
  _self=${PWD%/}/$_self
fi
PLUGIN_DIR=${_self%/*}
PYTHON=/usr/bin/python3
OMARCHY=/usr/bin/omarchy

echo "Omarchy Super Plugin Search"
echo "Adds Setup → Plugins → Search plugins"
echo

if [[ ! -x $PYTHON ]]; then
  echo "Missing $PYTHON" >&2
  exit 1
fi

"$PYTHON" -I "$PLUGIN_DIR/scripts/menu.py" install
if [[ -x $OMARCHY ]]; then
  "$OMARCHY" menu refresh >/dev/null 2>&1 || true
fi

echo "Ready. Super menu → Setup → Plugins → Search plugins"
echo "Type to filter. Enter installs with omarchy plugin add."
echo "Ctrl+O opens the repo, Ctrl+L the marketplace page, Ctrl+R refreshes."
