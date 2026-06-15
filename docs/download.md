# Download Hermes Desktop (hermes-wjl fork)

Installers for this fork are published to **GitHub Releases** and built by
[`.github/workflows/build-sign-installers.yml`](../.github/workflows/build-sign-installers.yml).

## Get the latest installer

→ **<https://github.com/wjlgatech/hermes-wjl/releases/latest>**

| Platform | File |
|----------|------|
| macOS | `Hermes-<version>-mac-<arch>.dmg` |
| Windows | `Hermes-<version>-win-<arch>.exe` |
| Linux | `Hermes-<version>-linux-<arch>.AppImage` (also `.deb` / `.rpm`) |

Download the file for your platform and open it.

> **Signing status:** until the Apple Developer ID and Windows Authenticode
> certificates are configured (see
> [`kid-mode-distribution.md`](kid-mode-distribution.md)), these builds are
> **unsigned** — macOS Gatekeeper and Windows SmartScreen will warn on first
> launch. That's why they're not yet suitable for handing to a child; use the
> command path below in the meantime.

## Prefer the command line?

```bash
curl -fsSL https://raw.githubusercontent.com/wjlgatech/hermes-wjl/main/scripts/install.sh | bash
```

For a child, add `--kid` to land in locked-down kid mode automatically:

```bash
curl -fsSL https://raw.githubusercontent.com/wjlgatech/hermes-wjl/main/scripts/install.sh | bash -s -- --kid
```

See [`kid-mode.md`](kid-mode.md) for the kid setup details.

## Cutting a release (maintainer)

1. Add the signing secrets to the repo (see `kid-mode-distribution.md`).
2. Tag a version: `git tag v0.x.y && git push origin v0.x.y`.
3. The workflow builds all three platforms, signs/notarizes when secrets are
   present, and attaches the installers to the `v0.x.y` GitHub Release.
