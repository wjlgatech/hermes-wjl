import { atom } from 'nanostores'

/**
 * Per-session terminal tabs. Each Hermes session owns its own set of tabs; the
 * pane only shows the active session's, but every session's terminals stay
 * mounted so their PTY + scrollback survive switching away and back. (Moving or
 * unmounting an xterm host detaches its WebGL renderer and drops scrollback —
 * see persistent.tsx — so background tabs are hidden, not unmounted.)
 *
 * The backend already supports N concurrent PTYs: each terminalApi.start()
 * returns its own session id, independent of the Hermes session id.
 *
 * Caveat: every visited-with-terminal session keeps a live shell; browsers cap
 * concurrent WebGL contexts (~16, then the oldest falls back to DOM rendering),
 * and a deleted session's hidden terminal lingers until the window closes.
 */

export interface TerminalTabState {
  key: string
  // Hermes session this tab belongs to (DRAFT_SESSION for an unsaved new chat).
  sessionId: string
  // Working directory the shell was opened in. A session's primary tab (its
  // first) tracks that session's project via syncPrimaryCwd; extra tabs keep
  // the cwd they were opened in.
  cwd: string
  // Shell name reported by the backend once the session starts (e.g. "zsh").
  shell: string
}

// Bucket for a brand-new chat draft, before its first message assigns a real
// session id. rekeyTabs migrates these into the real session once it exists.
export const DRAFT_SESSION = '__draft__'

// Every tab across every session (all kept mounted).
export const $terminalTabs = atom<TerminalTabState[]>([])
// Active tab key per session.
export const $activeTabKeyBySession = atom<Record<string, string>>({})

let counter = 0
const nextKey = () => `term-${(counter += 1)}`

function setActiveForSession(sessionId: string, key: null | string): void {
  const next = { ...$activeTabKeyBySession.get() }

  if (key === null) {
    delete next[sessionId]
  } else {
    next[sessionId] = key
  }

  $activeTabKeyBySession.set(next)
}

const sessionTabs = (sessionId: string) => $terminalTabs.get().filter(tab => tab.sessionId === sessionId)

/** Create the first tab for a session that has none. */
export function ensurePrimaryTab(sessionId: string, cwd: string): void {
  if (sessionTabs(sessionId).length > 0) {
    return
  }

  const key = nextKey()
  $terminalTabs.set([...$terminalTabs.get(), { cwd, key, sessionId, shell: 'shell' }])
  setActiveForSession(sessionId, key)
}

/**
 * Point a session's primary tab at its project (and create it on first run);
 * extra tabs are never retargeted.
 */
export function syncPrimaryCwd(sessionId: string, cwd: string): void {
  const tabs = sessionTabs(sessionId)

  if (tabs.length === 0) {
    ensurePrimaryTab(sessionId, cwd)

    return
  }

  const primary = tabs[0]

  if (primary.cwd === cwd) {
    return
  }

  $terminalTabs.set($terminalTabs.get().map(tab => (tab.key === primary.key ? { ...tab, cwd } : tab)))
}

/** Open a new shell tab in `cwd` for `sessionId` and focus it. */
export function addTerminalTab(sessionId: string, cwd: string): void {
  const key = nextKey()
  $terminalTabs.set([...$terminalTabs.get(), { cwd, key, sessionId, shell: 'shell' }])
  setActiveForSession(sessionId, key)
}

export function setActiveTerminalTab(key: string): void {
  const tab = $terminalTabs.get().find(entry => entry.key === key)

  if (tab) {
    setActiveForSession(tab.sessionId, key)
  }
}

export function setTabShell(key: string, shell: string): void {
  $terminalTabs.set($terminalTabs.get().map(tab => (tab.key === key ? { ...tab, shell } : tab)))
}

/**
 * Remove a tab. When the closed tab was its session's active one, focus the
 * nearest neighbor. Returns true when the session has no tabs left so the
 * caller can hide the pane.
 */
export function closeTerminalTab(key: string): boolean {
  const tab = $terminalTabs.get().find(entry => entry.key === key)

  if (!tab) {
    return false
  }

  const { sessionId } = tab
  const before = sessionTabs(sessionId)
  const index = before.findIndex(entry => entry.key === key)

  $terminalTabs.set($terminalTabs.get().filter(entry => entry.key !== key))

  const remaining = sessionTabs(sessionId)

  if ($activeTabKeyBySession.get()[sessionId] === key) {
    const neighbor = remaining[index] ?? remaining[index - 1] ?? null
    setActiveForSession(sessionId, neighbor ? neighbor.key : null)
  }

  return remaining.length === 0
}

/**
 * Migrate a draft session's tabs onto the real id assigned after its first
 * message. No-op when there's nothing to move or the target already has tabs.
 */
export function rekeyTabs(from: string, to: string): void {
  if (from === to) {
    return
  }

  const tabs = $terminalTabs.get()

  if (!tabs.some(tab => tab.sessionId === from) || tabs.some(tab => tab.sessionId === to)) {
    return
  }

  $terminalTabs.set(tabs.map(tab => (tab.sessionId === from ? { ...tab, sessionId: to } : tab)))

  const active = $activeTabKeyBySession.get()

  if (active[from] != null) {
    const next = { ...active, [to]: active[from] }
    delete next[from]
    $activeTabKeyBySession.set(next)
  }
}
