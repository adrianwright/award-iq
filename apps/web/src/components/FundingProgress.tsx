import { useEffect, useState, type ReactNode } from 'react'
import { ArrowRight, Check, CircleAlert, Clock3, LoaderCircle, Minus, Sparkles } from 'lucide-react'
import { sourceIcon, statusLabel } from '../sourceMeta'
import type { FundingSourceProgress } from '../fundingTypes'
import type { IQSource, SourceStatus } from '../types'
import './FundingProgress.css'

export type SourceActivity = FundingSourceProgress & { startedAt?: number }

const SOURCES: Array<{ source: IQSource; label: string; description: string }> = [
  { source: 'fabric', label: 'Fabric IQ', description: 'Notice scope, financials and match records' },
  { source: 'foundry', label: 'Foundry IQ', description: 'Current amendment and funding rules' },
  { source: 'work', label: 'Work IQ', description: 'Proposal documents and team coordination' },
  { source: 'web', label: 'External evidence', description: 'Packaged synthetic agency guidance' },
]

interface Props {
  progress: Record<IQSource, SourceStatus>
  activity: Partial<Record<IQSource, SourceActivity>>
  loading: boolean
  hasResult: boolean
  hasError: boolean
  startedAt: number | null
  finishedAt: number | null
  children?: ReactNode
}

function isRetrieved(status: SourceStatus) {
  return status === 'retrieved' || status === 'complete'
}

function formatDuration(ms: number) {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}

export function FundingProgress({
  progress, activity, loading, hasResult, hasError, startedAt, finishedAt, children,
}: Props) {
  const [now, setNow] = useState(Date.now)
  useEffect(() => {
    if (!loading) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [loading])

  const retrieved = Object.values(progress).filter(isRetrieved).length
  const active = Object.values(progress).filter((status) => status === 'searching').length
  const failed = Object.values(progress).some((status) => status === 'failed')
  const scopeReady = isRetrieved(progress.fabric)
  const allSettled = Object.values(progress).every((status) => isRetrieved(status) || status === 'needs_review')
  const synthesizing = loading && allSettled && !failed
  const headline = hasError
    ? 'Assessment paused'
    : hasResult ? 'Assessment ready for review'
    : failed ? 'A source needs attention'
    : synthesizing ? 'Building your evidence-backed assessment'
    : loading && scopeReady ? 'Gathering evidence in parallel'
    : loading ? 'Resolving the funding opportunity'
    : 'From evidence to a funding decision'
  const detail = hasError || failed
    ? 'Successful retrievals are preserved. No substitute evidence is used.'
    : hasResult ? 'Review the sources, funding conditions and proposed next steps below.'
    : synthesizing ? 'Reconciling the sources and writing the final answer. Retrieval is finished.'
    : loading && scopeReady ? `${active} source${active === 1 ? '' : 's'} active. Each card updates as its response arrives.`
    : loading ? 'Fabric establishes the notice and document scope before the other sources begin.'
    : 'Resolve the opportunity, gather independent sources, then prepare one assessment.'
  const elapsed = startedAt === null ? null : formatDuration((finishedAt ?? now) - startedAt)
  const PhaseIcon = hasError || failed ? CircleAlert : hasResult ? Check : loading ? LoaderCircle : Sparkles

  return (
    <section className="funding-progress funding-retrieval" aria-label="Evidence retrieval progress">
      <div className="retrieval-heading">
        <div className={`retrieval-phase-icon${loading && !failed ? ' is-active' : ''}`}>
          <PhaseIcon size={24} aria-hidden="true" />
        </div>
        <div className="retrieval-heading-copy" role="status">
          <p className="retrieval-eyebrow">IQ evidence retrieval</p>
          <h2>{headline}</h2>
          <p>{detail}</p>
        </div>
        {elapsed !== null && <span className="retrieval-elapsed" aria-label={`Elapsed time ${elapsed}`}>
          <Clock3 size={14} aria-hidden="true" /> {elapsed}
        </span>}
      </div>

      <ol className="retrieval-phases" aria-label="Assessment stages">
        <li className={scopeReady ? 'is-done' : loading ? 'is-current' : ''}>
          {scopeReady ? <Check size={14} aria-hidden="true" /> : <span aria-hidden="true">1</span>}
          Resolve opportunity
        </li>
        <li aria-hidden="true" className="retrieval-arrow"><ArrowRight size={16} /></li>
        <li className={allSettled ? 'is-done' : scopeReady && loading ? 'is-current' : ''}>
          {allSettled ? <Check size={14} aria-hidden="true" /> : <span aria-hidden="true">2</span>}
          Gather evidence
        </li>
        <li aria-hidden="true" className="retrieval-arrow"><ArrowRight size={16} /></li>
        <li className={hasResult ? 'is-done' : synthesizing ? 'is-current' : ''}>
          {hasResult ? <Check size={14} aria-hidden="true" /> : <span aria-hidden="true">3</span>}
          Prepare assessment
        </li>
      </ol>

      <div className="retrieval-source-grid">
        {SOURCES.map(({ source, label, description }) => {
          const status = progress[source]
          const entry = activity[source]
          const Icon = sourceIcon[source]
          const StatusIcon = isRetrieved(status) ? Check
            : status === 'searching' ? LoaderCircle
            : status === 'failed' || status === 'needs_review' ? CircleAlert
            : status === 'skipped' ? Minus : Clock3
          const labelText = status === 'idle' ? 'Ready'
            : status === 'queued' && !scopeReady && source !== 'fabric' ? 'Waiting for scope'
            : status === 'searching' ? source === 'web' ? 'Loading guidance' : 'Retrieving'
            : statusLabel(status)
          const duration = status === 'searching' && entry?.startedAt
            ? formatDuration(now - entry.startedAt)
            : entry?.durationMs !== undefined && entry.durationMs > 0 ? formatDuration(entry.durationMs) : null
          const citationCount = entry?.citations?.length
          return (
            <article key={source} className={`retrieval-source state-${status}`} aria-label={`${label}: ${labelText}`}>
              <div className="retrieval-source-top">
                <span className="retrieval-source-icon"><Icon size={24} strokeWidth={1.6} aria-hidden="true" /></span>
                <span className={`retrieval-state${status === 'searching' ? ' is-active' : ''}`}>
                  <StatusIcon size={14} aria-hidden="true" /> {labelText}
                </span>
              </div>
              <h3>{label}</h3>
              <p>{description}</p>
              <div className="retrieval-source-foot">
                <span>{isRetrieved(status) && citationCount !== undefined
                  ? `${citationCount} evidence source${citationCount === 1 ? '' : 's'}`
                  : status === 'needs_review' ? 'Evidence needs review'
                  : status === 'failed' ? 'See the error below'
                  : status === 'skipped' ? 'Not started'
                  : status === 'searching' ? 'Request in progress'
                  : 'Awaiting assessment'}</span>
                {duration && <span className="retrieval-duration">{duration}</span>}
              </div>
            </article>
          )
        })}
      </div>
      <div className="retrieval-footer">
        <span><strong>{retrieved} / 4</strong> sources retrieved</span>
        {synthesizing && <span className="retrieval-synthesis"><Sparkles size={16} aria-hidden="true" /> Preparing the answer</span>}
        {loading && active > 0 && <span>Live source updates</span>}
      </div>
      {children && <div className="retrieval-provenance">{children}</div>}
    </section>
  )
}
