import type { ShareSetting, ShareSettings } from '@/api/types'

/** Mirrors the defaults of `ShareSettings` in backend/app/schemas.py. */
export const DEFAULT_SHARE_SETTINGS: ShareSettings = {
  case_stage: true,
  coverage_exists: true,
  coverage_limits: false,
  own_bills: true,
  own_records: true,
  requests: true,
  treatment_activity: false,
}

/** The composer's toggles, in the order the provider page shows the sections. */
export const SHARE_SETTING_OPTIONS: { setting: ShareSetting; label: string; detail: string }[] = [
  { setting: 'case_stage', label: 'Case status', detail: 'Stage, neutral status updates, and whether the case is open' },
  { setting: 'coverage_exists', label: 'Coverage confirmed', detail: 'Yes or no only: no carrier, no amounts' },
  { setting: 'coverage_limits', label: 'Policy limits', detail: "The defendant's liability limits only, per person and per occurrence" },
  { setting: 'requests', label: 'What the firm needs', detail: 'Open record requests and tasks for this office' },
  { setting: 'own_bills', label: 'Their bills and liens', detail: 'With the cited page of each' },
  { setting: 'own_records', label: 'Their records on file', detail: 'With the cited page of each' },
  { setting: 'treatment_activity', label: 'Treatment activity', detail: 'Month of the latest visit, no provider named' },
]

export const SETTING_LABELS = Object.fromEntries(
  SHARE_SETTING_OPTIONS.map((option) => [option.setting, option.label]),
) as Record<ShareSetting, string>
