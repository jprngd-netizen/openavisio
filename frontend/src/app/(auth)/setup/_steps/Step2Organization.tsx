"use client";

import { useTranslations } from "next-intl";
import { WizardState } from "../_hooks/useWizardState";

interface Props {
  state: WizardState;
  onChange: (org: Partial<WizardState["org"]>) => void;
}

export function Step2Organization({ state, onChange }: Props) {
  const t = useTranslations("Setup");
  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <label className="text-sm font-medium">{t("OrgName")} *</label>
        <input
          type="text"
          required
          value={state.org.name}
          onChange={(e) => onChange({ name: e.target.value })}
          className="w-full rounded-lg border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">{t("OrgDescription")}</label>
        <textarea
          rows={3}
          value={state.org.description}
          onChange={(e) => onChange({ description: e.target.value })}
          className="w-full rounded-lg border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary resize-none"
        />
      </div>
    </div>
  );
}
