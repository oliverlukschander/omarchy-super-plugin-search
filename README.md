# Super Plugin Search

Search the Omarchy plugin marketplace from the super-menu.

Type to filter verified community listings. Tab moves between Popular, New,
Installed, and Updates. Enter installs or updates the marketplace-approved
snapshot. The card uses the Omarchy menu's colors, type, and confirm dialog.

`omarchy plugin add` never runs install hooks. The extra `install.sh` step
only writes one menu row: **Setup → Plugins → Search plugins**. It does not
change other rows or Hyprland config.

No sudo or pkexec is required.

## Install

Both steps are required:

```sh
omarchy plugin add https://github.com/oliverlukschander/omarchy-super-plugin-search.git --enable
~/.config/omarchy/plugins/oliverlukschander.super-plugin-search/install.sh
```

`install.sh` writes **Search plugins** into
`~/.config/omarchy/extensions/omarchy-menu.jsonc` and refreshes the menu.

To also open the overlay from the keyboard, pass `--bind`:

```sh
~/.config/omarchy/plugins/oliverlukschander.super-plugin-search/install.sh --bind
```

That appends one binding to `~/.config/hypr/bindings.lua`: **Super+Ctrl+M**.
Omarchy's default bindings leave that chord free. Super+Ctrl+letter is the
family that opens shell overlays (emoji, audio, network, power, and the
rest). M is not used there. The M chords that do exist are Super+Shift+M
(Music) and Super+Shift+Alt+M (Music TUI). If Super+Ctrl+M is already
present, `--bind` stops and leaves the file unchanged. The default install
path does not write this binding.

## Use

Super menu → Setup → Plugins → Search plugins, or type `search plugins` from
the root menu. With `--bind`, Super+Ctrl+M opens the same overlay.

| Key | Action |
| --- | --- |
| type | filter name, id, author, tag, category |
| ↑ ↓ | move |
| Tab | Popular → New → Installed → Updates |
| Shift+Tab | cycle modes backward |
| click a category chip | filter Widgets, System, Desktop, and the rest |
| Enter | install, update, or uninstall, depending on the selected plugin |
| Delete | uninstall the selected third-party plugin, after confirmation |
| Ctrl+O | open the repository |
| Ctrl+L | open the marketplace listing |
| Ctrl+R | refresh the catalog |
| Esc | clear the query, then the chip, then close |

Popular keeps the current ranking. New sorts by `listedAt`, newest first.
Installed lists every third-party plugin from `omarchy plugin list --json`,
enabled and disabled, including plugins that are not in the verified catalog.
Updates lists installed plugins whose checkout is behind the verified
snapshot. All four modes respect the current query and category chip.
First-party plugins stay in search with the installed mark and do not appear
as removable rows.

The selected plugin's marketplace screenshot sits large on the left, with the
description, version, and the Enter action under it. A missing image leaves
that text in place. The hint names only that action: Enter installs a plugin
that is not installed, updates one that is behind the verified snapshot, and
asks before uninstalling one that is already current. Built-ins are not
removable.

Enter installs or updates only when the catalog includes a full 40-character
`listingValidatedCommit`. A new install is checked out at that SHA before
enable. An installed third-party plugin whose `HEAD` already matches that SHA is
uninstalled from Enter, after the same confirmation as the Omarchy menu. If
`HEAD` differs and the worktree is clean, Enter fetches
that SHA, checks it out detached, verifies `HEAD`, then enables the plugin.
A dirty worktree or a SHA that cannot be pinned is left in place: nothing is
enabled and the folder is not deleted. Built-ins are not installable.

A word of four or more characters that misses the name, id, author, tag,
category, and description can still match a name token or the short id within
one edit. That match ranks below every exact, prefix, substring, author, tag,
category, and description hit. Every word in the query has to hit. The
description is not fuzzy-matched.

Delete asks for confirmation in the overlay, with the same confirm dialog as
the Omarchy menu. On confirm, an executable `uninstall.sh` in the plugin tree
runs first. If it fails, removal stops. Otherwise the overlay runs
`omarchy plugin remove <id> --yes` and refreshes the list. Removing this
plugin follows that same path, so its menu row is cleared before the folder
disappears.

The catalog is [plugins.omarchy.org/catalog.json](https://plugins.omarchy.org/catalog.json),
cached under `~/.local/state/omarchy/super-plugin-search/` for six hours.
Hearts and command-copies come from
[api.omarchyplugins.com/v1/stats](https://api.omarchyplugins.com/v1/stats).
Copies are marketplace install-command copies, not proven installs.

Results in Popular, New, and Updates are marketplace-verified listings only,
plus Omarchy built-ins in the first two modes. Unverified listings are
omitted. Marketplace verification is not a security audit. Third-party
plugins still run as unsandboxed code.

## Remove

```sh
~/.config/omarchy/plugins/oliverlukschander.super-plugin-search/uninstall.sh
omarchy plugin remove oliverlukschander.super-plugin-search
```

Run the uninstaller first so the menu row and the optional Super+Ctrl+M
binding are removed. Removing the plugin folder also deletes the uninstaller.
Delete inside the overlay does this for you.

## License and dependencies

MIT. See [LICENSE](LICENSE).

Runtime: Omarchy 4 (Quattro) with `omarchy-shell`, and `/usr/bin/python3`
(standard library only: `json`, `urllib`). No extra packages.
