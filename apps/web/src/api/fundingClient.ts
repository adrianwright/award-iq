import type { FundingAssessment, FundingSourceProgress } from '../fundingTypes'
import { authorizationHeaders, RequestError } from './client'

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
const STREAM_ENDPOINT = `${API_BASE}/api/funding/ask/stream`

export async function askFundingStream(
  question: string,
  accessToken: string | null,
  onSource: (progress: FundingSourceProgress) => void,
): Promise<FundingAssessment> {
  const response = await fetch(STREAM_ENDPOINT, {
    method: 'POST',
    headers: {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
      ...authorizationHeaders(accessToken),
    },
    body: JSON.stringify({ question }),
  })
  if (!response.ok) {
    let detail = `Request failed with ${response.status}`
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // Keep the HTTP status when the server does not return JSON.
    }
    throw new RequestError(detail, response.status)
  }
  if (!response.body) throw new Error('Funding assessment stream is unavailable.')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResult: FundingAssessment | undefined
  const readFrame = (frame: string) => {
    let eventType = ''
    const data: string[] = []
    for (const line of frame.split(/\r?\n/)) {
      if (line.startsWith('event:')) eventType = line.slice(6).trim()
      if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
    }
    if (!data.length) return
    const payload = JSON.parse(data.join('\n')) as Record<string, unknown>
    if (eventType === 'source_query') {
      onSource(payload as unknown as FundingSourceProgress)
    } else if (eventType === 'source_result') {
      onSource(payload as unknown as FundingSourceProgress)
    } else if (eventType === 'final') {
      finalResult = payload.result as FundingAssessment
    } else if (eventType === 'error') {
      throw new Error(String(payload.message ?? 'Funding assessment failed.'))
    }
  }

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split(/\r?\n\r?\n/)
    buffer = frames.pop() ?? ''
    frames.forEach(readFrame)
  }
  buffer += decoder.decode()
  if (buffer.trim()) readFrame(buffer)
  if (!finalResult) throw new Error('Funding assessment stream ended before a result was returned.')
  return finalResult
}
