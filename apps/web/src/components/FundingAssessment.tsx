import { resolveApiUrl } from '../api/client'
import type { FundingAssessment } from '../fundingTypes'

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

export function FundingAssessmentPanel({ result }: { result: FundingAssessment }) {
  const evidenceById = new Map(result.evidence.map((item) => [item.refId, item]))
  const citations = (refs: string[]) => refs.map((ref) => {
    const evidence = evidenceById.get(ref)
    return evidence ? (
      <a key={ref} href={resolveApiUrl(evidence.url)} title={`${evidence.title}: ${evidence.snippet}`}>{ref}</a>
    ) : null
  })
  return (
    <div className="funding-results">
      <section className="funding-card">
        <p className="funding-eyebrow">Funding opportunity · as of {result.opportunity.asOfDate}</p>
        <h2>{result.opportunity.title}</h2>
        <p>{result.opportunity.id} · {result.opportunity.agency} · closes {result.opportunity.deadline} {result.opportunity.deadlineTimezone} ({result.deadlineDays} days)</p>
        <div className="funding-status">
          <strong>{result.pursuitStatus}</strong>
          <span>{result.eligibility}</span>
        </div>
        <p>{result.answer}</p>
        <p className="funding-citations">{citations(result.answerRefs)}</p>
        <p>{result.bottomLine}</p>
        <p><strong>Recommendation:</strong> {result.recommendation}</p>
        <p className="funding-caution">Recommendation is decision support only. A human funding decision is still required.</p>
      </section>

      <section className="funding-card">
        <h3>Eligibility and amendment impact</h3>
        <ul className="funding-list">
          {result.criteria.map((criterion) => (
            <li key={criterion.id}>
              <span className={`funding-pill ${criterion.status}`}>{criterion.status.replace('_', ' ')}</span>
              <span>{criterion.text}</span>
              <span className="funding-citations">{citations(criterion.evidenceRefs)}</span>
            </li>
          ))}
        </ul>
        <p>{result.amendmentSummary}</p>
      </section>

      <section className="funding-card">
        <h3>Match readiness</h3>
        <p>{result.matchBasis}</p>
        <div className="funding-amounts">
          <div><span>Required</span><strong>{money.format(result.matchRequired)}</strong></div>
          <div><span>Confirmed</span><strong>{money.format(result.matchConfirmed)}</strong></div>
          <div><span>Gap</span><strong className="funding-gap">{money.format(result.matchGap)}</strong></div>
        </div>
        <p>Eligible project-cost basis: {money.format(result.opportunity.eligibleCostBasis)} · requested grant share: {money.format(result.opportunity.requestedAmount)}</p>
        <p>Proposed (not counted): {money.format(result.matchProposed)}. Confirmed funds only reduce the gap.</p>
      </section>

      <section className="funding-card">
        <h3>Evidence-backed rationale and next actions</h3>
        <div className="funding-rationale">
          {result.rationale.map((item) => (
            <article key={item.heading}>
              <h4>{item.heading}</h4>
              <p>{item.text}</p>
              <p className="funding-citations">{citations(item.evidenceRefs)}</p>
            </article>
          ))}
        </div>
        <p><strong>{result.partner}:</strong> {result.partnerEvidence}</p>
        <div className="funding-tasks">
          {result.tasks.map((task) => (
            <article key={task.id}>
              <strong>{task.id}</strong>
              <p>{task.text}</p>
              <p>Owner: {task.owner.display} ({task.owner.id}) · due {task.due} · recorded {task.recordedState}</p>
              {task.dependencyIds.length > 0 ? <p>Depends on: {task.dependencyIds.join(', ')}</p> : null}
              <p className="funding-citations">{citations(task.evidenceRefs)}</p>
              <span className="funding-pill uncertain">{task.status}</span>
            </article>
          ))}
        </div>
        <p><strong>Executive review:</strong> {result.executiveReview}</p>
        <p><strong>Legal/procurement:</strong> {result.legalConstraint}</p>
        <p><strong>Application:</strong> {result.submissionStatus}. {result.unknownRequirements}</p>
      </section>

      <section className="funding-card funding-critical-path">
        <h3>Ordered readiness path</h3>
        <ol className="funding-list">
          {result.criticalPath.map((step) => (
            <li key={step.id}>
              <span className={`funding-pill ${step.status === 'At risk' ? 'not_met' : step.status === 'Available' ? 'unknown' : ''}`}>
                {step.status}
              </span>
              <span>
                <strong>{step.order}. {step.title}</strong>
                <span className="funding-path-detail">
                  {step.owner ? `Owner: ${step.owner.display} (${step.owner.id}) · ` : ''}
                  {step.due ? `due ${step.due} · ` : ''}Dependency: {step.dependency}. {step.detail}
                </span>
                <span className="funding-citations">{citations(step.evidenceRefs)}</span>
              </span>
            </li>
          ))}
        </ol>
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
