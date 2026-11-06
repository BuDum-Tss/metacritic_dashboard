import type {
  GameDetail,
  GamePage,
  PlatformOption,
  SortKey,
  SortOrder,
  SyncRun,
  SyncStatus,
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
  platforms: () => request<PlatformOption[]>('/api/games/platforms'),
  syncStatus: () => request<SyncStatus>('/api/sync/status'),
  syncRuns: (limit = 20) => request<SyncRun[]>(`/api/sync/runs?limit=${limit}`),
  runSync: () => request<{ status: string }>('/api/sync/run', { method: 'POST' }),
}
