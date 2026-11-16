import { useState } from 'react'
import './App.css'
import { askFundingStream } from './api/fundingClient'
import { useAuthentication } from './authentication'
import { FundingAssessmentPanel } from './components/FundingAssessment'
import type { FundingAssessment } from './fundingTypes'
import type { IQSource, SourceStatus } from './types'

const HERO_QUESTION =
  'A new infrastructure and community-resilience grant closes in 30 days. Amendment 2 raises the local match to 25% and adds a regional-partner requirement. Are we eligible, should we pursue it, and what must happen next?'
const SOURCES: Array<{ source: IQSource; label: string }> = [
  { source: 'foundry', label: 'Foundry IQ' },
  { source: 'fabric', label: 'Fabric IQ' },
  { source: 'work', label: 'Work IQ' },
  { source: 'web', label: 'External evidence' },
]
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

  async function runAssessment() {
    setLoading(true)
    setError('')
    setResult(null)
    setProgress({ foundry: 'queued', fabric: 'queued', work: 'queued', web: 'queued' })
    try {
      const token = await getAccessToken()
      const assessment = await askFundingStream(question, token, (event) => {
        setProgress((current) => ({ ...current, [event.source]: event.status ?? 'searching' }))
      })
      setProgress(Object.fromEntries(
        assessment.sourceMap.map(({ source, status }) => [source, status]),
      ) as Record<IQSource, SourceStatus>)
      setResult(assessment)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The funding assessment could not be completed.')
      setProgress({ foundry: 'failed', fabric: 'failed', work: 'failed', web: 'failed' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="funding-app">
      <header className="funding-header">
        <div className="funding-brand"><span className="funding-mark">A</span><span>Award IQ</span></div>
        <span className="funding-synthetic">Synthetic scenario · Human reviewed</span>
      </header>
      <main className="funding-main">
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

        <section className="funding-progress" aria-label="Evidence retrieval progress" aria-live="polite">
          <h2>IQ evidence retrieval</h2>
          <div className="funding-source-grid">
            {SOURCES.map(({ source, label }) => (
              <div className="funding-source" key={source}>
                <strong>{label}</strong>
                <span>{progress[source]}</span>
              </div>
            ))}
          </div>
          <p>Mock mode uses deterministic synthetic fixtures. M365 data is not live-connected.</p>
        </section>
        {error ? <div className="funding-error" role="alert">{error}</div> : null}
        {result ? <FundingAssessmentPanel result={result} /> : null}
        <footer className="funding-footer">
          Award IQ is synthetic decision support, not a funding decision. Next actions are drafts only;
          no tasks, notifications, approvals, meetings, or applications are created or submitted.
        </footer>
      </main>
    </div>
  )
}

export default App
