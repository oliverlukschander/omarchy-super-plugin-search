#!/usr/bin/bash
set -euo pipefail

_self=${BASH_SOURCE[0]}
if [[ $_self != /* ]]; then
  _self=${PWD%/}/$_self
fi
PLUGIN_DIR=${_self%/*}
PYTHON=/usr/bin/python3
OMARCHY=/usr/bin/omarchy

echo "Removing the Search plugins menu row"

if [[ ! -x $PYTHON ]]; then
  echo "Missing $PYTHON" >&2
  exit 1
fi

"$PYTHON" -I "$PLUGIN_DIR/scripts/menu.py" uninstall
if [[ -x $OMARCHY ]]; then
  "$OMARCHY" menu refresh >/dev/null 2>&1 || true
fi

echo "Menu row removed. Then: omarchy plugin remove oliverlukschander.super-plugin-search"
