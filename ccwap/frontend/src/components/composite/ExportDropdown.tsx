import { Download, FileSpreadsheet, FileJson } from 'lucide-react'
import { useExport } from '@/hooks/useExport'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

interface ExportDropdownProps {
  page: string
  getData: () => Record<string, unknown>[]
  columns?: string[]
  metadata?: Record<string, unknown>
}

export function ExportDropdown({ page, getData, columns, metadata }: ExportDropdownProps) {
  const { exportData } = useExport()

  function handleExport(format: 'csv' | 'json') {
    const data = getData()
    if (data.length === 0) return
    exportData(format, { page, data, columns, metadata })
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          <Download className="mr-1.5 h-3.5 w-3.5" />
          Export
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => handleExport('csv')}>
          <FileSpreadsheet className="mr-2 h-4 w-4" />
          Export CSV
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => handleExport('json')}>
          <FileJson className="mr-2 h-4 w-4" />
          Export JSON
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
