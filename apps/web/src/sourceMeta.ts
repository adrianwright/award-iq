import { BrainCircuit, Database, Globe, Users, type LucideIcon } from 'lucide-react'
import type { IQSource, SourceStatus } from './types'

export const sourceLabels: Record<IQSource, string> = {
  foundry: 'Foundry IQ',
  fabric: 'Fabric IQ',
  work: 'Work IQ',
  web: 'Web IQ',
}

export const sourceIcon: Record<IQSource, LucideIcon> = {
  foundry: BrainCircuit,
  fabric: Database,
  work: Users,
  web: Globe,
}

export const sourceOrder: IQSource[] = ['foundry', 'fabric', 'work', 'web']

export function sourceClass(source: IQSource): string {
  return `source-${source}`
}

export const statusLabels: Record<SourceStatus, string> = {
  idle: 'Idle',
  queued: 'Queued',
  searching: 'Searching',
  retrieved: 'Retrieved',
  needs_review: 'Needs review',
  complete: 'Complete',
  failed: 'Failed',
  skipped: 'Skipped',
}

export function statusLabel(status: SourceStatus): string {
  return statusLabels[status] ?? status
}

