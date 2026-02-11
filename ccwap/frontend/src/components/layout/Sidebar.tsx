import { NavLink } from 'react-router'
import {
  LayoutDashboard, FolderKanban, List, DollarSign, Zap,
  BarChart3, FlaskConical, Radio, Settings, CalendarDays,
  Brain, GitBranch, Telescope, PanelLeftClose, PanelLeft,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'

interface NavItem {
  to: string
  icon: React.ComponentType<{ className?: string }>
  label: string
}

interface NavSection {
  title: string
  items: NavItem[]
}

const navSections: NavSection[] = [
  {
    title: 'Overview',
    items: [
      { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    ],
  },
  {
    title: 'Data',
    items: [
      { to: '/projects', icon: FolderKanban, label: 'Projects' },
      { to: '/sessions', icon: List, label: 'Sessions' },
      { to: '/explorer', icon: Telescope, label: 'Explorer' },
    ],
  },
  {
    title: 'Analysis',
    items: [
      { to: '/cost', icon: DollarSign, label: 'Cost Analysis' },
      { to: '/productivity', icon: Zap, label: 'Productivity' },
      { to: '/analytics', icon: BarChart3, label: 'Deep Analytics' },
      { to: '/heatmap', icon: CalendarDays, label: 'Activity Heatmap' },
      { to: '/models', icon: Brain, label: 'Model Comparison' },
      { to: '/workflows', icon: GitBranch, label: 'Workflows' },
    ],
  },
  {
    title: 'Advanced',
    items: [
      { to: '/experiments', icon: FlaskConical, label: 'Experiments' },
      { to: '/live', icon: Radio, label: 'Live Monitor' },
    ],
  },
  {
    title: 'System',
    items: [
      { to: '/settings', icon: Settings, label: 'Settings' },
    ],
  },
]

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
  isMobile: boolean
  mobileOpen: boolean
  onMobileClose: () => void
}

function NavItemLink({
  item,
  collapsed,
}: {
  item: NavItem
  collapsed: boolean
}) {
  const link = (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 rounded-md text-sm transition-colors',
          collapsed ? 'justify-center px-2 py-2' : 'px-3 py-2',
          isActive
            ? 'bg-accent text-accent-foreground font-medium'
            : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
        )
      }
    >
      <item.icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span>{item.label}</span>}
    </NavLink>
  )

  if (collapsed) {
    return (
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>{link}</TooltipTrigger>
        <TooltipContent side="right" sideOffset={10}>
          {item.label}
        </TooltipContent>
      </Tooltip>
    )
  }

  return link
}

function SidebarContent({ collapsed }: { collapsed: boolean }) {
  return (
    <ScrollArea className="flex-1">
      <nav className="p-2 space-y-4">
        {navSections.map((section, sectionIdx) => (
          <div key={section.title}>
            {sectionIdx > 0 && <Separator className="mb-3" />}
            {!collapsed && (
              <p className="px-3 mb-1 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                {section.title}
              </p>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => (
                <NavItemLink
                  key={item.to}
                  item={item}
                  collapsed={collapsed}
                />
              ))}
            </div>
          </div>
        ))}
      </nav>
    </ScrollArea>
  )
}

export function Sidebar({ collapsed, onToggle, isMobile, mobileOpen, onMobileClose }: SidebarProps) {
  // Mobile sidebar: renders as a Sheet overlay
  if (isMobile) {
    return (
      <Sheet open={mobileOpen} onOpenChange={(open) => !open && onMobileClose()}>
        <SheetContent side="left" className="w-56 p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <div className="flex flex-col h-full">
            <div className="p-4 border-b border-border">
              <h1 className="text-lg font-bold tracking-tight">CCWAP</h1>
              <p className="text-xs text-muted-foreground">Claude Code Analytics</p>
            </div>
            <SidebarContent collapsed={false} />
          </div>
        </SheetContent>
      </Sheet>
    )
  }

  // Desktop sidebar
  return (
    <aside
      className={cn(
        'shrink-0 border-r border-border bg-card h-screen sticky top-0 flex flex-col transition-all duration-200',
        collapsed ? 'w-14' : 'w-56'
      )}
    >
      <div className={cn('border-b border-border', collapsed ? 'p-2' : 'p-4')}>
        {collapsed ? (
          <div className="flex justify-center">
            <span className="text-sm font-bold">CC</span>
          </div>
        ) : (
          <>
            <h1 className="text-lg font-bold tracking-tight">CCWAP</h1>
            <p className="text-xs text-muted-foreground">Claude Code Analytics</p>
          </>
        )}
      </div>
      <SidebarContent collapsed={collapsed} />
      <div className="border-t border-border p-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggle}
          className={cn('w-full', collapsed ? 'justify-center' : 'justify-start')}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <PanelLeft className="h-4 w-4" />
          ) : (
            <>
              <PanelLeftClose className="h-4 w-4 mr-2" />
              <span className="text-xs">Collapse</span>
            </>
          )}
        </Button>
      </div>
    </aside>
  )
}
