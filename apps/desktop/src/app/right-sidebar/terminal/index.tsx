import '@xterm/xterm/css/xterm.css'

import { useStore } from '@nanostores/react'
import { useCallback } from 'react'

import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { KbdCombo } from '@/components/ui/kbd'
import { Loader } from '@/components/ui/loader'
import { Tip } from '@/components/ui/tooltip'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'

import { setTerminalTakeover } from '../store'

import {
  $activeTabKeyBySession,
  $terminalTabs,
  addTerminalTab,
  closeTerminalTab,
  setActiveTerminalTab,
  setTabShell
} from './tabs'
import { useTerminalSession } from './use-terminal-session'

/**
 * The shared tab strip above the stacked terminals for the active session: one
 * button per tab (click to focus, ✕ to close), a "+" to open another shell, and
 * the hide-pane button.
 */
export function TerminalHeader({ sessionId }: { sessionId: string }) {
  const { t } = useI18n()
  const allTabs = useStore($terminalTabs)
  const activeBySession = useStore($activeTabKeyBySession)
  const tabs = allTabs.filter(tab => tab.sessionId === sessionId)
  const activeKey = activeBySession[sessionId]

  const handleAdd = () => {
    const current = tabs.find(tab => tab.key === activeKey) ?? tabs[0]
    addTerminalTab(sessionId, current?.cwd ?? '')
  }

  const handleClose = (key: string) => {
    // Closing the last tab leaves nothing to show — hide the pane.
    if (closeTerminalTab(key)) {
      setTerminalTakeover(false)
    }
  }

  return (
    <div className="flex h-8 shrink-0 items-center gap-1 px-2">
      <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
        {tabs.map(tab => {
          const isActive = tab.key === activeKey

          return (
            <div
              aria-selected={isActive}
              className={cn(
                'group flex h-6 shrink-0 cursor-pointer select-none items-center gap-1 rounded-md py-0 pl-2 pr-1',
                isActive
                  ? 'bg-(--ui-row-active-background) text-(--theme-primary)'
                  : 'text-(--ui-text-secondary) hover:bg-(--ui-row-hover-background)'
              )}
              key={tab.key}
              onClick={() => setActiveTerminalTab(tab.key)}
              role="tab"
            >
              <span className="max-w-28 truncate text-[0.64rem] font-semibold uppercase tracking-[0.16em] leading-none">
                {tab.shell}
              </span>
              {tabs.length > 1 && (
                <Tip label={t.rightSidebar.terminalCloseTab}>
                  <Button
                    aria-label={t.rightSidebar.terminalCloseTab}
                    className="size-4 rounded text-current opacity-0 group-hover:opacity-70 hover:opacity-100!"
                    onClick={event => {
                      event.stopPropagation()
                      handleClose(tab.key)
                    }}
                    size="icon"
                    type="button"
                    variant="ghost"
                  >
                    <Codicon name="close" size="0.7rem" />
                  </Button>
                </Tip>
              )}
            </div>
          )
        })}
      </div>
      <Tip label={t.rightSidebar.terminalNewTab}>
        <Button
          aria-label={t.rightSidebar.terminalNewTab}
          className="size-6 shrink-0 rounded-md text-(--ui-text-secondary)!"
          onClick={handleAdd}
          size="icon"
          type="button"
          variant="ghost"
        >
          <Codicon name="add" size="0.875rem" />
        </Button>
      </Tip>
      <Tip label={t.rightSidebar.terminalHide}>
        <Button
          aria-label={t.rightSidebar.terminalHide}
          className="size-6 shrink-0 rounded-md text-(--ui-text-secondary)!"
          onClick={() => setTerminalTakeover(false)}
          size="icon"
          type="button"
          variant="ghost"
        >
          <Codicon name="close" size="0.875rem" />
        </Button>
      </Tip>
    </div>
  )
}

interface TerminalBodyProps {
  active: boolean
  cwd: string
  onAddSelectionToChat: (text: string, label?: string) => void
  tabKey: string
}

/** One terminal's xterm host + selection overlay. Stays mounted while hidden so
 *  its WebGL renderer and scrollback survive tab switches. */
export function TerminalBody({ active, cwd, onAddSelectionToChat, tabKey }: TerminalBodyProps) {
  const { t } = useI18n()

  const onShell = useCallback((shell: string) => setTabShell(tabKey, shell), [tabKey])

  const { addSelectionToChat, hostRef, selection, selectionStyle, status } = useTerminalSession({
    active,
    cwd,
    onAddSelectionToChat,
    onShell
  })

  return (
    <div className="relative min-h-0 flex-1 bg-(--ui-editor-surface-background) p-2">
      {status === 'starting' && (
        <div className="pointer-events-none absolute inset-0 z-10 grid place-items-center">
          <Loader
            className="size-8 text-(--ui-text-tertiary)"
            pathSteps={180}
            strokeScale={0.68}
            type="spiral-search"
          />
        </div>
      )}
      {selection.trim() && (
        <div className="absolute z-50 flex items-center gap-1" style={selectionStyle ?? { right: 12, top: 8 }}>
          <Button
            className="h-6 rounded-md px-2 text-[0.68rem] shadow-md backdrop-blur-md"
            onClick={event => event.preventDefault()}
            onMouseDown={event => {
              event.preventDefault()
              event.stopPropagation()
              addSelectionToChat()
            }}
            type="button"
            variant="secondary"
          >
            {t.rightSidebar.addToChat}
            <KbdCombo className="ml-1 opacity-70" combo="mod+l" size="sm" />
          </Button>
        </div>
      )}
      {/* Outer div paints terminal inset; inner div is the xterm host so the
          canvas sizes to the content area and p-2 stays as terminal padding.
          Screen/viewport inherit the live skin surface so the terminal blends
          with the app and follows light/dark; the xterm canvas itself is
          painted the resolved surface color in use-terminal-session. */}
      <div
        className="h-full min-h-0 overflow-hidden text-(--ui-text-secondary) [&_.xterm]:h-full [&_.xterm-screen]:bg-(--ui-editor-surface-background)! [&_.xterm-viewport]:bg-(--ui-editor-surface-background)!"
        ref={hostRef}
      />
    </div>
  )
}
