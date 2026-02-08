import { useState, useRef, useEffect } from 'react'
import { Download } from 'lucide-react'
import { useExport } from '@/hooks/useExport'

interface ExportDropdownProps {
  page: string
  getData: () => Record<string, unknown>[]
  columns?: string[]
  metadata?: Record<string, unknown>
}

export function ExportDropdown({ page, getData, columns, metadata }: ExportDropdownProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const { exportData } = useExport()

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClick)
      return () => document.removeEventListener('mousedown', handleClick)
    }
  }, [open])

  function handleExport(format: 'csv' | 'json') {
    const data = getData()
    if (data.length === 0) return
    exportData(format, { page, data, columns, metadata })
    setOpen(false)
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border border-border hover:bg-accent/50 transition-colors text-muted-foreground hover:text-foreground"
        title="Export data"
      >
        <Download className="h-3.5 w-3.5" />
        <span>Export</span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 bg-card border border-border rounded-md shadow-lg z-50 min-w-[140px]">
          <button
            onClick={() => handleExport('csv')}
            className="w-full text-left px-3 py-2 text-sm hover:bg-accent/50 transition-colors rounded-t-md"
          >
            Export CSV
          </button>
          <button
            onClick={() => handleExport('json')}
            className="w-full text-left px-3 py-2 text-sm hover:bg-accent/50 transition-colors rounded-b-md"
          >
            Export JSON
          </button>
        </div>
      )}
    </div>
  )
}
