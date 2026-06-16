# Changelog

All notable changes to this fork (`wjlgatech/hermes-wjl`) are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
