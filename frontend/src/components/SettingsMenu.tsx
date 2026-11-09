import { Monitor, Moon, Sun } from 'lucide-react'

import { setLang, t, useLang, type Lang } from '@/i18n'
import { setTheme, useTheme, type Theme } from '@/lib/theme'
import { cn } from '@/lib/utils'

const languages: { value: Lang; label: string }[] = [
  { value: 'ru', label: 'RU' },
  { value: 'en', label: 'EN' },
]

const themes = [
  { value: 'light', icon: Sun, label: 'theme.light' },
  { value: 'dark', icon: Moon, label: 'theme.dark' },
  { value: 'system', icon: Monitor, label: 'theme.system' },
] as const

function Segment({ active, className, ...props }: React.ComponentProps<'button'> & { active: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cn(
        'inline-flex h-7 min-w-7 items-center justify-center rounded px-2 text-xs font-medium transition-colors',
        active ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
        className,
      )}
      {...props}
    />
  )
}

// The settings of the interface, always at the right of the header: the language and the theme.
export function SettingsMenu() {
  const lang = useLang()
  const theme: Theme = useTheme()

  return (
    <div className="ml-auto flex items-center gap-2">
      <div className="flex rounded-md bg-muted p-0.5" role="group" aria-label={t('settings.language')}>
        {languages.map((item) => (
          <Segment key={item.value} active={lang === item.value} onClick={() => setLang(item.value)}>
            {item.label}
          </Segment>
        ))}
      </div>
      <div className="flex rounded-md bg-muted p-0.5" role="group" aria-label={t('settings.theme')}>
        {themes.map(({ value, icon: Icon, label }) => (
          <Segment
            key={value}
            active={theme === value}
            onClick={() => setTheme(value)}
            title={t(label)}
            aria-label={t(label)}
            className="px-1.5"
          >
            <Icon className="size-4" />
          </Segment>
        ))}
      </div>
    </div>
  )
}
