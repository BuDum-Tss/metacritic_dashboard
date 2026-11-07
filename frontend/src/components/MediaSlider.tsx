import { Play } from 'lucide-react'

import { ArrowButton, hideScrollbar } from '@/components/Carousel'
import { useScroller } from '@/lib/useScroller'
import { cn } from '@/lib/utils'

function Cover({ url, title }: { url: string | null; title: string }) {
  return url ? (
    <img src={url} alt={title} className="h-full w-full object-cover" />
  ) : (
    <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Нет обложки</div>
  )
}

function Trailer({ url, cover, title, active }: { url: string; cover: string | null; title: string; active: boolean }) {
  // jwplayer embed pages can be shown in a frame, other links are opened separately
  const embeddable = url.includes('/players/')

  if (embeddable && active) {
    // the player only exists while its slide is shown, so it stops when the slide is left
    return <iframe src={url} title={`Трейлер: ${title}`} allowFullScreen className="h-full w-full" />
  }
  return (
    <div className="relative h-full w-full bg-black">
      {cover && <img src={cover} alt="" className="h-full w-full object-cover opacity-40" />}
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-white">
        <Play className="size-12" />
        {embeddable ? (
          <span className="text-sm">Трейлер</span>
        ) : (
          <a href={url} target="_blank" rel="noreferrer" className="text-sm underline">
            Смотреть видео
          </a>
        )}
      </div>
    </div>
  )
}

// The cover and the trailer of a game as slides: the trailer is reached by swiping the picture.
export function MediaSlider({
  title,
  coverUrl,
  videoUrl,
}: {
  title: string
  coverUrl: string | null
  videoUrl: string | null
}) {
  const { ref, index, canPrev, canNext, scrollPage, scrollToIndex } = useScroller()
  const count = videoUrl ? 2 : 1

  return (
    <div className="relative h-full w-full">
      <div ref={ref} className={cn('flex h-full snap-x snap-mandatory overflow-x-auto scroll-smooth', hideScrollbar)}>
        <div className="h-full w-full shrink-0 snap-center">
          <Cover url={coverUrl} title={title} />
        </div>
        {videoUrl && (
          <div className="h-full w-full shrink-0 snap-center">
            <Trailer url={videoUrl} cover={coverUrl} title={title} active={index === 1} />
          </div>
        )}
      </div>

      {count > 1 && (
        <>
          {canPrev && <ArrowButton direction="prev" onClick={() => scrollPage(-1)} />}
          {canNext && <ArrowButton direction="next" onClick={() => scrollPage(1)} />}
          <div className="absolute inset-x-0 bottom-2 z-10 flex justify-center gap-2">
            {Array.from({ length: count }, (_, i) => (
              <button
                key={i}
                type="button"
                aria-label={i === 0 ? 'Обложка' : 'Трейлер'}
                aria-current={i === index}
                onClick={() => scrollToIndex(i)}
                className={cn('size-2 rounded-full bg-white/60 ring-1 ring-black/30', i === index && 'bg-white')}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
