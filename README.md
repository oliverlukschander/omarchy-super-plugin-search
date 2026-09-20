# Super Plugin Search

Search the Omarchy plugin marketplace from the super-menu.

Type to filter verified community listings, then Enter runs the official
`omarchy plugin add` in a floating terminal so the unsandboxed-code warning
still happens. No bar icon and no private catalog.

`omarchy plugin add` never runs install hooks. The extra `install.sh` step
only writes one menu row: **Setup → Plugins → Search plugins**.

No sudo or pkexec is required.

## Install

Both steps are required:

```sh
omarchy plugin add https://github.com/oliverlukschander/omarchy-super-plugin-search.git --enable
~/.config/omarchy/plugins/oliverlukschander.super-plugin-search/install.sh
```

`install.sh` writes **Search plugins** into
`~/.config/omarchy/extensions/omarchy-menu.jsonc` and refreshes the menu. It
does not overwrite other menu rows.

## Use

Super menu → Setup → Plugins → Search plugins, or type `search plugins` from
the root menu.

| Key | Action |
| --- | --- |
| type | filter name, id, author, tag, category |
| ↑ ↓ | move |
| Enter | install with `omarchy plugin add` (or notify if already installed) |
| click a category chip | filter Widgets, System, Desktop, and the rest |
| Ctrl+O | open the repository |
| Ctrl+L | open the marketplace listing |
| Ctrl+R | refresh the catalog |
| Esc | clear the query, then the chip, then close |

Enter always installs. GitHub listings without an official install command
still run `omarchy plugin add` against the repo. If the cloned plugin still
needs an extra `setup` (or `install.sh`) step, a clickable notification appears
at the top right; click it to finish in a floating terminal. Ctrl+O opens the
repo; Ctrl+L opens the marketplace listing.

The catalog is [plugins.omarchy.org/catalog.json](https://plugins.omarchy.org/catalog.json),
cached under `~/.local/state/omarchy/super-plugin-search/` for six hours.
Hearts and command-copies come from
[api.omarchyplugins.com/v1/stats](https://api.omarchyplugins.com/v1/stats).
Copies are marketplace install-command copies, not proven installs.

Results are marketplace-verified listings only, plus Omarchy built-ins.
Unverified listings are omitted. Marketplace verification is not a security
audit. Third-party plugins still run as unsandboxed code.

## Remove

```sh
~/.config/omarchy/plugins/oliverlukschander.super-plugin-search/uninstall.sh
omarchy plugin remove oliverlukschander.super-plugin-search
```

Run the uninstaller first so the menu row is removed. Removing the plugin
folder also deletes the uninstaller.

## License and dependencies

MIT. See [LICENSE](LICENSE).

Runtime: Omarchy 4 (Quattro) with `omarchy-shell`, and `/usr/bin/python3`
(standard library only: `json`, `urllib`). No extra packages.
