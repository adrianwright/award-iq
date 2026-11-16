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
    title: 'Community Resilience Infrastructure Grant',
    agency: 'Federal Resilience Agency',
    deadline: '2026-12-16',
    asOfDate: '2026-11-16',
  },
  pursuitStatus: 'Pursue - pending',
  recommendation: 'Continue conditionally.',
  eligibility: 'Conditional / unresolved evidence',
  matchBasis: '25% of total eligible project costs',
  matchRequired: 2250000,
  matchConfirmed: 1800000,
  matchProposed: 450000,
  matchGap: 450000,
  deadlineDays: 30,
  criteria: [{ text: 'Regional partner letter', status: 'uncertain', evidenceRefs: ['r1'] }],
  partner: 'Regional Transit Authority',
  partnerEvidence: '2024 letter is a lead only.',
  tasks: [
    { id: 'TASK-117-MATCH', text: 'Confirm capital reserve.', owner: { id: 'FIN-02', display: 'Maria Santos', role: 'Finance' }, due: '2026-11-18', status: 'Drafted (not submitted)' },
    { id: 'TASK-117-PARTNER', text: 'Request current letter.', owner: { id: 'PM-01', display: 'Jordan Lee', role: 'Proposal Manager' }, due: '2026-11-20', status: 'Drafted (not submitted)' },
  ],
  executiveReview: '2026-11-19, 10:00-11:00 America/Los_Angeles (PST, UTC-08:00)',
  legalConstraint: 'Sam Patel unavailable 2026-11-23 through 2026-11-27; finish by 2026-11-20.',
  submissionStatus: 'Not submitted',
  evidence: [],
  answerRefs: [],
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
    expect(markup).toContain('PST, UTC-08:00')
    expect(markup).toContain('Drafted (not submitted)')
    expect(markup).toContain('Not submitted')
  })
})
