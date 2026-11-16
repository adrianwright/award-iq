import type { Evidence, IQSource, SourceStatus, TraceStep } from './types'

export interface FundingAssessment {
  question: string
  answer: string
  bottomLine: string
  opportunity: { id: string; title: string; agency: string; deadline: string; asOfDate: string }
  pursuitStatus: string
  recommendation: string
  eligibility: string
  matchBasis: string
  matchRequired: number
  matchConfirmed: number
  matchProposed: number
  matchGap: number
  deadlineDays: number
  criteria: Array<{ text: string; status: 'met' | 'uncertain' | 'not_met'; evidenceRefs: string[] }>
  partner: string
  partnerEvidence: string
  tasks: Array<{
    id: string
    text: string
    owner: { id: string; display: string; role: string }
    due: string
    status: string
  }>
  executiveReview: string
  legalConstraint: string
  submissionStatus: string
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
