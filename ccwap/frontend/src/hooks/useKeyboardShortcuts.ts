import { useEffect } from 'react'
import { useNavigate } from 'react-router'

const PAGE_SHORTCUTS: Record<string, string> = {
  '1': '/',
  '2': '/projects',
  '3': '/sessions',
  '4': '/cost',
  '5': '/productivity',
  '6': '/analytics',
  '7': '/experiments',
  '8': '/live',
  '9': '/settings',
}

export function useKeyboardShortcuts(onCommandK?: () => void) {
  const navigate = useNavigate()

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) return

      // Cmd+K / Ctrl+K for command palette
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        onCommandK?.()
        return
      }

      // Alt+1-9 for page navigation
      if (e.altKey && PAGE_SHORTCUTS[e.key]) {
        e.preventDefault()
        navigate(PAGE_SHORTCUTS[e.key])
      }
    }

    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [navigate, onCommandK])
}
