# Changelog

All notable changes to this fork (`wjlgatech/hermes-wjl`) are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
