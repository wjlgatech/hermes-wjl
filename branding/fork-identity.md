# Fork identity — single source of truth (KTD1)

This fork (`wjlgatech/hermes-wjl`) installs, clones, and updates from **itself**,
not from upstream `NousResearch/hermes-agent`. Because the install/update code
spans shell, Rust, JavaScript, and Python, the values can't be a single shared
constant — instead each override site carries a `fork-override:` marker comment
so this file stays the re-audit checklist after upstream merges.

## Canonical values

| Key | Value |
|-----|-------|
| Owner/repo | `wjlgatech/hermes-wjl` |
| Clone (HTTPS) | `https://github.com/wjlgatech/hermes-wjl.git` |
| Clone (SSH) | `git@github.com:wjlgatech/hermes-wjl.git` |
| Canonical remote | `github.com/wjlgatech/hermes-wjl` |
| Raw content base | `https://raw.githubusercontent.com/wjlgatech/hermes-wjl` |
| Archive base | `https://github.com/wjlgatech/hermes-wjl/archive` |

## Override sites (grep `fork-override`)

- `scripts/install.sh` — `REPO_URL_SSH` / `REPO_URL_HTTPS`
- `scripts/install.ps1` — `$RepoUrlSsh` / `$RepoUrlHttps` / archive zip URLs
- `apps/bootstrap-installer/src-tauri/src/install_script.rs` — raw script URL
- `apps/desktop/electron/update-remote.cjs` — `OFFICIAL_REPO_HTTPS_URL` / `OFFICIAL_REPO_CANONICAL`
- `hermes_cli/main.py` — `OFFICIAL_REPO_URL` / `OFFICIAL_REPO_URLS` / archive zip URL

## Deliberately NOT changed

- **Upstream references.** Code/messages that add `NousResearch/hermes-agent` as
  an `upstream` remote (e.g. `hermes_cli/main.py` "Added upstream …") are
  correct — NousResearch *is* the upstream this fork merges from.
- **Electron `appId` / `productName`** (`apps/desktop/package.json`,
  `com.nousresearch.hermes` / `Hermes`). Left as-is so the currently-installed
  app keeps its identity and userData. A distinct fork `appId` (e.g.
  `com.wjlgatech.hermes-wjl`) belongs with the signed-distribution work (U3),
  where a fresh app identity is appropriate.

## Download host

`hermes-agent.nousresearch.com` (install.sh/ps1 one-liner host, installer
download page) is upstream infrastructure. A fork-hosted equivalent is part of
the distribution work (U3) and is not stood up here; the one-liner *hint*
comments still reference the upstream host until fork hosting exists.
