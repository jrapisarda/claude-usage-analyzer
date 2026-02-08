import type { ReactNode } from 'react'
import { Breadcrumbs, type BreadcrumbItem } from '@/components/layout/Breadcrumbs'

interface PageLayoutProps {
  title: string
  subtitle?: string
  actions?: ReactNode
  breadcrumbs?: BreadcrumbItem[]
  children: ReactNode
}

export function PageLayout({ title, subtitle, actions, breadcrumbs, children }: PageLayoutProps) {
  return (
    <div>
      {breadcrumbs && breadcrumbs.length > 0 && (
        <Breadcrumbs items={breadcrumbs} className="mb-4" />
      )}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">{title}</h2>
          {subtitle && <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>}
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
      {children}
    </div>
  )
}
