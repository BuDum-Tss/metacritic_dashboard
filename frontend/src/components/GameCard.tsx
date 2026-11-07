import { Link } from 'react-router-dom'

import { GameScore } from '@/components/GameScore'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import type { GameShort } from '@/api/types'

export function GameCard({ game }: { game: GameShort }) {
  return (
    <Link to={`/games/${game.id}`} className="group block h-full">
      <Card className="h-full gap-0 overflow-hidden py-0 transition-shadow group-hover:shadow-lg">
        {/* a fixed 16:9 frame: overflow-hidden keeps a tall picture from stretching it */}
        <div className="relative aspect-video w-full overflow-hidden bg-muted">
          {game.cover_url ? (
            <img
              src={game.cover_url}
              alt={game.title}
              loading="lazy"
              className="absolute inset-0 h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              Нет обложки
            </div>
          )}
        </div>
        <div className="flex flex-1 flex-col gap-2 p-3">
          <h3 className="line-clamp-2 font-semibold leading-tight">{game.title}</h3>
          {/* the developer, the genre and the score share one row */}
          <div className="mt-auto flex items-center justify-between gap-3">
            <div className="min-w-0 space-y-1">
              {game.developer && <p className="truncate text-xs text-muted-foreground">{game.developer}</p>}
              {game.genres.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {game.genres.slice(0, 2).map((genre) => (
                    <Badge key={genre} variant="secondary">
                      {genre}
                    </Badge>
                  ))}
                </div>
              )}
              {game.platforms.length > 0 && (
                <p className="truncate text-xs text-muted-foreground">
                  {game.platforms.map((p) => p.name).join(' · ')}
                </p>
              )}
            </div>
            <GameScore score={game.score} size="sm" />
          </div>
        </div>
      </Card>
    </Link>
  )
}
