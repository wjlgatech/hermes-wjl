# Changelog

All notable changes to this fork (`wjlgatech/hermes-wjl`) are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed
- **Upstream auto-sync silently froze `main` 1444 commits / 12 days behind.**
  The hourly `sync-upstream.yml` hit a merge conflict every run, ran
  `git merge --abort`, and still **exited 0** (green ✅), while its only alert —
  "open an issue" — no-oped because issues are disabled on this fork. Hardened:
  on conflict the workflow now commits the conflicted merge to a stable
  `auto-sync/upstream` branch, opens/refreshes **one PR** into `main`, and
  **fails the job** (red ✗) so the stall is visible. Clean merges still push
  straight to `main`. (One-time catch-up to upstream done separately in #8.)
- **Desktop backend process leak that hung the app (131 orphaned `dashboard`
  backends, ~1.5 GB).** The pool is keyed by profile (one slot each), but the
  child `exit`/`error` handlers and the spawn `.catch` deleted the slot by key
  with **no identity check**. A reaped child's *delayed* `exit` (reap → immediate
  respawn) then evicted the **newer** entry from `backendPool`, leaving its live,
  port-holding child untracked and unreapable forever — so they accumulated
  (309 spawns − 179 reaped ≈ 130 leaked over ~4 days). Fixes:
  `deletePoolEntryIfCurrent()` only deletes when the slot still holds *that*
  entry; the spawn `.catch` now SIGKILLs a child that spawned before the
  readiness sequence failed; and a periodic **orphan-backend sweeper**
  (POSIX, every 5 min) SIGTERMs any untracked `dashboard` child of the app older
  than 120 s as a safety net against future tracking gaps. (Trigger was benign —
  the primary profile is `kid`, so periodic `default` requests route to the pool;
  the leak was purely the lost-tracking race, now harmless.)

### Added
- **Windows support for the kid one-command setup.**
  `scripts/empower-with-hermes-wjl.sh` is now cross-platform: it detects Windows
  (Git Bash / MSYS / Cygwin) and uses `venv/Scripts/*.exe` instead of
  `venv/bin/*`, and it no longer hard-codes the macOS `~/Library/Application
  Support/Hermes` path (the desktop profile is set by `kid-setup` itself, which
  picks the right per-OS userData dir). Added a native
  `scripts/empower-with-hermes-wjl.ps1` twin so Windows users don't need Git
  Bash — run it with `& ([scriptblock]::Create((irm <url>))) -Key <key>` (no
  execution-policy change). Why: the prior one-liner was macOS-only and failed
  on a child's Windows PC at the Python/launch steps.
- **Git is no longer required on Windows.** `empower-with-hermes-wjl.ps1` now
  falls back to downloading the fork's `main` ZIP and overlaying the source
  (built-in `Invoke-WebRequest` + `Expand-Archive`; no Git, no admin, no
  execution-policy change) when `git` isn't on `PATH`; it still uses git when
  available. The install-present check is gated on the venv, not a `.git` dir.
  Why: a child's fresh Windows PC usually has no Git, which previously hard-
  failed the setup.

### Fixed
- **Desktop build break (`@assistant-ui/store` → `tap/react-shim`).** A rebuild
  (`hermes update` / `--force-build` / fresh-machine install) failed because
  `@assistant-ui/store` floated to `0.2.18`, which peer-depends on
  `@assistant-ui/tap@^0.9.0` and imports `tap/react-shim` — but
  `@assistant-ui/react@0.12.28` pins `tap@^0.5.10` (→ `0.5.14`), which has no
  `react-shim` export. Pinned `@assistant-ui/store` to `0.2.13` via npm
  `overrides` in the root `package.json` (the last `0.2.x` whose peer is
  `tap@^0.5.14` and which imports only `tap` + `tap/react`, both present in
  `0.5.14`). `npm run build` in `apps/desktop` now succeeds. Lockfile diff is
  the single `store` node (4 lines). Investigated/rejected: bumping `tap` to
  `0.9.x` (rejected — `react@0.12.28` + `core@0.1.17` both pin `tap@^0.5.x`, so
  raising `tap` breaks them instead).

### Added
- **`hermes kid-setup` now points the desktop GUI at the kid profile.** It
  writes Electron's own `active-profile.json` (under the app's userData dir,
  cross-platform) in addition to the CLI's `~/.hermes/active_profile`. Why: the
  desktop reads a *separate* file (`readActiveDesktopProfile()` in
  `apps/desktop/electron/main.cjs`), so setting only the CLI profile left the
  GUI opening the default profile — previously patched by hand / by the empower
  script. New `desktop_userdata_dir()` / `write_desktop_active_profile()` mirror
  Electron's path logic; `HERMES_DESKTOP_USERDATA` overrides it for tests.

### Fixed
- **`tests/hermes_cli/test_kid_setup.py` regression** from the builder-mode
  template switch — three tests still asserted the old `safe` lockdown. Updated
  to assert the `hermes-cli` builder toolset, plus new coverage for the desktop
  `active-profile.json` write.

### Changed
- **Kid profile is now builder mode, not lockdown.** `templates/kid-profile/`
  now grants the full `hermes-cli` toolset (websites/games/apps/code/files/
  terminal — same as an adult) with the guardrail moved to **content** instead
  of capability: the persona refuses sexual/violent/occult material and keeps
  web search on safe mode. Why: the child should be able to *build* freely; only
  age-inappropriate web content is off-limits. This makes the published
  one-command `scripts/empower-with-hermes-wjl.sh` → `hermes kid-setup` produce
  the profile the kid letter (`Hermes-for-Kids.md`) describes.
  - `templates/kid-profile/config.yaml`: `platform_toolsets.cli: [hermes-cli]`,
    no `disabled_toolsets`, `max_turns: 60`, builder `kid` persona.
  - `templates/kid-profile/SOUL.md`: "Builder Buddy" identity + firm content
    boundaries.
  - `tests/test_kid_mode.py`: now asserts the full builder toolset + content
    boundaries (4 tests).
  - `docs/kid-mode.md`: reframed from "locked-down assistant" to builder mode
    with an explicit safety caveat (guardrail is cooperative, not a hard wall;
    pair with macOS Screen Time + family DNS).
