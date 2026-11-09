export interface Platform {
  platform: string
  name: string
  metascore: number | null
  userscore: number | null
  critic_reviews_count: number | null
  user_reviews_count: number | null
}

export interface Score {
  critics: number | null
  users: number | null
}

export interface GameShort {
  id: number
  title: string
  cover_url: string | null
  developer: string | null
  genres: string[]
  platforms: Platform[]
  score: Score
}

export interface Review {
  id: number
  author: string | null
  score: number | null
  date: string | null
  text: string
  url: string | null
  platform: string | null
}

export interface SummaryPoint {
  id: number
  text: string
  review_ids: number[]
}

export interface ReviewSummary {
  generated_at: string
  sample_size: number
  total_reviews: number | null
  model: string
  likes: SummaryPoint[]
  dislikes: SummaryPoint[]
  reviews: Review[]
}

export type ReviewKind = 'critics' | 'users'

export interface Overall {
  score: number | null
  verdict: string | null
  reviews_count: number | null
  positive: number | null
  mixed: number | null
  negative: number | null
  captured_at: string
}

export type VideoKind = 'letsplay' | 'review'

export interface Video {
  kind: VideoKind
  video_id: string
  title: string | null
  channel: string | null
  views: number | null
  url: string
  playlist_url: string | null
}

export interface TranscriptSegment {
  start: number
  text: string
  speaker: string | null
}

export type TranscriptStatus = 'pending' | 'running' | 'done' | 'failed'

export interface TranscriptVideo {
  video_id: string
  title: string | null
  position: number
  status: TranscriptStatus
  source: 'captions' | 'stt' | null
  language: string | null
  duration_seconds: number | null
  error: string | null
  summary_status: 'none' | 'pending' | 'running' | 'done' | 'failed'
}

export interface Transcripts {
  kind: VideoKind
  running: boolean
  stt_enabled: boolean
  llm_enabled: boolean
  videos: TranscriptVideo[]
  segments: TranscriptSegment[] | null
}

export interface Moment {
  start: number
  type: 'problem' | 'positive'
  topic: string
  note: string
}

export interface VideoSummary {
  video_id: string
  status: 'none' | 'pending' | 'running' | 'done' | 'failed'
  running: boolean
  llm_enabled: boolean
  text: string | null
  moments: Moment[]
  error: string | null
  model: string | null
  updated_at: string | null
}

export interface GameDetail extends GameShort {
  url: string
  description: string | null
  video_url: string | null
  release_date: string | null
  first_seen_at: string
  updated_at: string
  last_processed_at: string
  videos: Video[]
  similar: GameShort[]
  overall: Record<ReviewKind, Overall | null>
  summaries: Record<ReviewKind, ReviewSummary | null>
}

export interface GamePage {
  items: GameShort[]
  total: number
  page: number
  page_size: number
}

export interface PlatformOption {
  platform: string
  name: string
  games: number
}

export type Pipeline = 'crawl' | 'analysis' | 'videos'

export interface SyncRun {
  id: number
  pipeline: Pipeline
  trigger: 'schedule' | 'manual'
  status: 'running' | 'success' | 'failed'
  source: string
  batch_index: number
  started_at: string
  finished_at: string | null
  games_found: number | null
  games_processed: number | null
  games_failed: number | null
  error: string | null
}

export interface RunGame {
  game_id: number | null
  slug: string
  title: string | null
  outcome: string
  details: Record<string, string> | null
  error: string | null
}

export interface PipelineStatus {
  running: boolean
  enabled: boolean
  interval_hours: number
  budget: number
  next_run_at: string | null
  current_run: SyncRun | null
  last_run: SyncRun | null
}

export type SyncStatus = Record<Pipeline, PipelineStatus>

export type SortKey = 'metascore' | 'userscore' | 'release' | 'title' | 'updated'
export type SortOrder = 'asc' | 'desc'

export interface DashboardTiles {
  games_total: number
  new_7d: number
  hits_share: number | null
  avg_gap: number | null
}

export interface MapPoint {
  id: number
  title: string
  critics: number | null
  users: number | null
  attention: number
}

export interface GenreStat {
  genre: string
  games: number
  avg_critics: number | null
  avg_users: number | null
  avg_attention: number
}

export interface Divergence {
  id: number
  title: string
  critics: number
  users: number
  gap: number
  reason: { source: ReviewKind; text: string } | null
}

export interface RhythmDay {
  date: string
  games: number
  avg_critics: number | null
  games_avg7: number
  critics_avg7: number | null
}

export interface Dashboard {
  tiles: DashboardTiles
  map: { points: MapPoint[]; attention_median: number | null }
  genres: GenreStat[]
  divergences: { critics_love: Divergence[]; players_love: Divergence[] }
  rhythm: { days: RhythmDay[]; coverage: { with_date: number; total: number } }
}
