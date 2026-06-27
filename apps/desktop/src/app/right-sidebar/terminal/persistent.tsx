import { useStore } from '@nanostores/react'
import { atom } from 'nanostores'
import { type CSSProperties, useEffect, useLayoutEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'

import { $terminalTakeover } from '../store'

import { $activeTabKeyBySession, $terminalTabs, DRAFT_SESSION, rekeyTabs, syncPrimaryCwd } from './tabs'

import { TerminalBody, TerminalHeader } from './index'

/**
 * One xterm Terminal per tab, all mounted at the layout root and CSS-overlayed
 * onto whichever `<TerminalSlot />` is active. Moving the host DOM detaches
 * xterm's WebGL renderer (it observes its own attachment) and resets the screen,
 * so the hosts stay put and we chase the slot's bounding rect with position:fixed.
 * Background tabs stay mounted (hidden) so their renderer + scrollback survive.
 */

const $slot = atom<HTMLElement | null>(null)

const SLOT_CLASS = 'relative flex min-h-0 min-w-0 flex-1 flex-col'

export function TerminalSlot({ className = SLOT_CLASS }: { className?: string }) {
  const ref = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const el = ref.current

    if (!el) {
      return
    }

    $slot.set(el)

    return () => {
      if ($slot.get() === el) {
        $slot.set(null)
      }
    }
  }, [])

  return <div className={className} ref={ref} />
}

interface PersistentTerminalProps {
  cwd: string
  onAddSelectionToChat: (text: string, label?: string) => void
  // Active Hermes session; null for an unsaved new-chat draft. Each session owns
  // its own tab set, so the pane swaps tabs when this changes.
  sessionId: null | string
}

interface Rect {
  top: number
  left: number
  width: number
  height: number
}

const sameRect = (a: Rect | null, b: Rect) =>
  !!a && a.top === b.top && a.left === b.left && a.width === b.width && a.height === b.height

export function PersistentTerminal({ cwd, onAddSelectionToChat, sessionId }: PersistentTerminalProps) {
  const slot = useStore($slot)
  const tabs = useStore($terminalTabs)
  const activeBySession = useStore($activeTabKeyBySession)
  const takeover = useStore($terminalTakeover)
  const [rect, setRect] = useState<Rect | null>(null)
  const [ready, setReady] = useState(false)

  // Tabs live under the real session id, or a draft bucket until the chat is
  // saved. activeKey is this session's focused tab.
  const bucket = sessionId || DRAFT_SESSION
  const activeKey = activeBySession[bucket]

  // While the pane is open, ensure this session has a primary tab pointed at its
  // project (extra tabs keep their own cwd), and fold any draft tabs into the
  // session once it's saved. Gating on `takeover` means closing the last tab —
  // which hides the pane — doesn't immediately respawn a shell; reopening
  // recreates one.
  useEffect(() => {
    if (takeover) {
      if (sessionId) {
        rekeyTabs(DRAFT_SESSION, sessionId)
      }

      syncPrimaryCwd(bucket, cwd)
    }
  }, [bucket, cwd, sessionId, takeover])

  useLayoutEffect(() => {
    if (!slot) {
      setRect(null)

      return
    }

    let prev: Rect | null = null
    let frame = 0

    const tick = () => {
      const r = slot.getBoundingClientRect()
      // floor top/left + ceil right/bottom: overlay always covers the slot's
      // full pixel footprint, so half-pixel rects can't leak page bg through.
      const top = Math.floor(r.top)
      const left = Math.floor(r.left)
      const next: Rect = { top, left, width: Math.ceil(r.right) - left, height: Math.ceil(r.bottom) - top }

      if (!sameRect(prev, next)) {
        prev = next
        setRect(next)

        if (next.width > 0 && next.height > 0) {
          setReady(true)
        }
      }

      frame = requestAnimationFrame(tick)
    }

    tick()

    return () => cancelAnimationFrame(frame)
  }, [slot])

  const visible = Boolean(rect && rect.width > 0 && rect.height > 0)

  const style: CSSProperties = {
    position: 'fixed',
    top: rect?.top ?? 0,
    left: rect?.left ?? 0,
    width: rect?.width ?? 0,
    height: rect?.height ?? 0,
    display: 'flex',
    flexDirection: 'column',
    visibility: visible ? 'visible' : 'hidden',
    pointerEvents: visible ? 'auto' : 'none',
    zIndex: 4,
    // Match the live skin surface so the header strip (transparent) and body
    // read as one cohesive pane instead of revealing a near-black slab behind.
    backgroundColor: 'var(--ui-editor-surface-background)',
    contain: 'layout size paint'
  }

  // Defer mount until the terminal sidebar is open and the slot has real dims.
  // Booting xterm/node-pty at 0×0 starts the shell at 80×24 and spawns a
  // visible conhost on Windows even when the pane is collapsed.
  return (
    <div aria-hidden={!visible} style={style}>
      {ready && (
        <>
          <TerminalHeader sessionId={bucket} />
          <div className="relative min-h-0 flex-1">
            {tabs.map(tab => {
              // Visible only when it's the active session's active tab; every
              // other tab (incl. background sessions') stays mounted but hidden.
              const isCurrent = tab.sessionId === bucket && tab.key === activeKey

              return (
                <div
                  className={cn(
                    'absolute inset-0 flex flex-col',
                    isCurrent ? 'z-10' : 'invisible z-0 pointer-events-none'
                  )}
                  key={tab.key}
                >
                  <TerminalBody
                    active={isCurrent}
                    cwd={tab.cwd}
                    onAddSelectionToChat={onAddSelectionToChat}
                    tabKey={tab.key}
                  />
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
