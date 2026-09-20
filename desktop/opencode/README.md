# OpenCode Desktop

The tracked configuration is portable. Provider authentication is not.

## What Desktop looks like after setup

Three independent Desktop entries:

| Shortcut | Mode | Default agent | User data directory |
| --- | --- | --- | --- |
| `OpenCode` (stock) | Stable | `stable-lead` | `%APPDATA%\ai.opencode.desktop` |
| `OpenCode Vanilla` | Vanilla | `build` | `%APPDATA%\ai.opencode.desktop-vanilla` |
| `OpenCode Core` | Core | `core-lead` | `%APPDATA%\ai.opencode.desktop-core` |

The stock shortcut is created by the OpenCode installer and is never modified by
this repository. Setup only adds the two new shortcuts.

The stock Stable shortcut passes no `--user-data-dir` and uses the app default.
The Vanilla and Core wrappers each pass a distinct `--user-data-dir`, which
separates UI state and the session database per mode. Provider authentication is
shared because the data and auth paths are not changed.

**Verified limitation: only one Desktop instance at a time.** On OpenCode Desktop
1.18.31, launching a second instance with a different `--user-data-dir` exits
immediately with code 0; the fresh directory is never written and the default
`lockfile` is untouched. The app calls `requestSingleInstanceLock()` and quits on
failure, and this build does not separate that lock by `--user-data-dir`.
Reproduced with three target directories and both argument forms.

The shortcuts are therefore alternative entries, not concurrent windows. Close
the running instance before opening another mode. The CLI launchers (`oc-vanilla`,
`oc-stable`, `oc-core`) are unaffected and can run concurrently.

## How the wrappers work

`OpenCode Vanilla` and `OpenCode Core` launch PowerShell wrappers deployed to
`~/.config/opencode/modes/`:

- `desktop-vanilla.ps1` sets `OPENCODE_CONFIG` to the Vanilla mode config and
  starts OpenCode with `--user-data-dir=...\ai.opencode.desktop-vanilla`.
- `desktop-core.ps1` additionally sets `OPENCODE_CONFIG_DIR`,
  `XDG_CONFIG_HOME`, and `OPENCODE_DISABLE_EXTERNAL_SKILLS=1`, then starts
  OpenCode with `--user-data-dir=...\ai.opencode.desktop-core`. It deliberately
  does not set `OPENCODE_DISABLE_DEFAULT_PLUGINS`, because that also removes the
  built-in provider plugins needed to resolve the pinned `openai/gpt-5.6-sol`.

The isolated `XDG_CONFIG_HOME` is what stops the global full-Superpowers config
from being read into Core. Verified with `opencode debug config` and
`opencode debug skill`.

## Limits

- Session history is separate per mode, because each mode uses its own user-data
  directory whenever it is the running instance.
- `opencode://` deep links route to whichever instance is currently running.
- Launcher failures are written to `%LOCALAPPDATA%\OpenCode\mode-launcher.log` and
  shown in a message box, because the shortcuts run PowerShell hidden.
- An OpenCode Desktop update can change Electron launch behavior. Re-run setup and
  re-verify if a shortcut stops isolating correctly.

## Rebuild

1. Install OpenCode and OpenCode Desktop.
2. Authenticate providers locally.
3. Run `scripts/setup-windows.ps1`.
4. Open the stock shortcut for Stable, or the Vanilla/Core shortcuts.

## Remove stale deployed artifacts

Earlier generations deployed a multi-agent Team workflow, a product profile, and
an `oc-product` wrapper. Setup lists them, and `-CleanLegacy` removes them,
including the `oc-product` shims in `~/bin` and `%APPDATA%\npm` and the retired
`OpenCode PRODUCT` / `OpenCode TEAM` shortcuts.

## UI/TUI preferences

OpenCode keeps TUI-specific preferences separately from provider config. If you
have a personal `tui.json` you want to preserve, copy a **secret-free** version
into this directory manually and commit it.

Do not copy a global provider config into Git unless you have inspected it and
replaced every credential with environment/file references.
