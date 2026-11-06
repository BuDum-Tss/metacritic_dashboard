export interface Platform {
  platform: string
  name: string
  metascore: number | null
  userscore: number | null
  critic_reviews_count: number | null
  user_reviews_count: number | null
}

export interface GameShort {
  id: number
  title: string
  cover_url: string | null
  developer: string | null
  genres: string[]
  platforms: Platform[]
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

export interface GameDetail extends GameShort {
  url: string
  description: string | null
  video_url: string | null
  first_seen_at: string
  updated_at: string
  last_processed_at: string
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

export interface SyncRun {
  id: number
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

export interface SyncStatus {
  running: boolean
  interval_hours: number
  next_run_at: string | null
  current_run: SyncRun | null
  last_run: SyncRun | null
}

export type SortKey = 'metascore' | 'userscore' | 'title' | 'updated'
export type SortOrder = 'asc' | 'desc'
