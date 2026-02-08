import type { ReactNode } from 'react'
import { Sidebar } from '@/components/layout/Sidebar'
import { TopBar } from '@/components/layout/TopBar'
import { TooltipProvider } from '@/components/ui/tooltip'

interface AppShellProps {
  children: ReactNode
  collapsed: boolean
  onToggleSidebar: () => void
  isMobile: boolean
  mobileOpen: boolean
  onMobileOpen: () => void
  onMobileClose: () => void
  onCommandK?: () => void
}

export function AppShell({
  children,
  collapsed,
  onToggleSidebar,
  isMobile,
  mobileOpen,
  onMobileOpen,
  onMobileClose,
  onCommandK,
}: AppShellProps) {
  return (
    <TooltipProvider>
      <div className="flex h-screen bg-background text-foreground">
        <Sidebar
          collapsed={collapsed}
          onToggle={onToggleSidebar}
          isMobile={isMobile}
          mobileOpen={mobileOpen}
          onMobileClose={onMobileClose}
        />
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <TopBar
            onCommandK={onCommandK}
            isMobile={isMobile}
            onMobileMenuOpen={onMobileOpen}
          />
          <main className="flex-1 overflow-y-auto p-6">
            {children}
          </main>
        </div>
      </div>
    </TooltipProvider>
  )
}
