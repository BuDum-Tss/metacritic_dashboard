import { t } from '@/i18n'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { Layout } from '@/components/Layout'
import { GamePage } from '@/pages/GamePage'
import { GamesPage } from '@/pages/GamesPage'
import { MonitoringPage } from '@/pages/MonitoringPage'

// the charts library is heavy: it loads only with the dashboard
const DashboardPage = lazy(() => import('@/pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, staleTime: 15_000 } },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route
              index
              element={
                <Suspense fallback={<p className="text-muted-foreground">{t('app.loading')}</p>}>
                  <DashboardPage />
                </Suspense>
              }
            />
            <Route path="games" element={<GamesPage />} />
            <Route path="games/:id" element={<GamePage />} />
            <Route path="monitoring" element={<MonitoringPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
