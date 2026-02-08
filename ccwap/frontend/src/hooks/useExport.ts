import { useCallback } from 'react'

type ExportFormat = 'csv' | 'json'

interface ExportOptions {
  /** Page identifier for filename */
  page: string
  /** Column headers for CSV */
  columns?: string[]
  /** Data rows (array of objects) */
  data: Record<string, unknown>[]
  /** Additional metadata for JSON export */
  metadata?: Record<string, unknown>
}

function formatDate(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function escapeCSV(value: unknown): string {
  if (value == null) return ''
  let str = String(value)
  // Prevent formula injection in spreadsheet applications
  if (/^[=+\-@\t\r]/.test(str)) {
    str = '\t' + str
  }
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\t')) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

function exportCSV(options: ExportOptions) {
  const { page, columns, data } = options
  if (data.length === 0) return

  const headers = columns || Object.keys(data[0])
  const rows = data.map(row => headers.map(h => escapeCSV(row[h])).join(','))
  // BOM for Windows Excel UTF-8 support
  const csv = '\uFEFF' + [headers.join(','), ...rows].join('\r\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  downloadBlob(blob, `ccwap-${page}-${formatDate()}.csv`)
}

function exportJSON(options: ExportOptions) {
  const { page, data, metadata } = options
  const wrapper = {
    exported_at: new Date().toISOString(),
    source: 'CCWAP Dashboard',
    page,
    record_count: data.length,
    ...metadata,
    data,
  }
  const json = JSON.stringify(wrapper, null, 2)
  const blob = new Blob([json], { type: 'application/json' })
  downloadBlob(blob, `ccwap-${page}-${formatDate()}.json`)
}

export function useExport() {
  const exportData = useCallback((format: ExportFormat, options: ExportOptions) => {
    if (format === 'csv') {
      exportCSV(options)
    } else {
      exportJSON(options)
    }
  }, [])

  return { exportData }
}
