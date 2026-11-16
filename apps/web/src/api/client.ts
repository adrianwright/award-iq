import type { FabricStatus } from '../types'

// In production the UI calls the Container App API directly (VITE_API_BASE_URL) so that Server-Sent
// Events stream live; the Static Web App managed proxy buffers SSE, which would leave the IQ layers
// stuck "queued". Locally VITE_API_BASE_URL is unset and the Vite dev proxy handles /api.
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
const FABRIC_STATUS_ENDPOINT = `${API_BASE}/api/fabric/status`

/** Resolve a relative backend link (e.g. /api/evidence/doc?...) against the API base so evidence
 *  links work when the UI is served from the Static Web App but the API is the Container App. */
export function resolveApiUrl(url: string | undefined | null): string | undefined {
  if (!url) return undefined
  return url.startsWith('/api/') ? `${API_BASE}${url}` : url
}

/** Backend HTTP status and error detail. */
export class RequestError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'RequestError'
    this.status = status
  }
}

export function authorizationHeaders(accessToken: string | null): Record<string, string> {
  if (accessToken === null) return {}
  if (!accessToken.trim()) throw new Error('Access token is required')
  return { Authorization: `Bearer ${accessToken}` }
}

/** Read-only Fabric capacity state (Active/Paused/Resuming/Pausing/Unknown) so the UI can tell users
 *  whether a live assessment will work. The backend never errors this route; on any backend/network
 *  failure we return an "Unknown" status so the chip stays informative rather than throwing. */
export async function getFabricStatus(): Promise<FabricStatus> {
  const unknown: FabricStatus = { state: 'Unknown', capacityName: '', portalUrl: '' }
  try {
    const response = await fetch(FABRIC_STATUS_ENDPOINT, { headers: { Accept: 'application/json' } })
    if (!response.ok) return unknown
    return (await response.json()) as FabricStatus
  } catch {
    return unknown
  }
}
