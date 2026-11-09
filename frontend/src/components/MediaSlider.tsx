import { t } from '@/i18n'
import { Play } from 'lucide-react'

import type { Video } from '@/api/types'
import { ArrowButton, hideScrollbar } from '@/components/Carousel'
import { videoKindLabels } from '@/lib/format'
import { useScroller } from '@/lib/useScroller'
import { cn } from '@/lib/utils'

function Cover({ url, title }: { url: string | null; title: string }) {
  return url ? (
    <img src={url} alt={title} className="h-full w-full object-cover" />
  ) : (
    <div className="flex h-full items-center justify-center text-sm text-muted-foreground">{t('common.noCover')}</div>
  )
}

function Trailer({ url, cover, title, active }: { url: string; cover: string | null; title: string; active: boolean }) {
  // jwplayer embed pages can be shown in a frame, other links are opened separately
  const embeddable = url.includes('/players/')

  if (embeddable && active) {
    // the player only exists while its slide is shown, so it stops when the slide is left
    return <iframe src={url} title={t('media.trailerOf', { title })} allowFullScreen className="h-full w-full" />
  }
  return (
    <div className="relative h-full w-full bg-black">
      {cover && <img src={cover} alt="" className="h-full w-full object-cover opacity-40" />}
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-white">
        <Play className="size-12" />
        {embeddable ? (
          <span className="text-sm">{t('media.trailer')}</span>
        ) : (
          <a href={url} target="_blank" rel="noreferrer" className="text-sm underline">
            {t('media.watch')}
          </a>
        )}
      </div>
    </div>
  )
}

function YouTubeVideo({ video, active }: { video: Video; active: boolean }) {
  const label = `${videoKindLabels[video.kind]}: ${video.title ?? t('media.youtube')}`
  if (active) {
    // like the trailer, the player exists only while its slide is shown
    return (
      <iframe
        src={`https://www.youtube-nocookie.com/embed/${video.video_id}?rel=0`}
        title={label}
        allow="accelerometer; encrypted-media; picture-in-picture; fullscreen"
        allowFullScreen
        className="h-full w-full"
      />
    )
  }
  return (
    <div className="relative h-full w-full bg-black">
      <img
        src={`https://i.ytimg.com/vi/${video.video_id}/hqdefault.jpg`}
        alt=""
        loading="lazy"
        className="h-full w-full object-cover opacity-50"
      />
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center text-white">
        <Play className="size-12" />
        <span className="text-sm font-medium">{videoKindLabels[video.kind]}</span>
      </div>
    </div>
  )
}

type Slide =
  | { key: string; label: string; type: 'cover' }
  | { key: string; label: string; type: 'trailer'; url: string }
  | { key: string; label: string; type: 'youtube'; video: Video }

// The cover, the trailer and the videos of a game as slides: the rest is reached by swiping the picture.
export function MediaSlider({
  title,
  coverUrl,
  videoUrl,
  videos = [],
}: {
  title: string
  coverUrl: string | null
  videoUrl: string | null
  videos?: Video[]
}) {
  const { ref, index, canPrev, canNext, scrollPage, scrollToIndex } = useScroller()

  const slides: Slide[] = [{ key: 'cover', label: t('media.cover'), type: 'cover' }]
  if (videoUrl) slides.push({ key: 'trailer', label: t('media.trailer'), type: 'trailer', url: videoUrl })
  for (const video of videos) {
    slides.push({ key: video.kind, label: videoKindLabels[video.kind], type: 'youtube', video })
  }

  return (
    <div className="relative h-full w-full">
      <div ref={ref} className={cn('flex h-full snap-x snap-mandatory overflow-x-auto scroll-smooth', hideScrollbar)}>
        {slides.map((slide, i) => (
          <div key={slide.key} className="h-full w-full shrink-0 snap-center">
            {slide.type === 'cover' && <Cover url={coverUrl} title={title} />}
            {slide.type === 'trailer' && <Trailer url={slide.url} cover={coverUrl} title={title} active={index === i} />}
            {slide.type === 'youtube' && <YouTubeVideo video={slide.video} active={index === i} />}
          </div>
        ))}
      </div>

      {slides.length > 1 && (
        <>
          {canPrev && <ArrowButton direction="prev" onClick={() => scrollPage(-1)} />}
          {canNext && <ArrowButton direction="next" onClick={() => scrollPage(1)} />}
          <div className="absolute inset-x-0 bottom-2 z-10 flex justify-center gap-2">
            {slides.map((slide, i) => (
              <button
                key={slide.key}
                type="button"
                aria-label={slide.label}
                title={slide.label}
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
