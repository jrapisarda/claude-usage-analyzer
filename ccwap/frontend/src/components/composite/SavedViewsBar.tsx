import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { toast } from '@/components/ui/toast'
import { useLocalStorage } from '@/hooks/useLocalStorage'
import {
  useAlertEvaluations,
  useCreateAlertRule,
  useCreateSavedView,
  useDeleteAlertRule,
  useDeleteSavedView,
  useSavedViews,
} from '@/api/savedViews'

interface SavedViewsBarProps {
  page: string
  currentFilters: Record<string, unknown>
  onApply: (filters: Record<string, unknown>) => void
  from: string | null
  to: string | null
  defaultMetricForAlert: string
}

export function SavedViewsBar({
  page,
  currentFilters,
  onApply,
  from,
  to,
  defaultMetricForAlert,
}: SavedViewsBarProps) {
  const [selectedView, setSelectedView] = useState<string>('')
  const [lastNotified, setLastNotified] = useLocalStorage<string[]>(`ccwap:alerts:notified:${page}`, [])

  const { data: viewsData } = useSavedViews(page)
  const { data: evalData } = useAlertEvaluations(page, from, to)

  const createView = useCreateSavedView(page)
  const deleteView = useDeleteSavedView(page)
  const createAlert = useCreateAlertRule(page)
  const deleteAlert = useDeleteAlertRule(page)

  const views = viewsData?.views ?? []
  const selected = useMemo(() => views.find(v => String(v.id) === selectedView), [views, selectedView])

  useEffect(() => {
    const triggered = (evalData?.evaluations ?? []).filter(e => e.triggered)
    if (triggered.length === 0) return
    const newIds = triggered
      .map(t => `${t.rule_id}:${from ?? ''}:${to ?? ''}`)
      .filter(id => !lastNotified.includes(id))
    if (newIds.length === 0) return
    const first = triggered[0]
    toast({
      title: `Alert Triggered (${page})`,
      description: `${first.name}: ${first.current_value.toFixed(4)} ${first.operator} ${first.threshold.toFixed(4)}`,
      variant: 'destructive',
    })
    setLastNotified(prev => [...prev, ...newIds].slice(-100))
  }, [evalData, from, lastNotified, page, setLastNotified, to])

  const handleSaveView = () => {
    const name = window.prompt(`Name this ${page} view:`)
    if (!name) return
    createView.mutate(
      { name: name.trim(), filters: currentFilters },
      {
        onSuccess: () => {
          toast({ title: 'Saved view created', description: name, variant: 'success' })
        },
        onError: (err: any) => {
          toast({ title: 'Failed to save view', description: err?.message ?? 'Unknown error', variant: 'destructive' })
        },
      }
    )
  }

  const handleDeleteView = () => {
    if (!selected) return
    if (!window.confirm(`Delete saved view "${selected.name}"?`)) return
    deleteView.mutate(selected.id, {
      onSuccess: () => {
        setSelectedView('')
        toast({ title: 'Saved view deleted', description: selected.name, variant: 'success' })
      },
      onError: (err: any) => {
        toast({ title: 'Failed to delete view', description: err?.message ?? 'Unknown error', variant: 'destructive' })
      },
    })
  }

  const handleCreateAlert = () => {
    const name = window.prompt(`Alert name for ${page}:`)
    if (!name) return
    const metric = window.prompt('Metric key:', defaultMetricForAlert) || defaultMetricForAlert
    const operator = window.prompt('Operator (> >= < <= == !=):', '>') || '>'
    const thresholdRaw = window.prompt('Threshold numeric value:', '0')
    if (!thresholdRaw) return
    const threshold = Number(thresholdRaw)
    if (Number.isNaN(threshold)) {
      toast({ title: 'Invalid threshold', description: thresholdRaw, variant: 'destructive' })
      return
    }

    createAlert.mutate(
      {
        name: name.trim(),
        metric: metric.trim(),
        operator: operator.trim(),
        threshold,
        filters: currentFilters,
      },
      {
        onSuccess: () => {
          toast({ title: 'Alert rule created', description: name, variant: 'success' })
        },
        onError: (err: any) => {
          toast({ title: 'Failed to create alert', description: err?.message ?? 'Unknown error', variant: 'destructive' })
        },
      }
    )
  }

  const handleClearAlerts = () => {
    const triggered = (evalData?.evaluations ?? []).filter(e => e.triggered)
    if (triggered.length === 0) return
    if (!window.confirm(`Delete ${triggered.length} triggered alert rule(s) for ${page}?`)) return
    for (const t of triggered) {
      deleteAlert.mutate(t.rule_id)
    }
  }

  return (
    <div className="rounded-md border border-border p-3 mb-4 flex flex-wrap items-center gap-2">
      <span className="text-xs text-muted-foreground">Saved Views</span>
      <Select value={selectedView} onValueChange={setSelectedView}>
        <SelectTrigger className="w-[220px] h-8">
          <SelectValue placeholder={`Choose ${page} view`} />
        </SelectTrigger>
        <SelectContent>
          {views.length === 0 ? (
            <SelectItem value="__none__" disabled>No saved views</SelectItem>
          ) : (
            views.map(v => <SelectItem key={v.id} value={String(v.id)}>{v.name}</SelectItem>)
          )}
        </SelectContent>
      </Select>

      <Button size="sm" variant="outline" onClick={() => selected && onApply(selected.filters)} disabled={!selected}>
        Apply
      </Button>
      <Button size="sm" variant="outline" onClick={handleSaveView}>
        Save Current
      </Button>
      <Button size="sm" variant="outline" onClick={handleDeleteView} disabled={!selected}>
        Delete View
      </Button>

      <span className="mx-2 h-5 w-px bg-border" />

      <Button size="sm" variant="outline" onClick={handleCreateAlert}>
        Add Alert
      </Button>
      <Button size="sm" variant="outline" onClick={handleClearAlerts}>
        Clear Triggered Alerts
      </Button>
      <span className="text-xs text-muted-foreground">
        Triggered: {(evalData?.evaluations ?? []).filter(e => e.triggered).length}
      </span>
    </div>
  )
}
