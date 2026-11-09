import type {
  Dashboard,
  GameDetail,
  GamePage,
  Pipeline,
  PlatformOption,
  RunGame,
  SortKey,
  SortOrder,
  SyncRun,
  SyncStatus,
  Transcripts,
  VideoKind,
} from './types'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    let message = response.statusText
    try {
      message = (await response.json()).detail ?? message
    } catch {
      // keep the status text
    }
    throw new ApiError(response.status, message)
  }
  return response.json()
}

export interface GamesQuery {
  q?: string
  platform?: string
  sort: SortKey
  order: SortOrder
  page: number
  pageSize: number
}

export const api = {
  games: (query: GamesQuery) => {
    const params = new URLSearchParams({
      sort: query.sort,
      order: query.order,
      page: String(query.page),
      page_size: String(query.pageSize),
    })
    if (query.q) params.set('q', query.q)
    if (query.platform) params.set('platform', query.platform)
    return request<GamePage>(`/api/games?${params}`)
  },
  game: (id: number) => request<GameDetail>(`/api/games/${id}`),
  transcripts: (gameId: number, kind: VideoKind, videoId?: string) =>
    request<Transcripts>(`/api/games/${gameId}/transcripts/${kind}${videoId ? `?video_id=${encodeURIComponent(videoId)}` : ''}`),
  requestTranscripts: (gameId: number, kind: VideoKind) =>
    request<{ status: string }>(`/api/games/${gameId}/transcripts/${kind}`, { method: 'POST' }),
  platforms: () => request<PlatformOption[]>('/api/games/platforms'),
  dashboard: () => request<Dashboard>('/api/dashboard'),
  syncStatus: () => request<SyncStatus>('/api/sync/status'),
  syncRuns: (pipeline: Pipeline, limit = 20) =>
    request<SyncRun[]>(`/api/sync/runs?pipeline=${pipeline}&limit=${limit}`),
  runGames: (runId: number) => request<RunGame[]>(`/api/sync/runs/${runId}/games`),
  runSync: (pipeline: Pipeline) =>
    request<{ status: string }>(`/api/sync/run?pipeline=${pipeline}`, { method: 'POST' }),
}
