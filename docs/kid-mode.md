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
hermes desktop              # opens straight into locked-down kid mode
```

That's it — no sign-in screen, no API keys for the child to enter.

---

## What kid mode does

`hermes kid-setup` creates a profile (default name `kid`) seeded from
`templates/kid-profile/` and makes it the active profile, so the desktop app
opens into it with **no onboarding wall**. The profile:

- **Restricts tools** to a safe allowlist — only web search, web read, image
  understanding, and image generation. No terminal, file editing, browser
  automation, code execution, task delegation, scheduling, or messaging.
- **Uses a child persona** (simple, warm, encouraging; declines unsafe topics;
  never asks for personal info) — see `templates/kid-profile/SOUL.md`.
- **Bounds conversations** to keep them short.

Re-running `hermes kid-setup` re-applies the lockdown, so it also *repairs* a
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
at <https://build.nvidia.com> first:

```bash
curl -fsSL https://raw.githubusercontent.com/wjlgatech/hermes-wjl/main/scripts/empower-with-hermes-wjl.sh | bash -s -- --key <YOUR_FREE_NVIDIA_KEY>
```

**Fresh install (no app yet):** the fork's installer + `hermes kid-setup`:

```bash
curl -fsSL https://raw.githubusercontent.com/wjlgatech/hermes-wjl/main/scripts/install.sh | bash
hermes kid-setup --llm free --provider nvidia --key <YOUR_FREE_NVIDIA_KEY>
hermes desktop
```

> ⚠️ **Known issue:** a desktop **rebuild** (`hermes update` / `--force-build`,
> and therefore a fresh-machine install that builds the app) currently fails on
> an upstream `@assistant-ui` dependency mismatch (`store` imports a
> `tap/react-shim` path no published `tap` exports). The **one-command re-point
> above works** because it reuses the existing built app (`--skip-build`). Fix
> tracked separately.

**The goal — a true download-and-double-click installer for the child** — is
tracked but **not finished**: it needs code-signing/notarization certificates
and hosting. See [`docs/kid-mode-distribution.md`](kid-mode-distribution.md) for
exactly what's required and what's left to build.
