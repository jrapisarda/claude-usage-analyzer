import { lazy, Suspense, useState, useCallback } from 'react'
import { Routes, Route } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Sidebar } from '@/components/Sidebar'
import { TopBar } from '@/components/TopBar'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { LoadingState } from '@/components/ui/LoadingState'
import { CommandPalette } from '@/components/CommandPalette'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'

const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const ProjectsPage = lazy(() => import('@/pages/ProjectsPage'))
const SessionsPage = lazy(() => import('@/pages/SessionsPage'))
const SessionDetailPage = lazy(() => import('@/pages/SessionDetailPage'))
const CostPage = lazy(() => import('@/pages/CostPage'))
const ProductivityPage = lazy(() => import('@/pages/ProductivityPage'))
const AnalyticsPage = lazy(() => import('@/pages/AnalyticsPage'))
const ExperimentsPage = lazy(() => import('@/pages/ExperimentsPage'))
const LiveMonitorPage = lazy(() => import('@/pages/LiveMonitorPage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const HeatmapPage = lazy(() => import('@/pages/HeatmapPage'))
const ModelComparisonPage = lazy(() => import('@/pages/ModelComparisonPage'))
const WorkflowPage = lazy(() => import('@/pages/WorkflowPage'))
const ProjectDetailPage = lazy(() => import('@/pages/ProjectDetailPage'))
const ExplorerPage = lazy(() => import('@/pages/ExplorerPage'))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 300_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function AppContent() {
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false)
  const toggleCommandPalette = useCallback(() => setCommandPaletteOpen(prev => !prev), [])
  useKeyboardShortcuts(toggleCommandPalette)

  return (
    <>
      <CommandPalette open={commandPaletteOpen} onOpenChange={setCommandPaletteOpen} />
      <div className="flex min-h-screen bg-background text-foreground">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <TopBar onCommandK={toggleCommandPalette} />
          <main className="flex-1 p-6">
            <ErrorBoundary>
            <Suspense fallback={<LoadingState message="Loading page..." />}>
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/projects" element={<ProjectsPage />} />
                <Route path="/projects/:path" element={<ProjectDetailPage />} />
                <Route path="/sessions" element={<SessionsPage />} />
                <Route path="/sessions/:id" element={<SessionDetailPage />} />
                <Route path="/cost" element={<CostPage />} />
                <Route path="/productivity" element={<ProductivityPage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/heatmap" element={<HeatmapPage />} />
                <Route path="/models" element={<ModelComparisonPage />} />
                <Route path="/workflows" element={<WorkflowPage />} />
                <Route path="/explorer" element={<ExplorerPage />} />
                <Route path="/experiments" element={<ExperimentsPage />} />
                <Route path="/live" element={<LiveMonitorPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </Suspense>
            </ErrorBoundary>
          </main>
        </div>
      </div>
    </>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  )
}
