import { resolveApiUrl } from '../api/client'
import type { FundingAssessment } from '../fundingTypes'

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

export function FundingAssessmentPanel({ result }: { result: FundingAssessment }) {
  const evidenceById = new Map(result.evidence.map((item) => [item.refId, item]))
  return (
    <div className="funding-results">
      <section className="funding-card">
        <p className="funding-eyebrow">Funding opportunity · as of {result.opportunity.asOfDate}</p>
        <h2>{result.opportunity.title}</h2>
        <p>{result.opportunity.id} · {result.opportunity.agency} · closes {result.opportunity.deadline} ({result.deadlineDays} days)</p>
        <div className="funding-status">
          <strong>{result.pursuitStatus}</strong>
          <span>{result.eligibility}</span>
        </div>
        <p>{result.bottomLine}</p>
        <p className="funding-caution">Recommendation is decision support only. A human funding decision is still required.</p>
      </section>

      <section className="funding-card">
        <h3>Eligibility and amendment impact</h3>
        <ul className="funding-list">
          {result.criteria.map((criterion) => (
            <li key={criterion.text}>
              <span className={`funding-pill ${criterion.status}`}>{criterion.status.replace('_', ' ')}</span>
              <span>{criterion.text}</span>
              <span className="funding-citations">
                {criterion.evidenceRefs.map((ref) => {
                  const evidence = evidenceById.get(ref)
                  return evidence ? (
                    <a key={ref} href={resolveApiUrl(evidence.url)} title={`${evidence.title}: ${evidence.snippet}`}>{ref}</a>
                  ) : null
                })}
              </span>
            </li>
          ))}
        </ul>
        <p>Amendment 2 is current: match increased from 20% to 25% and a current regional-partner commitment letter is required.</p>
      </section>

      <section className="funding-card">
        <h3>Match readiness</h3>
        <p>{result.matchBasis}</p>
        <div className="funding-amounts">
          <div><span>Required</span><strong>{money.format(result.matchRequired)}</strong></div>
          <div><span>Confirmed</span><strong>{money.format(result.matchConfirmed)}</strong></div>
          <div><span>Gap</span><strong className="funding-gap">{money.format(result.matchGap)}</strong></div>
        </div>
        <p>Proposed (not counted): {money.format(result.matchProposed)}. Confirmed funds only reduce the gap.</p>
      </section>

      <section className="funding-card">
        <h3>Partner and drafted next actions</h3>
        <p><strong>{result.partner}:</strong> {result.partnerEvidence}</p>
        <div className="funding-tasks">
          {result.tasks.map((task) => (
            <article key={task.id}>
              <strong>{task.id}</strong>
              <p>{task.text}</p>
              <p>Owner: {task.owner.display} ({task.owner.id}) · due {task.due}</p>
              <span className="funding-pill uncertain">{task.status}</span>
            </article>
          ))}
        </div>
        <p><strong>Executive review:</strong> {result.executiveReview}</p>
        <p><strong>Legal/procurement:</strong> {result.legalConstraint}</p>
        <p><strong>Application:</strong> {result.submissionStatus}</p>
      </section>

      <section className="funding-card">
        <h3>Evidence packet</h3>
        <ol className="funding-list">
          {result.evidence.map((item) => (
            <li key={item.refId}>
              <a href={resolveApiUrl(item.url)}>{item.refId} · {item.title}</a>
              <span>{item.source.toUpperCase()} · {item.sourceType} · {item.snippet}</span>
            </li>
          ))}
        </ol>
        <h3>Assessment steps</h3>
        <ol className="funding-list">
          {result.trace.map((step) => <li key={step.ts}><strong>{step.step}</strong><span>{step.detail}</span></li>)}
        </ol>
      </section>
      <p className="funding-disclaimer">{result.disclaimer}</p>
    </div>
  )
}
