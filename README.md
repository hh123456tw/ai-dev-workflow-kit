# OpenCode Dual Workflow Profiles

Portable configuration for two isolated AI development workflows:

## 1. PRODUCT mode

**GPT-5.6 Sol product lead + DeepSeek V4.1 Flash workers + gstack + Superpowers**

Use for:

- side projects
- hackathons
- fast product iteration
- product thinking / QA / shipping

Launch:

```powershell
oc-product
```

## 2. TEAM V2 mode

**GPT-5.6 Sol orchestrator/reviewer + Matt Pocock engineering skills + DeepSeek V4.1 Flash bounded workers**

Core rule:

> GPT decides correctness. DeepSeek implements. Tests are contracts.

Launch:

```powershell
oc-team
```

## Why the profiles are isolated

Superpowers has a strong session bootstrap and gstack has its own product workflow. TEAM V2 intentionally keeps Matt Pocock as the workflow owner so routing does not become ambiguous.

- PRODUCT sees gstack + Superpowers; GPT-5.6 leads and DeepSeek V4.1 Flash handles scoped implementation work.
- TEAM sees Matt skills and hides gstack.
- TEAM does **not** load the Superpowers plugin.

## Repository layout

```text
profiles/
  product/              PRODUCT OpenCode config
  team/                 TEAM V2 OpenCode config + orchestration rules
workflows/
  product.md            Human-readable PRODUCT workflow
  team-v2.md            Human-readable TEAM V2 workflow
prompts/
  team-v2-upgrade.md    Prompt for repairing/upgrading TEAM mode
scripts/
  setup-windows.ps1     Restore on Windows
  setup-unix.sh         Restore on macOS/Linux
  oc-product.ps1        PRODUCT launcher
  oc-team.ps1           TEAM launcher
  models.*.example      Local model-ID templates
desktop/
  codex/                Codex Desktop rebuild checklist
  opencode/             OpenCode Desktop/TUI rebuild notes
```

## First install on a new Windows computer

Prerequisites:

- Git
- Node.js / npm
- OpenCode
- PowerShell
- Bash from Git for Windows or WSL if you want gstack installed automatically

Clone this repo and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
./scripts/setup-windows.ps1 -InstallLaunchers
```

Then copy the model template:

```powershell
Copy-Item ./scripts/models.ps1.example ./.local/models.ps1
```

Use OpenCode `/models` to get the **actual IDs available on that computer**, then edit `.local/models.ps1`.

Do not guess model IDs.

After provider authentication is configured locally:

```powershell
oc-product
oc-team
```

## First install on macOS/Linux

```bash
chmod +x scripts/setup-unix.sh scripts/oc-product.sh scripts/oc-team.sh
./scripts/setup-unix.sh --install-launchers
cp scripts/models.sh.example .local/models.sh
```

Fill the actual model IDs from `opencode /models`, then:

```bash
oc-product
oc-team
```

## Updating third-party frameworks

This repo deliberately does not vendor gstack, Superpowers, or Matt Pocock's skills.

- Superpowers: PRODUCT profile uses OpenCode's git-backed plugin install.
- gstack: setup scripts clone/update upstream and install with the `gstack-` prefix.
- Matt skills: setup scripts clone upstream and copy only the selected skills into the TEAM profile's private skills directory.

Run setup again to refresh them.

## Desktop apps

See:

- `desktop/codex/README.md`
- `desktop/opencode/README.md`

Account-backed plugin connections and OAuth authorizations are intentionally **not** backed up to Git.

## Sources / upstream projects

- OpenCode: https://opencode.ai/
- Superpowers: https://github.com/obra/superpowers
- gstack: https://github.com/garrytan/gstack
- Matt Pocock Skills: https://github.com/mattpocock/skills

## Publish this backup repo to GitHub

The recommended default is a **private** repository.

Windows:

```powershell
./scripts/publish-github.ps1 -RepoName opencode-dev-profiles -Visibility private
```

macOS/Linux:

```bash
./scripts/publish-github.sh opencode-dev-profiles private
```

The publish helper requires GitHub CLI (`gh`) to already be authenticated on that computer.
