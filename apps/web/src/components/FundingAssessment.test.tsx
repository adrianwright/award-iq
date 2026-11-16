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
  it('leads with the decision and one action table, retaining details behind closed disclosures', () => {
    const markup = renderToStaticMarkup(<FundingAssessmentPanel result={result} />)
    const visible = markup.replace(/<details\b[\s\S]*?<\/details>/g, '')
    expect(visible).toContain('Pursue - pending; resolve the match and partner conditions.')
    expect(visible).toContain('Current grant scenario.')
    expect(visible).toContain('$2,250,000')
    expect(visible).toContain('$1,800,000')
    expect(visible).toContain('$450,000')
    expect(visible).toContain('Maria Santos')
    expect(visible).toContain('Nov 18, 2026')
    expect(visible).toContain('Not submitted')
    expect(visible).toContain('Nothing booked or submitted')
    expect(visible).toContain('Regional partner letter')
    expect(visible).toContain('Confirm portal-specific attachments')
    expect(visible).not.toContain('Continue conditionally.')
    expect(visible).not.toContain('Program and community alignment.')
    expect(visible).not.toContain('Confirm then document the source.')
    expect(markup.match(/<table>/g)).toHaveLength(1)
    expect(markup).not.toMatch(/<details[^>]*\bopen(?:=|\s|>)/)
    expect(markup).not.toContain('TASK-117-PARTNER')
    expect(markup).toContain('America/New_York (EST, UTC-05:00)')
    expect(markup).toContain('Confirm then document the source.')
    expect(markup).not.toContain('Synthetic program evidence')
    expect(visible.replace(/<[^>]*>/g, ' ').trim().split(/\s+/).length).toBeLessThan(400)
  })

  it('renders generated narrative with numbered source links, not document IDs or raw retrieval', () => {
    const markup = renderToStaticMarkup(<FundingAssessmentPanel result={{
      ...result,
      answer: 'The current amendment requires a partner letter [DOC-AMD2].\n\nCoordination remains open [DOC-PARTNER].',
      rationale: [{ heading: 'Live Work IQ coordination context', text: '{"author":"private@example.com"}', evidenceRefs: ['DOC-PARTNER'] }],
    }} />)
    expect(markup).toContain('Source 1: Amendment 2')
    expect(markup).toContain('Source 4: Partner note')
    expect(markup).toContain('[1]</a>')
    expect(markup).toContain('[4]</a>')
    expect(markup).toContain('href="/api/evidence/doc?path=work/partner.md"')
    expect(markup).not.toContain('DOC-AMD2')
    expect(markup).not.toContain('Live Work IQ coordination context')
    expect(markup).not.toContain('private@example.com')
    expect(markup).not.toContain('Proposal workflow')
  })

  it('keeps failed eligibility visible and uses the selected opportunity rather than a canned pursuit answer', () => {
    const markup = renderToStaticMarkup(<FundingAssessmentPanel result={{
      ...result,
      pursuitStatus: 'Do not pursue',
      eligibility: 'Not eligible',
      bottomLine: 'The applicant type is not eligible.',
      answer: 'Do not pursue: the applicant type fails the current rule. Match gap is $0 [DOC-AMD2].',
      matchGap: 0,
      criteria: [{ id: 'applicant-type', text: 'Public-sector applicant required', status: 'not_met', evidenceRefs: ['DOC-AMD2'] }],
      criticalPath: [{ ...result.criticalPath[0], title: 'Review the failed criterion', owner: null, due: null }],
    }} />)
    const visible = markup.replace(/<details\b[\s\S]*?<\/details>/g, '')
    expect(visible).toContain('Not met')
    expect(visible).toContain('Public-sector applicant required')
    expect(visible).toContain('Review the failed criterion')
    expect(visible).toContain('Not assigned')
    expect(visible).toContain('Not set')
    expect(visible).not.toContain('Pursue - pending')
    expect(visible).not.toContain('Confirm match')
  })
})
