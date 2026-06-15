---
name: free-llm-kid
description: "Set up a free, kid-safe LLM for a child's Hermes profile: free-tier cloud (NVIDIA NIM / Groq / Gemini) with automatic fallback to a local Ollama model, or inherit a parent's credential. Parent-assisted, no cost by default."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [kid, child, free, llm, nvidia, nim, groq, gemini, ollama, local, safe, parent]
    related_skills: [free-llm]
---

# Free LLM for Kids

Configure the model for a child's **kid profile** (`~/.hermes/profiles/<kid>/`)
so it runs on a **free** LLM by default, with a safe fallback — no paid keys
required, no cost to the parent.

This is the kid-safe sibling of the `free-llm` skill. It writes into the kid
profile only, and a **parent/guardian performs any signup steps** — never the
child.

## The three options (default: free → local)

| Mode | What it is | Trade-off |
|------|-----------|-----------|
| **free** (default) | A free-tier cloud model: NVIDIA NIM (`build.nvidia.com`), Groq, or Google Gemini | Good quality, free, but needs a one-time **free key signup** (parent does this) and is rate-limited |
| **local** (fallback) | A model on the child's own machine via **Ollama** | Private, offline, zero cost — but needs a capable machine + a model download, and lower quality |
| **inherit** (opt-in) | Copy the **parent's** API key + model into the kid profile | Works instantly at full quality, but a paid key on the child's machine carries **cost/abuse risk** |

The recommended setup is **free with automatic fallback to local**: try the
free-tier cloud model; if there's no key, it's rate-limited, or the machine is
offline, fall back to the local Ollama model.

## How to run it

The actual configuration is performed by the **`hermes kid-setup`** command,
which creates/repairs the kid profile and writes the model config + key. This
skill is the guide for choosing a mode and getting a free key.

```bash
# Free-tier cloud (default provider: NVIDIA NIM), with local fallback:
hermes kid-setup --llm free

# Pick a specific free provider:
hermes kid-setup --llm free --provider groq      # or: nvidia | gemini

# Local-only (Ollama on this machine):
hermes kid-setup --llm local

# Inherit the parent's current credential (opt-in; cost/abuse warning shown):
hermes kid-setup --llm inherit
```

## Getting a free key (parent step)

Free-tier providers need a one-time, no-cost key. Do this as the parent:

- **NVIDIA NIM** — sign in at <https://build.nvidia.com>, create an API key
  (free tier ~40 req/min). Provide it when `kid-setup` asks, or set
  `NVIDIA_API_KEY`.
- **Groq** — get a free key at <https://console.groq.com/keys> (`GROQ_API_KEY`).
- **Gemini** — get a free key at <https://aistudio.google.com/apikey>
  (`GEMINI_API_KEY`).

No key handy? Run `hermes kid-setup --llm local` — Ollama needs no key. Install
Ollama and pull a small model first (e.g. `ollama pull llama3.2`).

## Safety note

This skill only sets the **model**. The kid profile's tool lockdown and
child-appropriate persona come from the kid-mode template (see
`templates/kid-profile/`). Even so, a free/safe model can still produce
content that needs a grown-up's judgment — **adult supervision is expected**.
See `docs/kid-mode.md`.
