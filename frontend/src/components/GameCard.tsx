import { Link } from 'react-router-dom'

import { ScoreBadge } from '@/components/ScoreBadge'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import type { GameShort } from '@/api/types'

export function GameCard({ game }: { game: GameShort }) {
  return (
    <Link to={`/games/${game.id}`} className="group block h-full">
      <Card className="h-full gap-0 overflow-hidden py-0 transition-shadow group-hover:shadow-lg">
        <div className="aspect-video w-full bg-muted">
          {game.cover_url ? (
            <img
              src={game.cover_url}
              alt={game.title}
              loading="lazy"
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              Нет обложки
            </div>
          )}
        </div>
        <div className="flex flex-1 flex-col gap-2 p-3">
          <div>
            <h3 className="line-clamp-2 font-semibold leading-tight">{game.title}</h3>
            {game.developer && (
              <p className="line-clamp-1 text-xs text-muted-foreground">{game.developer}</p>
            )}
          </div>
          {game.genres.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {game.genres.slice(0, 2).map((genre) => (
                <Badge key={genre} variant="secondary">
                  {genre}
                </Badge>
              ))}
            </div>
          )}
          <ul className="mt-auto space-y-1 pt-1">
            {game.platforms.map((p) => (
              <li key={p.platform} className="flex items-center justify-between gap-2 text-xs">
                <span className="truncate text-muted-foreground">{p.name}</span>
                <span className="flex shrink-0 gap-1">
                  <ScoreBadge kind="critic" value={p.metascore} />
                  <ScoreBadge kind="user" value={p.userscore} />
                </span>
              </li>
            ))}
          </ul>
        </div>
      </Card>
    </Link>
  )
}
