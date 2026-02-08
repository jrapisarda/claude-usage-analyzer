import { useState, useCallback } from 'react'
import { useLocalStorage } from './useLocalStorage'
import { useMediaQuery } from './useMediaQuery'

export function useSidebar() {
  const [collapsed, setCollapsed] = useLocalStorage('ccwap:sidebar-collapsed', false)
  const isMobile = useMediaQuery('(max-width: 1023px)')
  const [mobileOpen, setMobileOpen] = useState(false)

  const toggleSidebar = useCallback(() => {
    if (isMobile) {
      setMobileOpen(prev => !prev)
    } else {
      setCollapsed((prev: boolean) => !prev)
    }
  }, [isMobile, setCollapsed])

  const openMobile = useCallback(() => {
    setMobileOpen(true)
  }, [])

  const closeMobile = useCallback(() => {
    setMobileOpen(false)
  }, [])

  return {
    collapsed: isMobile ? false : collapsed,
    isMobile,
    mobileOpen,
    toggleSidebar,
    openMobile,
    closeMobile,
    // Keep old API for backward compat
    setCollapsed,
    setMobileOpen,
    toggle: toggleSidebar,
  }
}
