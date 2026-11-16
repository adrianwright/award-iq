import type { Evidence, IQSource, SourceStatus, TraceStep } from './types'

export interface FundingAssessment {
  question: string
  answer: string
  bottomLine: string
  opportunity: {
    id: string
    programId: string
    projectId: string
    title: string
    agency: string
    deadline: string
    deadlineTimezone: string
    asOfDate: string
    eligibleCostBasis: number
    requestedAmount: number
    projectCostBasis: string
  }
  pursuitStatus: string
  recommendation: string
  eligibility: string
  amendmentSummary: string
  matchBasis: string
  matchRequired: number
  matchConfirmed: number
  matchProposed: number
  matchGap: number
  deadlineDays: number
  criteria: Array<{ id: string; text: string; status: 'met' | 'unknown' | 'not_met'; evidenceRefs: string[] }>
  rationale: Array<{ heading: string; text: string; evidenceRefs: string[] }>
  partner: string
  partnerEvidence: string
  tasks: Array<{
    id: string
    text: string
    owner: { id: string; display: string; role: string }
    due: string
    recordedState: string
    dependencyIds: string[]
    evidenceRefs: string[]
    status: string
  }>
  criticalPath: Array<{
    id: string
    order: number
    title: string
    owner: { id: string; display: string; role: string } | null
    due: string | null
    status: string
    dependency: string
    detail: string
    evidenceRefs: string[]
  }>
  executiveReview: string
  legalConstraint: string
  submissionStatus: string
  unknownRequirements: string
  evidence: Evidence[]
  answerRefs: string[]
  sourceMap: Array<{
    source: IQSource
    label: string
    status: SourceStatus
    queries: string[]
    citations: string[]
    summary: string
    retrieving: string
    evidenceCount: number
    evidenceNoun: string
  }>
  trace: TraceStep[]
  mode: 'mock' | 'live'
  disclaimer: string
}

export type FundingSourceProgress = {
  source: IQSource
  label?: string
  status?: SourceStatus
  summary?: string
}
