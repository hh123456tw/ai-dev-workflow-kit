# OpenCode Desktop / TUI rebuild

The tracked profile files are portable. Provider authentication is not.

## Rebuild

1. Install OpenCode.
2. Authenticate the same providers locally.
3. Run `scripts/setup-windows.ps1` or `scripts/setup-unix.sh`.
4. Use `/models` and copy actual model IDs into the ignored `.local/models.*` file.
5. Start either `oc-product` or `oc-team`.

## UI/TUI preferences

OpenCode keeps TUI-specific preferences separately from main provider config. If you have a personal `tui.json` you want to preserve, copy a **secret-free** version into this directory manually and commit it.

Do not copy a global provider config into Git unless you have inspected it and replaced every credential with environment/file references.
