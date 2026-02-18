import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router'
import { useSearch } from '@/api/search'
import {
  LayoutDashboard, FolderKanban, List, DollarSign, Zap,
  BarChart3, FlaskConical, Radio, Settings, CalendarDays,
  Brain, GitBranch, Telescope, ChartScatter,
} from 'lucide-react'

import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandSeparator,
} from '@/components/ui/command'

const PAGES = [
  { label: 'Dashboard', path: '/', icon: LayoutDashboard, keywords: ['home', 'overview'] },
  { label: 'Projects', path: '/projects', icon: FolderKanban, keywords: ['repos'] },
  { label: 'Sessions', path: '/sessions', icon: List, keywords: ['history'] },
  { label: 'Cost Analysis', path: '/cost', icon: DollarSign, keywords: ['spending', 'money', 'budget'] },
  { label: 'Productivity', path: '/productivity', icon: Zap, keywords: ['loc', 'code'] },
  { label: 'Deep Analytics', path: '/analytics', icon: BarChart3, keywords: ['thinking', 'cache', 'branches'] },
  { label: 'Reliability', path: '/reliability', icon: BarChart3, keywords: ['errors', 'failures', 'tools'] },
  { label: 'Branch Health', path: '/branch-health', icon: GitBranch, keywords: ['merge', 'release', 'quality'] },
  { label: 'Prompt Efficiency', path: '/prompt-efficiency', icon: Brain, keywords: ['prompts', 'truncation', 'cost'] },
  { label: 'Workflow Bottlenecks', path: '/workflow-bottlenecks', icon: GitBranch, keywords: ['retries', 'handoff', 'stalls'] },
  { label: 'Activity Heatmap', path: '/heatmap', icon: CalendarDays, keywords: ['hourly', 'time'] },
  { label: 'Model Comparison', path: '/models', icon: Brain, keywords: ['claude', 'sonnet', 'opus'] },
  { label: 'Workflows', path: '/workflows', icon: GitBranch, keywords: ['agent', 'human', 'tools'] },
  { label: 'Explorer', path: '/explorer', icon: Telescope, keywords: ['browse', 'data'] },
  { label: 'Visualization Lab', path: '/visualizations', icon: ChartScatter, keywords: ['scatter', 'x axis', 'y axis', 'tableau'] },
  { label: 'Experiments', path: '/experiments', icon: FlaskConical, keywords: ['tags', 'compare'] },
  { label: 'Live Monitor', path: '/live', icon: Radio, keywords: ['realtime', 'websocket'] },
  { label: 'Settings', path: '/settings', icon: Settings, keywords: ['pricing', 'config'] },
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
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput
        value={search}
        onValueChange={setSearch}
        placeholder="Search pages, projects, sessions..."
      />
      <CommandList className="max-h-80">
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Pages">
          {PAGES.map(page => (
            <CommandItem
              key={page.path}
              value={`${page.label} ${page.keywords.join(' ')}`}
              onSelect={() => handleSelect(page.path)}
            >
              <page.icon className="mr-2 h-4 w-4 text-muted-foreground" />
              <span>{page.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        {searchResults?.results && searchResults.results.length > 0 && (
          <>
            <CommandSeparator />
            {['project', 'session', 'model', 'branch', 'tag'].map(category => {
              const items = searchResults.results.filter(r => r.category === category)
              if (items.length === 0) return null
              const heading = category.charAt(0).toUpperCase() + category.slice(1) + 's'
              return (
                <CommandGroup key={category} heading={heading}>
                  {items.map((item, i) => (
                    <CommandItem
                      key={`${category}-${i}`}
                      value={`${item.label} ${item.sublabel}`}
                      onSelect={() => handleSelect(item.url)}
                    >
                      <span>{item.label}</span>
                      <span className="ml-auto text-xs text-muted-foreground">
                        {item.sublabel}
                      </span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              )
            })}
          </>
        )}
      </CommandList>
      <div className="border-t border-border px-3 py-2 text-xs text-muted-foreground flex items-center justify-between">
        <span>Navigate with arrow keys</span>
        <span>
          <kbd className="px-1 py-0.5 text-[10px] bg-muted rounded">Esc</kbd> to close
        </span>
      </div>
    </CommandDialog>
  )
}
