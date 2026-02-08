import { NavLink } from 'react-router'
import {
  LayoutDashboard, FolderKanban, List, DollarSign, Zap,
  BarChart3, FlaskConical, Radio, Settings, CalendarDays,
  Brain, GitBranch, Telescope,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/projects', icon: FolderKanban, label: 'Projects' },
  { to: '/sessions', icon: List, label: 'Sessions' },
  { to: '/cost', icon: DollarSign, label: 'Cost Analysis' },
  { to: '/productivity', icon: Zap, label: 'Productivity' },
  { to: '/analytics', icon: BarChart3, label: 'Deep Analytics' },
  { to: '/heatmap', icon: CalendarDays, label: 'Activity Heatmap' },
  { to: '/models', icon: Brain, label: 'Model Comparison' },
  { to: '/workflows', icon: GitBranch, label: 'Workflows' },
  { to: '/explorer', icon: Telescope, label: 'Explorer' },
  { to: '/experiments', icon: FlaskConical, label: 'Experiments' },
  { to: '/live', icon: Radio, label: 'Live Monitor' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export function Sidebar() {
  return (
    <aside className="w-56 shrink-0 border-r border-border bg-card h-screen sticky top-0 flex flex-col">
      <div className="p-4 border-b border-border">
        <h1 className="text-lg font-bold tracking-tight">CCWAP</h1>
        <p className="text-xs text-muted-foreground">Claude Code Analytics</p>
      </div>
      <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) => cn(
              "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
              isActive
                ? "bg-accent text-accent-foreground font-medium"
                : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
            )}
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
