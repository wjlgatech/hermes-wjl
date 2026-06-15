# Kid-mode distribution — what's needed for a download-and-double-click installer

The kid experience (locked-down profile, free LLM, `hermes kid-setup`) and the
fork redirection are **done and tested**. The remaining piece — a signed,
hosted installer a child can download and double-click — is **not finished**
because it depends on assets and accounts that can't be produced in-repo. This
doc is the concrete checklist (covers plan units U2, U3, U7).

## Status

| Piece | State |
|-------|-------|
| Fork redirection (clone/update → `wjlgatech/hermes-wjl`) | ✅ Done (U1) |
| Locked-down kid profile + `/free-llm-kid` + `hermes kid-setup` | ✅ Done & tested (U4/U5/U6) |
| Rebranded Tauri bootstrap installer identifier (U2) | ✅ Done |
| Installer → `hermes kid-setup` wiring — `--kid` (U7) | ✅ `install.sh` done; `install.ps1` done (unverified — needs a Windows run) |
| Cross-platform build/publish workflow + download page (U3) | ✅ Authored (`build-sign-installers.yml`, `docs/download.md`) — builds **unsigned** today |
| **Code-signing + notarization** (U3) | ⛔ **Needs your certs** — the only true blocker left |

**What's left is the signing itself:** add the certificate secrets below and cut
a tagged release. The build pipeline already runs (unsigned) without them.

## Prerequisites you must provide (U3)

These cannot be created from the repo:

- **macOS:** an **Apple Developer ID Application** certificate + an
  app-specific password / API key for **notarization**. Without it, Gatekeeper
  blocks the app on the child's Mac.
- **Windows:** an **Authenticode** code-signing certificate (OV or EV). Without
  it, SmartScreen warns on launch.
- **Hosting:** somewhere to publish the installers and the `install.sh` /
  `install.ps1` one-liners for the fork (the current one-liner host,
  `hermes-agent.nousresearch.com`, is upstream infrastructure). GitHub Releases
  + a small download page is the cheapest option.
- **CI runners:** macOS + Windows + Linux runners to build per-OS (GitHub
  Actions hosted runners suffice).

## What's left to build once the above exist

1. **U2 — rebrand the Tauri bootstrap installer**
   `apps/bootstrap-installer/src-tauri/tauri.conf.json`: product name,
   bundle identifier, icons, window title. (The installer already fetches its
   scripts from the fork via the U1 `fork-override` in `install_script.rs`.)

2. **U3 — sign, notarize, host**
   - electron-builder signing config in `apps/desktop/package.json`
     (`mac.notarize`, `win` signing) fed by CI secrets.
   - A `.github/workflows/build-sign-installers.yml` that builds the desktop app
     (dmg/zip, nsis/msi, AppImage/deb/rpm) + the bootstrap installer per OS,
     signs/notarizes, and publishes to GitHub Releases.
   - A fork download page (replace the `nousresearch.com` links in
     `website/docs/index.mdx`).
   - A distinct fork `appId` (e.g. `com.wjlgatech.hermes-wjl`) is appropriate
     here — see `branding/fork-identity.md` (left unchanged until now to avoid
     disturbing the existing install's identity).

3. **U7 — installer runs kid-setup**
   - A `--kid` install mode in `scripts/install.sh` / `install.ps1` that runs
     `hermes kid-setup` after the standard clone/venv/build.
   - A kid-setup stage in `apps/bootstrap-installer/src-tauri/src/bootstrap.rs`.

## Interim path (no certificates needed)

Until the above is in place, use the documented command flow in
[`docs/kid-mode.md`](kid-mode.md): install the fork via the one-liner, then run
`hermes kid-setup`. Unsigned local builds (`hermes desktop`) also work for
testing — they just trip Gatekeeper/SmartScreen, which is why they aren't
suitable for handing to a child yet.
