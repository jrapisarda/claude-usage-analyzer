import { useState, useEffect, useCallback } from 'react'
import { Command } from 'cmdk'
import { useNavigate } from 'react-router'
import { useSearch } from '@/api/search'
import {
  LayoutDashboard, FolderKanban, List, DollarSign, Zap,
  BarChart3, FlaskConical, Radio, Settings, CalendarDays,
  Brain, GitBranch,
} from 'lucide-react'

const PAGES = [
  { label: 'Dashboard', path: '/', icon: LayoutDashboard, keywords: ['home', 'overview'] },
  { label: 'Projects', path: '/projects', icon: FolderKanban, keywords: ['repos'] },
  { label: 'Sessions', path: '/sessions', icon: List, keywords: ['history'] },
  { label: 'Cost Analysis', path: '/cost', icon: DollarSign, keywords: ['spending', 'money', 'budget'] },
  { label: 'Productivity', path: '/productivity', icon: Zap, keywords: ['loc', 'code'] },
  { label: 'Deep Analytics', path: '/analytics', icon: BarChart3, keywords: ['thinking', 'cache', 'branches'] },
  { label: 'Experiments', path: '/experiments', icon: FlaskConical, keywords: ['tags', 'compare'] },
  { label: 'Live Monitor', path: '/live', icon: Radio, keywords: ['realtime', 'websocket'] },
  { label: 'Settings', path: '/settings', icon: Settings, keywords: ['pricing', 'config'] },
  { label: 'Activity Heatmap', path: '/heatmap', icon: CalendarDays, keywords: ['hourly', 'time'] },
  { label: 'Model Comparison', path: '/models', icon: Brain, keywords: ['claude', 'sonnet', 'opus'] },
  { label: 'Workflows', path: '/workflows', icon: GitBranch, keywords: ['agent', 'human', 'tools'] },
]

interface CommandPaletteProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const [search, setSearch] = useState('')
  const navigate = useNavigate()
  const { data: searchResults } = useSearch(search)

  const handleSelect = useCallback((path: string) => {
    navigate(path)
    onOpenChange(false)
    setSearch('')
  }, [navigate, onOpenChange])

  useEffect(() => {
    if (!open) setSearch('')
  }, [open])

  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label="Global search"
      className="fixed inset-0 z-50"
    >
      <div className="fixed inset-0 bg-black/50" onClick={() => onOpenChange(false)} />
      <div className="fixed left-1/2 top-[20vh] -translate-x-1/2 w-full max-w-lg bg-card border border-border rounded-xl shadow-2xl overflow-hidden z-50">
        <Command.Input
          value={search}
          onValueChange={setSearch}
          placeholder="Search pages, projects, sessions..."
          className="w-full px-4 py-3 text-sm bg-transparent border-b border-border outline-none placeholder:text-muted-foreground"
        />
        <Command.List className="max-h-80 overflow-y-auto p-2">
          <Command.Empty className="px-4 py-6 text-sm text-center text-muted-foreground">
            No results found.
          </Command.Empty>

          <Command.Group heading="Pages" className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground">
            {PAGES.map(page => (
              <Command.Item
                key={page.path}
                value={`${page.label} ${page.keywords.join(' ')}`}
                onSelect={() => handleSelect(page.path)}
                className="flex items-center gap-2 px-3 py-2 text-sm rounded-md cursor-pointer data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground"
              >
                <page.icon className="h-4 w-4 text-muted-foreground" />
                {page.label}
              </Command.Item>
            ))}
          </Command.Group>

          {searchResults?.results && searchResults.results.length > 0 && (
            <>
              {['project', 'session', 'model', 'branch', 'tag'].map(category => {
                const items = searchResults.results.filter(r => r.category === category)
                if (items.length === 0) return null
                const heading = category.charAt(0).toUpperCase() + category.slice(1) + 's'
                return (
                  <Command.Group key={category} heading={heading} className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground">
                    {items.map((item, i) => (
                      <Command.Item
                        key={`${category}-${i}`}
                        value={`${item.label} ${item.sublabel}`}
                        onSelect={() => handleSelect(item.url)}
                        className="flex items-center justify-between px-3 py-2 text-sm rounded-md cursor-pointer data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground"
                      >
                        <span>{item.label}</span>
                        <span className="text-xs text-muted-foreground">{item.sublabel}</span>
                      </Command.Item>
                    ))}
                  </Command.Group>
                )
              })}
            </>
          )}
        </Command.List>
        <div className="border-t border-border px-3 py-2 text-xs text-muted-foreground flex items-center justify-between">
          <span>Navigate with arrow keys</span>
          <span>
            <kbd className="px-1 py-0.5 text-[10px] bg-muted rounded">Esc</kbd> to close
          </span>
        </div>
      </div>
    </Command.Dialog>
  )
}
