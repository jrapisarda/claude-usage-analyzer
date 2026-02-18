import { useState, useCallback } from 'react'
import { RefreshCw, Save, Download, Plus, Trash2, Bell } from 'lucide-react'
import { PageLayout } from '@/components/layout/PageLayout'
import { useSettings, useUpdatePricing, useRebuildDatabase } from '@/api/settings'
import type { PricingEntry } from '@/api/settings'
import { ErrorState } from '@/components/composite/ErrorState'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table, TableHeader, TableBody, TableHead, TableRow, TableCell,
} from '@/components/ui/table'
import { formatNumber } from '@/lib/utils'
import { useLocalStorage } from '@/hooks/useLocalStorage'

interface CustomPreset {
  label: string
  from: string
  to: string
}

const EMPTY_PRICING_ENTRY: PricingEntry = {
  input: 0,
  output: 0,
  cache_read: 0,
  cache_write_5m: 0,
  cache_write_1h: 0,
}

function PricingEditor({ pricing }: { pricing: Record<string, PricingEntry> }) {
  const updatePricing = useUpdatePricing()
  const [editModel, setEditModel] = useState<string | null>(null)
  const [editValues, setEditValues] = useState<PricingEntry>({ ...EMPTY_PRICING_ENTRY })
  const [isAddingModel, setIsAddingModel] = useState(false)
  const [newModel, setNewModel] = useState('')
  const [newValues, setNewValues] = useState<PricingEntry>({ ...EMPTY_PRICING_ENTRY })
  const [addError, setAddError] = useState<string | null>(null)

  const startEdit = useCallback((model: string, entry: PricingEntry) => {
    setIsAddingModel(false)
    setAddError(null)
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

  const startAddModel = useCallback(() => {
    setEditModel(null)
    setAddError(null)
    setNewModel('')
    setNewValues({ ...EMPTY_PRICING_ENTRY })
    setIsAddingModel(true)
  }, [])

  const cancelAddModel = useCallback(() => {
    setAddError(null)
    setNewModel('')
    setNewValues({ ...EMPTY_PRICING_ENTRY })
    setIsAddingModel(false)
  }, [])

  const saveNewModel = useCallback(() => {
    const model = newModel.trim()
    if (!model) {
      setAddError('Model name is required.')
      return
    }

    const hasDuplicate = models.some(([existingModel]) => existingModel.toLowerCase() === model.toLowerCase())
    if (hasDuplicate) {
      setAddError('Model already exists. Use Edit.')
      return
    }

    setAddError(null)
    updatePricing.mutate({ model, pricing: newValues }, {
      onSuccess: () => cancelAddModel(),
    })
  }, [cancelAddModel, models, newModel, newValues, updatePricing])

  return (
    <div className="rounded-md border border-border overflow-hidden">
      <div className="flex justify-end gap-2 border-b border-border p-3">
        {isAddingModel ? (
          <>
            <Button variant="ghost" size="sm" onClick={cancelAddModel} disabled={updatePricing.isPending}>
              Cancel
            </Button>
            <Button size="sm" onClick={saveNewModel} disabled={updatePricing.isPending || !newModel.trim()}>
              <Save className="mr-1.5 h-4 w-4" />
              Save Model
            </Button>
          </>
        ) : (
          <Button variant="outline" size="sm" onClick={startAddModel} disabled={updatePricing.isPending}>
            <Plus className="mr-1.5 h-4 w-4" />
            Add Model
          </Button>
        )}
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Model</TableHead>
            <TableHead className="text-right">Input $/M</TableHead>
            <TableHead className="text-right">5m Write $/M</TableHead>
            <TableHead className="text-right">1h Write $/M</TableHead>
            <TableHead className="text-right">Hits/Refresh $/M</TableHead>
            <TableHead className="text-right">Output $/M</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isAddingModel && (
            <TableRow>
              <TableCell>
                <Input
                  type="text"
                  value={newModel}
                  onChange={e => setNewModel(e.target.value)}
                  placeholder="claude-model-name"
                  className="font-mono text-xs"
                />
              </TableCell>
              {(['input', 'cache_write_5m', 'cache_write_1h', 'cache_read', 'output'] as const).map(field => (
                <TableCell key={`new-${field}`}>
                  <Input
                    type="number"
                    step="0.01"
                    value={newValues[field]}
                    onChange={e => setNewValues(prev => ({ ...prev, [field]: parseFloat(e.target.value) || 0 }))}
                    className="w-full text-right font-mono text-sm"
                  />
                </TableCell>
              ))}
              <TableCell className="text-right">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={saveNewModel}
                  disabled={updatePricing.isPending || !newModel.trim()}
                >
                  <Save className="h-4 w-4" />
                </Button>
              </TableCell>
            </TableRow>
          )}
          {isAddingModel && addError && (
            <TableRow>
              <TableCell colSpan={7} className="text-xs text-destructive">
                {addError}
              </TableCell>
            </TableRow>
          )}
          {models.map(([model, entry]) => (
            <TableRow key={model}>
              <TableCell className="font-mono text-xs">{model}</TableCell>
              {editModel === model ? (
                <>
                  {(['input', 'cache_write_5m', 'cache_write_1h', 'cache_read', 'output'] as const).map(field => (
                    <TableCell key={field}>
                      <Input
                        type="number"
                        step="0.01"
                        value={editValues[field]}
                        onChange={e => setEditValues(prev => ({ ...prev, [field]: parseFloat(e.target.value) || 0 }))}
                        className="w-full text-right font-mono text-sm"
                      />
                    </TableCell>
                  ))}
                  <TableCell className="text-right">
                    <Button variant="ghost" size="icon" onClick={saveEdit} disabled={updatePricing.isPending}>
                      <Save className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </>
              ) : (
                <>
                  <TableCell className="font-mono text-right">${entry.input.toFixed(2)}</TableCell>
                  <TableCell className="font-mono text-right">${entry.cache_write_5m.toFixed(2)}</TableCell>
                  <TableCell className="font-mono text-right">${entry.cache_write_1h.toFixed(2)}</TableCell>
                  <TableCell className="font-mono text-right">${entry.cache_read.toFixed(2)}</TableCell>
                  <TableCell className="font-mono text-right">${entry.output.toFixed(2)}</TableCell>
                  <TableCell className="text-right">
                    <Button variant="link" size="sm" onClick={() => startEdit(model, entry)}>
                      Edit
                    </Button>
                  </TableCell>
                </>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function DatabaseExport() {
  const handleExport = useCallback((format: 'csv' | 'json') => {
    window.open(`/api/settings/export?format=${format}`, '_blank')
  }, [])

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Full Database Export</CardTitle>
        <CardDescription>
          Download a complete export of your database in CSV or JSON format.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex gap-3">
          <Button variant="outline" size="sm" onClick={() => handleExport('csv')}>
            <Download className="mr-1.5 h-4 w-4" />
            Export CSV
          </Button>
          <Button variant="outline" size="sm" onClick={() => handleExport('json')}>
            <Download className="mr-1.5 h-4 w-4" />
            Export JSON
          </Button>
        </div>
      </CardContent>
    </Card>
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
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Custom Date Presets</CardTitle>
        <CardDescription>
          Create custom date range presets for quick access in the date picker.
        </CardDescription>
      </CardHeader>
      <CardContent>
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
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => removePreset(index)}
                  className="text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
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
            <Input
              type="text"
              value={newLabel}
              onChange={e => setNewLabel(e.target.value)}
              placeholder="e.g. Q1 2026"
            />
          </div>
          <div className="min-w-[140px]">
            <label className="block text-xs text-muted-foreground mb-1">From</label>
            <Input
              type="date"
              value={newFrom}
              onChange={e => setNewFrom(e.target.value)}
            />
          </div>
          <div className="min-w-[140px]">
            <label className="block text-xs text-muted-foreground mb-1">To</label>
            <Input
              type="date"
              value={newTo}
              onChange={e => setNewTo(e.target.value)}
            />
          </div>
          <Button
            onClick={addPreset}
            disabled={!newLabel.trim() || !newFrom || !newTo}
            size="sm"
          >
            <Plus className="mr-1 h-4 w-4" />
            Add
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function NotificationThresholds() {
  const [dailyCost, setDailyCost] = useLocalStorage<number>('ccwap:alert-daily-cost', 0)
  const [weeklyCost, setWeeklyCost] = useLocalStorage<number>('ccwap:alert-weekly-cost', 0)
  const [errorRate, setErrorRate] = useLocalStorage<number>('ccwap:alert-error-rate', 0)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Bell className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-sm">Notification Thresholds</CardTitle>
        </div>
        <CardDescription>
          Set alert thresholds for cost and error monitoring. A value of 0 means no alert.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <label className="text-sm text-muted-foreground w-48">Daily Cost Alert ($)</label>
            <Input
              type="number"
              min="0"
              step="0.01"
              value={dailyCost}
              onChange={e => setDailyCost(parseFloat(e.target.value) || 0)}
              className="w-32 text-right font-mono"
            />
          </div>
          <div className="flex items-center gap-4">
            <label className="text-sm text-muted-foreground w-48">Weekly Cost Alert ($)</label>
            <Input
              type="number"
              min="0"
              step="0.01"
              value={weeklyCost}
              onChange={e => setWeeklyCost(parseFloat(e.target.value) || 0)}
              className="w-32 text-right font-mono"
            />
          </div>
          <div className="flex items-center gap-4">
            <label className="text-sm text-muted-foreground w-48">Error Rate Alert (%)</label>
            <Input
              type="number"
              min="0"
              max="100"
              step="0.1"
              value={errorRate}
              onChange={e => setErrorRate(parseFloat(e.target.value) || 0)}
              className="w-32 text-right font-mono"
            />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function SettingsPage() {
  const { data, isLoading, error, refetch } = useSettings()
  const rebuild = useRebuildDatabase()

  if (isLoading) {
    return (
      <PageLayout title="Settings" subtitle="Pricing, display preferences, and data management">
        <Skeleton className="h-4 w-32 mb-6" />
        <Skeleton className="h-64 w-full mb-6" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      </PageLayout>
    )
  }

  if (error) return <ErrorState message={error.message} onRetry={() => refetch()} />
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
        <Badge variant="secondary" className="mb-6">CCWAP v{version}</Badge>
      )}

      {/* Pricing Table */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-sm">Model Pricing (per million tokens)</CardTitle>
        </CardHeader>
        <CardContent>
          <PricingEditor pricing={pricing} />
        </CardContent>
      </Card>

      <Separator className="my-6" />

      {/* Data Management */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* ETL Status */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">ETL Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Files Processed</span>
                <span className="font-mono">{etl_status.files_processed} / {etl_status.files_total}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Last Run</span>
                <span className="font-mono">{etl_status.last_run || 'Never'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Database Size</span>
                <span className="font-mono">{formatBytes(etl_status.database_size_bytes)}</span>
              </div>
            </div>
          </CardContent>
          <CardFooter className="flex-col items-start gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => rebuild.mutate()}
              disabled={rebuild.isPending}
            >
              <RefreshCw className={`mr-1.5 h-4 w-4 ${rebuild.isPending ? 'animate-spin' : ''}`} />
              {rebuild.isPending ? 'Rebuilding...' : 'Rebuild Database'}
            </Button>
            {rebuild.isSuccess && <Badge variant="secondary" className="text-green-500">Rebuild complete</Badge>}
            {rebuild.isError && <Badge variant="destructive">Rebuild failed</Badge>}
          </CardFooter>
        </Card>

        {/* Database Stats */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Database Statistics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              {Object.entries(db_stats).map(([table, count]) => (
                <div key={table} className="flex justify-between">
                  <span className="text-muted-foreground capitalize">{table.replace(/_/g, ' ')}</span>
                  <span className="font-mono">{formatNumber(count)}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Separator className="my-6" />

      {/* Database Export */}
      <div className="mb-6">
        <DatabaseExport />
      </div>

      <Separator className="my-6" />

      {/* Custom Date Presets */}
      <div className="mb-6">
        <CustomPresetsEditor />
      </div>

      <Separator className="my-6" />

      {/* Notification Thresholds */}
      <div className="mb-6">
        <NotificationThresholds />
      </div>
    </PageLayout>
  )
}
