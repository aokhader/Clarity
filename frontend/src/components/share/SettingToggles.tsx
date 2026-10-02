import type { ShareSetting, ShareSettings } from '@/api/types'
import { SHARE_SETTING_OPTIONS } from '@/components/share/shareSettings'

type SettingTogglesProps = {
  settings: ShareSettings
  onChange: (setting: ShareSetting, on: boolean) => void
}

export function SettingToggles({ settings, onChange }: SettingTogglesProps) {
  return (
    <fieldset className="space-y-2">
      <legend className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Sections</legend>
      {SHARE_SETTING_OPTIONS.map(({ setting, label, detail }) => (
        <label key={setting} className="flex cursor-pointer items-start gap-3 rounded-md px-1 py-1 hover:bg-muted">
          <input
            type="checkbox"
            className="mt-0.5 size-4 accent-primary"
            checked={settings[setting]}
            onChange={(event) => onChange(setting, event.target.checked)}
          />
          <span className="text-sm">
            <span className={settings[setting] ? 'font-medium' : 'text-muted-foreground'}>{label}</span>
            <span className="block text-xs text-muted-foreground">{detail}</span>
          </span>
        </label>
      ))}
    </fieldset>
  )
}
