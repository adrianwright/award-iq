import { afterEach, describe, expect, it, vi } from 'vitest'
import { authorizationHeaders, getFabricStatus, resolveApiUrl } from './client'
import { askFundingStream } from './fundingClient'

afterEach(() => vi.unstubAllGlobals())

describe('shared funding HTTP helpers', () => {
  it('distinguishes anonymous access from an invalid empty token', () => {
    expect(authorizationHeaders(null)).toEqual({})
    expect(authorizationHeaders('token')).toEqual({ Authorization: 'Bearer token' })
    expect(() => authorizationHeaders(' ')).toThrow('Access token is required')
  })

  it('keeps external source links intact and accepts missing links', () => {
    expect(resolveApiUrl('https://example.com/evidence')).toBe('https://example.com/evidence')
    expect(resolveApiUrl(null)).toBeUndefined()
  })

  it('reports an unknown capacity when the status service is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    expect((await getFabricStatus()).state).toBe('Unknown')
  })
})

describe('funding stream', () => {
  it('uses the funding route and delegated header, forwarding source progress', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response([
      'event: source_query',
      'data: {"source":"fabric","status":"searching"}',
      '',
      'event: final',
      'data: {"result":{"question":"FO-2026-117"}}',
      '',
      '',
    ].join('\r\n')))
    vi.stubGlobal('fetch', fetch)
    const progress = vi.fn()
    const result = await askFundingStream('FO-2026-117', 'token', progress)
    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/funding\/ask\/stream$/),
      expect.objectContaining({
        body: JSON.stringify({ question: 'FO-2026-117' }),
        headers: expect.objectContaining({ Authorization: 'Bearer token' }),
      }),
    )
    expect(progress).toHaveBeenCalledWith({ source: 'fabric', status: 'searching' })
    expect(result.question).toBe('FO-2026-117')
  })

  it('surfaces source failure instead of returning a sample assessment', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response('event: error\ndata: {"message":"Fabric unavailable"}\n\n'),
    ))
    await expect(askFundingStream('FO-2026-117', null, vi.fn())).rejects.toThrow('Fabric unavailable')
  })

  it('rejects an incomplete stream', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('event: plan\ndata: {"steps":[]}\n\n')))
    await expect(askFundingStream('FO-2026-117', null, vi.fn())).rejects.toThrow('before a result')
  })
})
