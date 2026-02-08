import { useState, useCallback } from 'react'
import { RefreshCw, Save, Download, Plus, Trash2, Bell } from 'lucide-react'
import { PageLayout } from '@/components/PageLayout'
import { useSettings, useUpdatePricing, useRebuildDatabase } from '@/api/settings'
import type { PricingEntry } from '@/api/settings'
import { LoadingState } from '@/components/ui/LoadingState'
import { ErrorState } from '@/components/ui/ErrorState'
import { formatNumber } from '@/lib/utils'
import { useLocalStorage } from '@/hooks/useLocalStorage'

interface CustomPreset {
  label: string
  from: string
  to: string
}

function PricingEditor({ pricing }: { pricing: Record<string, PricingEntry> }) {
  const updatePricing = useUpdatePricing()
  const [editModel, setEditModel] = useState<string | null>(null)
  const [editValues, setEditValues] = useState<PricingEntry>({ input: 0, output: 0, cache_read: 0, cache_write: 0 })

  const startEdit = useCallback((model: string, entry: PricingEntry) => {
    setEditModel(model)
    setEditValues({ ...entry })
  }, [])

  const saveEdit = useCallback(() => {
    if (!editModel) return
    updatePricing.mutate({ model: editModel, pricing: editValues }, {
      onSuccess: () => setEditModel(null),
    })
  }, [editModel, editValues, updatePricing])

  const models = Object.entries(pricing).sort((a, b) => a[0].localeCompare(b[0]))

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/50 border-b border-border">
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Model</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Input $/M</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Output $/M</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Cache Read $/M</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Cache Write $/M</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Actions</th>
            </tr>
          </thead>
          <tbody>
            {models.map(([model, entry]) => (
              <tr key={model} className="border-b border-border hover:bg-accent/10">
                <td className="px-4 py-3 font-mono text-xs">{model}</td>
                {editModel === model ? (
                  <>
                    {(['input', 'output', 'cache_read', 'cache_write'] as const).map(field => (
                      <td key={field} className="px-4 py-2">
                        <input
                          type="number"
                          step="0.01"
                          value={editValues[field]}
                          onChange={e => setEditValues(prev => ({ ...prev, [field]: parseFloat(e.target.value) || 0 }))}
                          className="w-full px-2 py-1 text-sm text-right font-mono rounded border border-border bg-background focus:outline-none focus:ring-1 focus:ring-ring"
                        />
                      </td>
                    ))}
                    <td className="px-4 py-2 text-right">
                      <button onClick={saveEdit} disabled={updatePricing.isPending} className="p-1 rounded text-primary hover:bg-primary/10">
                        <Save className="h-4 w-4" />
                      </button>
                    </td>
                  </>
                ) : (
                  <>
                    <td className="px-4 py-3 font-mono text-right">${entry.input.toFixed(2)}</td>
                    <td className="px-4 py-3 font-mono text-right">${entry.output.toFixed(2)}</td>
                    <td className="px-4 py-3 font-mono text-right">${entry.cache_read.toFixed(2)}</td>
                    <td className="px-4 py-3 font-mono text-right">${entry.cache_write.toFixed(2)}</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => startEdit(model, entry)} className="text-xs text-primary hover:underline">Edit</button>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function DatabaseExport() {
  const handleExport = useCallback((format: 'csv' | 'json') => {
    window.open(`/api/settings/export?format=${format}`, '_blank')
  }, [])

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="text-sm font-medium text-muted-foreground mb-3">Full Database Export</h3>
      <p className="text-sm text-muted-foreground mb-4">
        Download a complete export of your database in CSV or JSON format.
      </p>
      <div className="flex gap-3">
        <button
          onClick={() => handleExport('csv')}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded-md border border-border hover:bg-accent"
        >
          <Download className="h-4 w-4" />
          Export CSV
        </button>
        <button
          onClick={() => handleExport('json')}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded-md border border-border hover:bg-accent"
        >
          <Download className="h-4 w-4" />
          Export JSON
        </button>
      </div>
    </div>
  )
}

function CustomPresetsEditor() {
  const [presets, setPresets] = useLocalStorage<CustomPreset[]>('ccwap:custom-presets', [])
  const [newLabel, setNewLabel] = useState('')
  const [newFrom, setNewFrom] = useState('')
  const [newTo, setNewTo] = useState('')

  const addPreset = useCallback(() => {
    if (!newLabel.trim() || !newFrom || !newTo) return
    setPresets(prev => [...prev, { label: newLabel.trim(), from: newFrom, to: newTo }])
    setNewLabel('')
    setNewFrom('')
    setNewTo('')
  }, [newLabel, newFrom, newTo, setPresets])

  const removePreset = useCallback((index: number) => {
    setPresets(prev => prev.filter((_, i) => i !== index))
  }, [setPresets])

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="text-sm font-medium text-muted-foreground mb-3">Custom Date Presets</h3>
      <p className="text-sm text-muted-foreground mb-4">
        Create custom date range presets for quick access in the date picker.
      </p>

      {/* Existing presets list */}
      {presets.length > 0 && (
        <div className="space-y-2 mb-4">
          {presets.map((preset, index) => (
            <div key={index} className="flex items-center justify-between px-3 py-2 rounded-md bg-muted/50 border border-border">
              <div className="text-sm">
                <span className="font-medium">{preset.label}</span>
                <span className="text-muted-foreground ml-2">
                  {preset.from} to {preset.to}
                </span>
              </div>
              <button
                onClick={() => removePreset(index)}
                className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {presets.length === 0 && (
        <p className="text-sm text-muted-foreground italic mb-4">No custom presets defined.</p>
      )}

      {/* Add new preset form */}
      <div className="flex flex-wrap gap-2 items-end">
        <div className="flex-1 min-w-[140px]">
          <label className="block text-xs text-muted-foreground mb-1">Label</label>
          <input
            type="text"
            value={newLabel}
            onChange={e => setNewLabel(e.target.value)}
            placeholder="e.g. Q1 2026"
            className="w-full px-2 py-1.5 text-sm rounded border border-border bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div className="min-w-[140px]">
          <label className="block text-xs text-muted-foreground mb-1">From</label>
          <input
            type="date"
            value={newFrom}
            onChange={e => setNewFrom(e.target.value)}
            className="w-full px-2 py-1.5 text-sm rounded border border-border bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div className="min-w-[140px]">
          <label className="block text-xs text-muted-foreground mb-1">To</label>
          <input
            type="date"
            value={newTo}
            onChange={e => setNewTo(e.target.value)}
            className="w-full px-2 py-1.5 text-sm rounded border border-border bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <button
          onClick={addPreset}
          disabled={!newLabel.trim() || !newFrom || !newTo}
          className="flex items-center gap-1 px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          Add
        </button>
      </div>
    </div>
  )
}

function NotificationThresholds() {
  const [dailyCost, setDailyCost] = useLocalStorage<number>('ccwap:alert-daily-cost', 0)
  const [weeklyCost, setWeeklyCost] = useLocalStorage<number>('ccwap:alert-weekly-cost', 0)
  const [errorRate, setErrorRate] = useLocalStorage<number>('ccwap:alert-error-rate', 0)

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Bell className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-medium text-muted-foreground">Notification Thresholds</h3>
      </div>
      <p className="text-sm text-muted-foreground mb-4">
        Set alert thresholds for cost and error monitoring. A value of 0 means no alert.
      </p>
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <label className="text-sm text-muted-foreground w-48">Daily Cost Alert ($)</label>
          <input
            type="number"
            min="0"
            step="0.01"
            value={dailyCost}
            onChange={e => setDailyCost(parseFloat(e.target.value) || 0)}
            className="w-32 px-2 py-1.5 text-sm font-mono text-right rounded border border-border bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div className="flex items-center gap-4">
          <label className="text-sm text-muted-foreground w-48">Weekly Cost Alert ($)</label>
          <input
            type="number"
            min="0"
            step="0.01"
            value={weeklyCost}
            onChange={e => setWeeklyCost(parseFloat(e.target.value) || 0)}
            className="w-32 px-2 py-1.5 text-sm font-mono text-right rounded border border-border bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div className="flex items-center gap-4">
          <label className="text-sm text-muted-foreground w-48">Error Rate Alert (%)</label>
          <input
            type="number"
            min="0"
            max="100"
            step="0.1"
            value={errorRate}
            onChange={e => setErrorRate(parseFloat(e.target.value) || 0)}
            className="w-32 px-2 py-1.5 text-sm font-mono text-right rounded border border-border bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const { data, isLoading, error } = useSettings()
  const rebuild = useRebuildDatabase()

  if (isLoading) return <LoadingState message="Loading settings..." />
  if (error) return <ErrorState message={error.message} />
  if (!data) return null

  const { pricing, etl_status, db_stats, version } = data

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1048576).toFixed(1)} MB`
  }

  return (
    <PageLayout title="Settings" subtitle="Pricing, display preferences, and data management">
      {/* Version */}
      {version && (
        <div className="mb-6 text-sm text-muted-foreground">CCWAP v{version}</div>
      )}

      {/* Pricing Table */}
      <div className="mb-6">
        <h3 className="text-sm font-medium mb-3">Model Pricing (per million tokens)</h3>
        <PricingEditor pricing={pricing} />
      </div>

      {/* Data Management */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* ETL Status */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-medium text-muted-foreground mb-3">ETL Status</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-muted-foreground">Files Processed</span><span className="font-mono">{etl_status.files_processed} / {etl_status.files_total}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Last Run</span><span className="font-mono">{etl_status.last_run || 'Never'}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Database Size</span><span className="font-mono">{formatBytes(etl_status.database_size_bytes)}</span></div>
          </div>
          <button
            onClick={() => rebuild.mutate()}
            disabled={rebuild.isPending}
            className="mt-4 flex items-center gap-2 px-3 py-2 text-sm rounded-md border border-border hover:bg-accent disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${rebuild.isPending ? 'animate-spin' : ''}`} />
            {rebuild.isPending ? 'Rebuilding...' : 'Rebuild Database'}
          </button>
          {rebuild.isSuccess && <p className="mt-2 text-xs text-green-500">Rebuild complete</p>}
          {rebuild.isError && <p className="mt-2 text-xs text-red-400">Rebuild failed</p>}
        </div>

        {/* Database Stats */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="text-sm font-medium text-muted-foreground mb-3">Database Statistics</h3>
          <div className="space-y-2 text-sm">
            {Object.entries(db_stats).map(([table, count]) => (
              <div key={table} className="flex justify-between">
                <span className="text-muted-foreground capitalize">{table.replace(/_/g, ' ')}</span>
                <span className="font-mono">{formatNumber(count)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Database Export */}
      <div className="mb-6">
        <DatabaseExport />
      </div>

      {/* Custom Date Presets */}
      <div className="mb-6">
        <CustomPresetsEditor />
      </div>

      {/* Notification Thresholds */}
      <div className="mb-6">
        <NotificationThresholds />
      </div>
    </PageLayout>
  )
}
