import { NavLink, Outlet } from 'react-router-dom'

import { SettingsMenu } from '@/components/SettingsMenu'
import { t, useLang, type Key } from '@/i18n'
import { cn } from '@/lib/utils'

const links: { to: string; label: Key; end: boolean }[] = [
  { to: '/', label: 'nav.dashboard', end: true },
  { to: '/games', label: 'nav.games', end: false },
  { to: '/monitoring', label: 'nav.monitoring', end: false },
]

export function Layout() {
  const lang = useLang()
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
          <span className="font-bold">Metacritic Dashboard</span>
          <nav className="flex gap-1">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-3 py-1.5 text-sm font-medium transition-colors hover:bg-muted',
                    isActive ? 'bg-muted text-foreground' : 'text-muted-foreground',
                  )
                }
              >
                {t(link.label)}
              </NavLink>
            ))}
          </nav>
          <SettingsMenu />
        </div>
      </header>
      {/* the key rebuilds the page when the language changes */}
      <main key={lang} className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
