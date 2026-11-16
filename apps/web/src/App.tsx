import { useEffect, useRef, useState } from 'react'
import './App.css'
import { askFundingStream } from './api/fundingClient'
import { useAuthentication } from './authentication'
import { FundingAssessmentPanel } from './components/FundingAssessment'
import { FundingProgress, type SourceActivity } from './components/FundingProgress'
import type { FundingAssessment } from './fundingTypes'
import type { IQSource, SourceStatus } from './types'

const HERO_QUESTION =
  'A new infrastructure and community-resilience grant closes in 30 days. Amendment 2 raises the local match to 25% and adds a regional-partner requirement. Are we eligible, should we pursue it, and what must happen next?'
const QUESTION_EXAMPLES = [
  'How much confirmed match is still missing, and what must happen next?',
  'Is FO-2026-204 ready to submit?',
  'Which eligibility criterion is not met for FO-2026-330?',
]

function App() {
  const { getAccessToken } = useAuthentication()
  const [question, setQuestion] = useState(HERO_QUESTION)
  const [result, setResult] = useState<FundingAssessment | null>(null)
  const [progress, setProgress] = useState<Record<IQSource, SourceStatus>>({
    foundry: 'idle',
    fabric: 'idle',
    work: 'idle',
    web: 'idle',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [activity, setActivity] = useState<Partial<Record<IQSource, SourceActivity>>>({})
  const [startedAt, setStartedAt] = useState<number | null>(null)
  const [finishedAt, setFinishedAt] = useState<number | null>(null)
  const resultRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (result) {
      resultRef.current?.focus({ preventScroll: true })
      resultRef.current?.scrollIntoView({
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',
        block: 'start',
      })
    }
  }, [result])

  async function runAssessment() {
    setLoading(true)
    setError('')
    setResult(null)
    setStartedAt(Date.now())
    setFinishedAt(null)
    setActivity({})
    setProgress({ foundry: 'queued', fabric: 'queued', work: 'queued', web: 'queued' })
    try {
      const token = await getAccessToken()
      const assessment = await askFundingStream(question, token, (event) => {
        setProgress((current) => ({ ...current, [event.source]: event.status ?? 'searching' }))
        setActivity((current) => ({
          ...current,
          [event.source]: {
            ...current[event.source],
            ...event,
            startedAt: current[event.source]?.startedAt ?? (event.status === 'searching' ? Date.now() : undefined),
            durationMs: event.durationMs || current[event.source]?.durationMs,
          },
        }))
      })
      setProgress(Object.fromEntries(
        assessment.sourceMap.map(({ source, status }) => [source, status]),
      ) as Record<IQSource, SourceStatus>)
      setResult(assessment)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The funding assessment could not be completed.')
      setProgress((current) => Object.fromEntries(
        Object.entries(current).map(([source, status]) => [
          source,
          status === 'searching' ? 'failed' : status === 'queued' ? 'skipped' : status,
        ]),
      ) as Record<IQSource, SourceStatus>)
    } finally {
      setFinishedAt(Date.now())
      setLoading(false)
    }
  }

  return (
    <div className="funding-app">
      <header className="funding-header">
        <div className="funding-brand"><span className="funding-mark">A</span><span>Award IQ</span></div>
        <span className="funding-synthetic">Synthetic scenario · Human review required</span>
      </header>
      <main className="funding-main">
        <details className={`funding-question-panel ${result ? '' : 'is-initial'}`} open={!result}>
        <summary>Your question / Ask another question</summary>
        <section className="funding-hero">
          <p className="funding-eyebrow">Grant eligibility and funding readiness</p>
          <h1>Make the next funding decision with evidence.</h1>
          <p>Ground a grant-readiness assessment across current funding rules, structured operations, team workflow, and external guidance.</p>
          <label htmlFor="funding-question">Ask about a funding opportunity</label>
          <textarea
            id="funding-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={4}
          />
          <div className="funding-example-questions" aria-label="Example funding questions">
            {QUESTION_EXAMPLES.map((example) => (
              <button
                type="button"
                key={example}
                onClick={() => setQuestion(example)}
                disabled={loading}
              >
                {example}
              </button>
            ))}
          </div>
          <button type="button" onClick={() => void runAssessment()} disabled={loading || !question.trim()}>
            {loading ? 'Building assessment…' : 'Assess funding readiness'}
          </button>
        </section>
        </details>

        <details className={`funding-completed-progress ${result ? '' : 'is-active'}`} open={!result}>
          <summary>Retrieval complete
            <span>{result?.evidence.length} sources{startedAt && finishedAt
              ? ` · ${Math.round((finishedAt - startedAt) / 1000)}s` : ''}</span>
          </summary>
        <FundingProgress
          progress={progress} activity={activity} loading={loading}
          hasResult={result !== null} hasError={Boolean(error)}
          startedAt={startedAt} finishedAt={finishedAt}
        >
          <p>{result
            ? [
                result.mode === 'live' ? 'Live Fabric SQL reads.' : 'Local fixture assessment.',
                result.knowledgeMode === 'foundry_iq'
                  ? 'Live Foundry IQ retrieval over indexed funding documents.'
                  : 'Funding documents are packaged fixtures.',
                result.narrativeModel ? `Narrative generated by ${result.narrativeModel}.` : 'Deterministic narrative.',
                result.workMode === 'work_iq'
                  ? 'Live delegated Work IQ over synthetic M365 documents.'
                  : 'M365 is not live-connected.',
                'All scenario records are synthetic.',
              ].join(' ')
            : 'Synthetic decision support. Connection and model provenance appear with each assessment.'}</p>
        </FundingProgress>
        </details>
        {error ? <div className="funding-error" role="alert">{error}</div> : null}
        {result ? <div ref={resultRef} tabIndex={-1} className="funding-result-target" aria-label="Funding assessment result">
          <FundingAssessmentPanel result={result} />
        </div> : null}
        {!result && <footer className="funding-footer">
          Award IQ is synthetic decision support, not a funding decision. Next actions are drafts only;
          no tasks, notifications, approvals, meetings, or applications are created or submitted.
        </footer>}
      </main>
    </div>
  )
}

export default App
