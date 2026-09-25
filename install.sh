#!/usr/bin/bash
set -euo pipefail

_self=${BASH_SOURCE[0]}
if [[ $_self != /* ]]; then
  _self=${PWD%/}/$_self
fi
PLUGIN_DIR=${_self%/*}
PYTHON=/usr/bin/python3
OMARCHY=/usr/bin/omarchy

bind=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --bind)
      bind=1
      shift
      ;;
    -h | --help)
      echo "Usage: install.sh [--bind]"
      echo "  --bind    also bind Super+Ctrl+M to open Search plugins"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: install.sh [--bind]" >&2
      exit 2
      ;;
  esac
done

echo "Omarchy Super Plugin Search"
echo "Adds Setup → Plugins → Search plugins"
echo

if [[ ! -x $PYTHON ]]; then
  echo "Missing $PYTHON" >&2
  exit 1
fi

"$PYTHON" -I "$PLUGIN_DIR/scripts/menu.py" install
if [[ $bind == 1 ]]; then
  "$PYTHON" -I "$PLUGIN_DIR/scripts/menu.py" bind
fi
if [[ -x $OMARCHY ]]; then
  "$OMARCHY" menu refresh >/dev/null 2>&1 || true
fi

echo "Ready. Super menu → Setup → Plugins → Search plugins"
echo "Type to filter. Tab changes mode."
echo "Enter installs, updates, or uninstalls, depending on the selected plugin."
if [[ $bind == 1 ]]; then
  echo "Super+Ctrl+M opens Search plugins."
fi
