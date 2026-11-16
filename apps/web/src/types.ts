export type IQSource = 'foundry' | 'fabric' | 'work' | 'web'

export type SourceStatus =
  | 'idle'
  | 'queued'
  | 'searching'
  | 'retrieved'
  | 'needs_review'
  | 'complete'
  | 'failed'
  | 'skipped'

export type TraceStatus = 'completed' | 'in_progress' | 'pending' | 'queued'

export type FabricState = 'Active' | 'Paused' | 'Pausing' | 'Resuming' | 'Unknown'

export interface FabricStatus {
  state: FabricState
  capacityName: string
  portalUrl: string
  detail?: string | null
}

export interface Evidence {
  refId: string
  source: IQSource
  title: string
  snippet: string
  url: string | null
  sourceType: string
}

export interface TraceStep {
  step: string
  source?: IQSource
  detail: string
  ts: number
  status?: TraceStatus
}
