import { cn } from '@/lib/utils'

interface ActiveSessionBadgeProps {
  projectDisplay: string
  gitBranch?: string
  className?: string
}

export function ActiveSessionBadge({ projectDisplay, gitBranch, className }: ActiveSessionBadgeProps) {
  return (
    <div className={cn(
      "flex items-center gap-2 px-3 py-1.5 rounded-md bg-green-500/10 border border-green-500/30",
      className,
    )}>
      <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
      <span className="text-xs font-medium">{projectDisplay}</span>
      {gitBranch && (
        <span className="text-xs text-muted-foreground font-mono">{gitBranch}</span>
      )}
    </div>
  )
}
