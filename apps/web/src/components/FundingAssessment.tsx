import { resolveApiUrl } from '../api/client'
import type { FundingAssessment } from '../fundingTypes'
import './FundingAssessment.css'

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const sourceNames = { foundry: 'Funding documents', fabric: 'Funding records', work: 'Team documents', web: 'External guidance' }
const date = (value: string) => new Date(`${value}T12:00:00Z`).toLocaleDateString('en-US', {
  month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC',
})

export function FundingAssessmentPanel({ result }: { result: FundingAssessment }) {
  const evidenceById = new Map(result.evidence.map((item, index) => [item.refId, { ...item, number: index + 1 }]))
  const citations = (refs: string[]) => [...new Set(refs)].map((ref) => {
    const evidence = evidenceById.get(ref)
    return evidence ? (
      <a key={ref} href={resolveApiUrl(evidence.url)} title={evidence.title}
        aria-label={`Source ${evidence.number}: ${evidence.title}`} target="_blank" rel="noopener noreferrer">
        [{evidence.number}]
      </a>
    ) : null
  })
  const citedText = (text: string) => text.split(/(\[DOC-[^\]]+\])/g).map((part, index) =>
    /^\[DOC-[^\]]+\]$/.test(part)
      ? <sup className="assessment-citations" key={index}>{citations([part.slice(1, -1)])}</sup>
      : part,
  )
  const steps = [...result.criticalPath].sort((a, b) => a.order - b.order)
  const stepTitle = (step: FundingAssessment['criticalPath'][number]) =>
    step.title.startsWith(`${step.id}: `) ? step.title.slice(step.id.length + 2) : step.title
  const unresolved = result.criteria.filter((criterion) => criterion.status !== 'met')

  return (
    <div className="funding-results assessment">
      <section className="assessment-card assessment-summary" aria-labelledby="assessment-title">
        <p className="assessment-eyebrow">{result.opportunity.id} · As of {date(result.opportunity.asOfDate)}</p>
        <h2 id="assessment-title">{result.opportunity.title}</h2>
        <div className="assessment-status">
          <strong>{result.pursuitStatus}</strong>
          <span>{result.eligibility}</span>
        </div>
        <p className="assessment-takeaway">{citedText(result.bottomLine)}</p>
        <div className="assessment-answer">
          {result.answer.split(/\n\s*\n/).filter(Boolean).map((paragraph, index) =>
            <p key={index}>{citedText(paragraph)}</p>,
          )}
        </div>
        {!/\[DOC-[^\]]+\]/.test(result.answer + result.bottomLine) &&
          <p className="assessment-citations">Sources {citations(result.answerRefs)}</p>}
        <dl className="assessment-facts">
          <div><dt>Unconfirmed match</dt><dd>{money.format(result.matchGap)}</dd>
            <small>{money.format(result.matchConfirmed)} confirmed / {money.format(result.matchRequired)} required</small></div>
          <div><dt>Application deadline</dt><dd>{date(result.opportunity.deadline)}</dd>
            <small>{result.deadlineDays} days from assessment · {result.opportunity.deadlineTimezone}</small></div>
          <div><dt>Application</dt><dd>{result.submissionStatus}</dd>
            <small>Human review required</small></div>
        </dl>
        {unresolved.length > 0 && <div className="assessment-conditions">
          <h3>Conditions still open</h3>
          <ul>{unresolved.map((criterion) => <li key={criterion.id}>
            <strong>{criterion.status === 'not_met' ? 'Not met' : 'Unverified'}:</strong> {criterion.text}{' '}
            <span className="assessment-citations">{citations(criterion.evidenceRefs)}</span>
          </li>)}</ul>
        </div>}
        <p className="assessment-unknowns"><strong>Before submission:</strong> {result.unknownRequirements}</p>
      </section>

      <section className="assessment-card assessment-actions" aria-labelledby="assessment-actions-title">
        <div className="assessment-section-heading">
          <h3 id="assessment-actions-title">What happens next</h3>
          <span>Suggested actions · Nothing booked or submitted</span>
        </div>
        <div className="assessment-table-wrap">
          <table>
            <caption className="assessment-sr-only">Ordered next actions with accountable owners and recorded status</caption>
            <thead><tr><th scope="col">Action</th><th scope="col">Owner</th><th scope="col">Due</th><th scope="col">Status</th></tr></thead>
            <tbody>{steps.map((step) => <tr key={step.id}>
              <th scope="row"><span className="assessment-step">{step.order}.</span> {stepTitle(step)}</th>
              <td>{step.owner?.display ?? 'Not assigned'}</td>
              <td>{step.due ? date(step.due) : 'Not set'}</td>
              <td>{step.status}</td>
            </tr>)}</tbody>
          </table>
        </div>
        <details className="assessment-action-details">
          <summary>Dependencies and review constraints</summary>
          <p><strong>Executive review:</strong> {result.executiveReview}</p>
          <p><strong>Legal / procurement:</strong> {result.legalConstraint}</p>
          <p><strong>{result.partner}:</strong> {result.partnerEvidence}</p>
          <ol>{steps.map((step) => <li key={step.id}>
            <strong>{stepTitle(step)}.</strong> {step.detail} Dependency: {step.dependency}{' '}
            <span className="assessment-citations">{citations(step.evidenceRefs)}</span>
          </li>)}</ol>
        </details>
      </section>

      <div className="assessment-support">
        <details className="assessment-detail">
          <summary>Eligibility and funding calculation</summary>
          <p>{result.amendmentSummary}</p>
          <ul>{result.criteria.map((criterion) => <li key={criterion.id}>
            <strong>{criterion.status === 'met' ? 'Met' : criterion.status === 'not_met' ? 'Not met' : 'Unverified'}:</strong>{' '}
            {criterion.text} <span className="assessment-citations">{citations(criterion.evidenceRefs)}</span>
          </li>)}</ul>
          <p>{result.matchBasis}</p>
          <p>Eligible project costs: {money.format(result.opportunity.eligibleCostBasis)}.
            Requested grant: {money.format(result.opportunity.requestedAmount)}.</p>
          <p>Required {money.format(result.matchRequired)} − confirmed {money.format(result.matchConfirmed)} =
            gap {money.format(result.matchGap)}. Proposed {money.format(result.matchProposed)} is not counted as confirmed.</p>
        </details>
        <details className="assessment-detail">
          <summary>Sources ({result.evidence.length})</summary>
          <ol className="assessment-sources">{result.evidence.map((item) => <li key={item.refId}>
            <a href={resolveApiUrl(item.url)} target="_blank" rel="noopener noreferrer">{item.title}</a>
            <span>{sourceNames[item.source]}</span>
          </li>)}</ol>
        </details>
        <details className="assessment-detail assessment-diagnostics">
          <summary>Technical details</summary>
          <p>{result.mode === 'live' ? 'Live Fabric records' : 'Local fixture records'} ·{' '}
            {result.knowledgeMode === 'foundry_iq' ? 'Live Foundry IQ' : 'Packaged funding documents'} ·{' '}
            {result.workMode === 'work_iq' ? 'Live Work IQ' : 'Packaged team documents'} · Packaged external guidance</p>
          <p>{result.narrativeModel ? `Narrative model: ${result.narrativeModel}` : 'Deterministic fixture narrative'}</p>
          <ol>{result.trace.map((step, index) => <li key={`${step.ts}-${index}`}>
            <strong>{step.step}</strong> {step.detail}
          </li>)}</ol>
        </details>
      </div>
      <p className="assessment-disclaimer">{result.disclaimer}</p>
    </div>
  )
}
