import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { FundingProgress } from './FundingProgress'
import type { IQSource, SourceStatus } from '../types'

const ready: Record<IQSource, SourceStatus> = {
  fabric: 'retrieved', foundry: 'retrieved', work: 'retrieved', web: 'retrieved',
}

describe('Funding retrieval progress', () => {
  it('distinguishes final synthesis from active source retrieval', () => {
    const markup = renderToStaticMarkup(<FundingProgress
      progress={ready} activity={{ work: { source: 'work', citations: ['doc1', 'doc2'], durationMs: 12000 } }}
      loading hasResult={false} hasError={false} startedAt={null} finishedAt={null}
    />)
    expect(markup).toContain('Building your evidence-backed assessment')
    expect(markup).toContain('Retrieval is finished.')
    expect(markup).toContain('2 evidence sources')
    expect(markup).toContain('12s')
    expect(markup).not.toContain('Request in progress')
  })

  it('preserves successful results and never calls a failed run synthesis', () => {
    const markup = renderToStaticMarkup(<FundingProgress
      progress={{ ...ready, work: 'failed', web: 'skipped' }}
      activity={{ fabric: { source: 'fabric', citations: ['doc1'] } }}
      loading={false} hasResult={false} hasError startedAt={1000} finishedAt={66000}
    />)
    expect(markup).toContain('Assessment paused')
    expect(markup).toContain('Fabric IQ: Retrieved')
    expect(markup).toContain('Work IQ: Failed')
    expect(markup).toContain('External evidence: Skipped')
    expect(markup).toContain('1m 5s')
    expect(markup).not.toContain('Preparing the answer')
  })

  it('shows the Fabric dependency, then parallel active sources without fake completion', () => {
    const before = renderToStaticMarkup(<FundingProgress
      progress={{ fabric: 'searching', foundry: 'queued', work: 'queued', web: 'queued' }}
      activity={{}} loading hasResult={false} hasError={false} startedAt={null} finishedAt={null}
    />)
    expect(before).toContain('Waiting for scope')
    expect(before).toContain('Resolving the funding opportunity')
    const after = renderToStaticMarkup(<FundingProgress
      progress={{ ...ready, foundry: 'searching', work: 'searching' }}
      activity={{}} loading hasResult={false} hasError={false} startedAt={null} finishedAt={null}
    />)
    expect(after).toContain('Gathering evidence in parallel')
    expect(after).toContain('2 sources active.')
    expect(after).not.toContain('Assessment ready')
    expect(after).not.toContain('progressbar')
  })
})
