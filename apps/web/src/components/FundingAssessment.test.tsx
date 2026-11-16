import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { FundingAssessmentPanel } from './FundingAssessment'
import type { FundingAssessment } from '../fundingTypes'

const result: FundingAssessment = {
  question: 'Should we pursue FO-2026-117?',
  answer: 'Current grant scenario.',
  bottomLine: 'Pursue - pending; resolve the match and partner conditions.',
  opportunity: {
    id: 'FO-2026-117',
    programId: 'PROGRAM-RESILIENCE',
    projectId: 'PROJECT-RESILIENCE-2026',
    title: 'Community Resilience Infrastructure Grant',
    agency: 'Federal Resilience Agency',
    deadline: '2026-12-16',
    deadlineTimezone: 'America/New_York',
    asOfDate: '2026-11-16',
    eligibleCostBasis: 9000000,
    requestedAmount: 6750000,
    projectCostBasis: 'Synthetic fixture-design assumption.',
  },
  pursuitStatus: 'Pursue - pending',
  recommendation: 'Continue conditionally.',
  eligibility: 'Conditional / unresolved evidence',
  amendmentSummary: 'Amendment 2 is current.',
  matchBasis: '25% of total eligible project costs',
  matchRequired: 2250000,
  matchConfirmed: 1800000,
  matchProposed: 450000,
  matchGap: 450000,
  deadlineDays: 30,
  criteria: [{ id: 'FO117-ELIG-PARTNER', text: 'Regional partner letter', status: 'unknown', evidenceRefs: ['DOC-AMD2'] }],
  rationale: [{ heading: 'Why conditional pursuit may be worthwhile', text: 'Program and community alignment.', evidenceRefs: ['DOC-OUTCOMES'] }],
  partner: 'Regional Transit Authority',
  partnerEvidence: '2024 letter is a lead only.',
  tasks: [
    { id: 'TASK-117-MATCH', text: 'Confirm capital reserve.', owner: { id: 'FIN-02', display: 'Maria Santos', role: 'Finance' }, due: '2026-11-18', recordedState: 'Open', dependencyIds: [], evidenceRefs: ['DOC-MATCH'], status: 'Drafted (not submitted)' },
    { id: 'TASK-117-PARTNER', text: 'Request current letter.', owner: { id: 'PM-01', display: 'Jordan Lee', role: 'Proposal Manager' }, due: '2026-11-20', recordedState: 'Open', dependencyIds: ['SLOT-117'], evidenceRefs: ['DOC-PARTNER'], status: 'Drafted (not submitted)' },
  ],
  criticalPath: [{
    id: 'TASK-117-MATCH',
    order: 1,
    title: 'Confirm match',
    owner: { id: 'FIN-02', display: 'Maria Santos', role: 'Finance' },
    due: '2026-11-18',
    status: 'Open',
    dependency: 'None',
    detail: 'Confirm then document the source.',
    evidenceRefs: ['DOC-MATCH'],
  }],
  executiveReview: '2026-11-19, 10:00-11:00 America/New_York (EST, UTC-05:00)',
  legalConstraint: 'Sam Patel unavailable 2026-11-23 through 2026-11-27; finish by 2026-11-20.',
  submissionStatus: 'Not submitted',
  unknownRequirements: 'Confirm portal-specific attachments.',
  evidence: [
    { refId: 'DOC-AMD2', source: 'foundry', title: 'Amendment 2', snippet: 'Current amendment', url: '/api/evidence/doc?path=foundry_docs/amendment.md', sourceType: 'Current effective amendment · v2 · published 2026-10-28' },
    { refId: 'DOC-OUTCOMES', source: 'foundry', title: 'Outcomes', snippet: 'Synthetic program evidence', url: '/api/evidence/doc?path=foundry_docs/outcomes.md', sourceType: 'Program performance · v1 · published 2026-10-31' },
    { refId: 'DOC-MATCH', source: 'fabric', title: 'Match', snippet: 'Confirmed and proposed allocations', url: '/api/evidence/doc?path=funding_ops/snapshot.md', sourceType: 'Structured operations · v1 · published 2026-11-16' },
    { refId: 'DOC-PARTNER', source: 'work', title: 'Partner note', snippet: 'Current letter pending', url: '/api/evidence/doc?path=work/partner.md', sourceType: 'Proposal workflow · v1 · published 2026-11-09' },
  ],
  answerRefs: ['DOC-AMD2', 'DOC-OUTCOMES'],
  sourceMap: [],
  trace: [],
  mode: 'mock',
  disclaimer: 'Synthetic grant decision support.',
}

describe('FundingAssessmentPanel', () => {
  it('renders the grant decision, funding gap, owners, deadlines and draft boundary', () => {
    const markup = renderToStaticMarkup(<FundingAssessmentPanel result={result} />)
    expect(markup).toContain('FO-2026-117')
    expect(markup).toContain('$2,250,000')
    expect(markup).toContain('$1,800,000')
    expect(markup).toContain('$450,000')
    expect(markup).toContain('TASK-117-PARTNER')
    expect(markup).toContain('Maria Santos')
    expect(markup).toContain('Jordan Lee')
    expect(markup).toContain('America/New_York (EST, UTC-05:00)')
    expect(markup).toContain('Drafted (not submitted)')
    expect(markup).toContain('Not submitted')
    expect(markup).toContain('DOC-AMD2')
    expect(markup).toContain('Why conditional pursuit may be worthwhile')
    expect(markup).toContain('Ordered readiness path')
    expect(markup).toContain('Confirm portal-specific attachments')
  })
})
