# Hermes Kid Mode — parent guide

Set up Hermes for a child in **builder mode**: full builder powers (websites,
games, apps, code, files, terminal — like an adult), a child-appropriate persona,
**content guardrails** (no sexual/violent/occult material; safe-search; family
faith-friendly), and a **free** LLM by default — running on **this fork**
(`wjlgatech/hermes-wjl`).

> **Safety, honestly:** the content guardrail is the model's *instructions*
> (cooperative), **not a hard technical wall** — and the child has full
> web/terminal/file powers. Pair it with **macOS Screen Time → Web Content →
> Limit Adult Websites** and a **family DNS filter**, and supervise. Conversations
> live under the child's profile and can be reviewed any time.

---

## TL;DR

On the child's machine, once Hermes is installed:

```bash
hermes kid-setup            # free-tier cloud LLM, falls back to local
hermes desktop              # opens straight into kid builder mode
```

That's it — no sign-in screen, no API keys for the child to enter.

---

## What kid mode does

`hermes kid-setup` creates a profile (default name `kid`) seeded from
`templates/kid-profile/` and makes it the active profile, so the desktop app
opens into it with **no onboarding wall**. The profile:

- **Grants full builder tools** — the same `hermes-cli` toolset an adult gets:
  terminal, code execution, file editing, browser automation, web, and image.
  The child can build websites, games, and apps for real.
- **Uses a builder persona with content boundaries** (warm, step-by-step;
  refuses sexual/violent/occult material; keeps web search on safe mode; never
  asks for personal info; says what it's about to do before changing important
  files) — see `templates/kid-profile/SOUL.md`.
- **Bounds turns** (`max_turns: 60`) to give room to actually build.

Re-running `hermes kid-setup` re-applies the template, so it also *repairs* a
profile that's been tampered with.

---

## Choosing the LLM

`hermes kid-setup --llm <mode>` (the `/free-llm-kid` skill explains the choices):

| Mode | Command | What it is | Trade-off |
|------|---------|-----------|-----------|
| **free** (default) | `hermes kid-setup --llm free` | Free-tier cloud: NVIDIA NIM, Groq, or Gemini | Free to you, good quality; needs a one-time **free key** (you get it) and is rate-limited |
| **local** | `hermes kid-setup --llm local` | A model on the child's machine via **Ollama** | Private, offline, no key; needs a capable machine + a model download, lower quality |
| **inherit** | `hermes kid-setup --llm inherit` | Copies **your** key + model into the kid profile | Instant, full quality; but a paid key on the child's machine carries **cost/abuse risk** |

Recommended: **free with local fallback** — try the free cloud model, fall back
to local when there's no key, it's rate-limited, or you're offline.

### Getting a free key (you do this once)

| Provider | Where | Env var |
|----------|-------|---------|
| NVIDIA NIM (default) | <https://build.nvidia.com> | `NVIDIA_API_KEY` |
| Groq | <https://console.groq.com/keys> | `GROQ_API_KEY` |
| Gemini | <https://aistudio.google.com/apikey> | `GEMINI_API_KEY` |

Then: `hermes kid-setup --llm free --provider nvidia --key <your-key>`
(or set the env var and omit `--key`).

No key handy? `hermes kid-setup --llm local` needs none — install
[Ollama](https://ollama.com) and `ollama pull llama3.2` first.

---

## Reviewing and changing things

- **Review chats:** the child's conversations are stored under their profile
  (`~/.hermes/profiles/kid/sessions/`). You can also open the profile in the
  desktop app and read the history.
- **Switch the model later:** re-run `hermes kid-setup --llm <mode> …`.
- **Switch back to your own profile:** in the desktop app's profile switcher, or
  `hermes profile use default`.
- **Update Hermes:** `hermes update` (pulls the latest from this fork).

---

## Installing Hermes (today vs. the goal)

**Already have the Hermes desktop app? One command** re-points it at this fork
and sets up the kid profile (no re-download, no rebuild). Get a free NVIDIA key
at <https://build.nvidia.com> first.

**macOS / Linux** (Terminal):

```bash
curl -fsSL https://raw.githubusercontent.com/wjlgatech/hermes-wjl/main/scripts/empower-with-hermes-wjl.sh | bash -s -- --key <YOUR_FREE_NVIDIA_KEY>
```

**Windows** (PowerShell — no Git Bash needed):

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/wjlgatech/hermes-wjl/main/scripts/empower-with-hermes-wjl.ps1))) -Key <YOUR_FREE_NVIDIA_KEY>
```

Windows prerequisite: just the Hermes desktop app already installed. **Git is
not required** — if it's missing, the PowerShell script updates by downloading
the fork's `main` as a ZIP and overlaying the source (built-in PowerShell only;
no admin, no execution-policy change). If Git *is* present it's used instead.
(The same `.sh` one-liner also works inside Git Bash — it detects Windows and
uses `venv\Scripts\` automatically.)

**Fresh install (no app yet):** the fork's installer + `hermes kid-setup`:

```bash
curl -fsSL https://raw.githubusercontent.com/wjlgatech/hermes-wjl/main/scripts/install.sh | bash
hermes kid-setup --llm free --provider nvidia --key <YOUR_FREE_NVIDIA_KEY>
hermes desktop
```

> ℹ️ A desktop **rebuild** (`hermes update` / `--force-build`, and a
> fresh-machine install that builds the app) previously failed on an upstream
> `@assistant-ui` dependency mismatch (`store` floated to a version importing a
> `tap/react-shim` path no compatible `tap` exports). **Fixed** in this fork via
> an npm `overrides` pin (`@assistant-ui/store` → `0.2.13`, the last release
> compatible with the `tap 0.5.x` the rest of the tree uses) — `npm run build`
> succeeds.

**The goal — a true download-and-double-click installer for the child** — is
tracked but **not finished**: it needs code-signing/notarization certificates
and hosting. See [`docs/kid-mode-distribution.md`](kid-mode-distribution.md) for
exactly what's required and what's left to build.
