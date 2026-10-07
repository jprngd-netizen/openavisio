"use client";

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";

type Settings = {
  event_reminder: boolean;
  caregiver_added: boolean;
  invitation: boolean;
};

const LABELS: { key: keyof Settings; labelKey: string; hintKey: string }[] = [
  {
    key: "event_reminder",
    labelKey: "NotifyEventReminderLabel",
    hintKey: "NotifyEventReminderHint",
  },
  {
    key: "caregiver_added",
    labelKey: "NotifyCaregiverAddedLabel",
    hintKey: "NotifyCaregiverAddedHint",
  },
  {
    key: "invitation",
    labelKey: "NotifyInvitationLabel",
    hintKey: "NotifyInvitationHint",
  },
];

export function NotificationSettings({ initial }: { initial: Settings }) {
  const t = useTranslations("AdminOrganization");
  const [settings, setSettings] = useState(initial);
  const [pending, startTransition] = useTransition();
  const [saved, setSaved] = useState(false);

  function toggle(key: keyof Settings) {
    const next = { ...settings, [key]: !settings[key] };
    setSettings(next);
    setSaved(false);
    startTransition(async () => {
      await fetch("/api/admin/notification-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [key]: next[key] }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    });
  }

  return (
    <div className="rounded-xl border bg-card p-6 space-y-4">
      <div>
        <h2 className="font-medium text-sm">{t("NotificationsTitle")}</h2>
        <p className="text-xs text-muted-foreground mt-0.5">{t("NotificationsHint")}</p>
      </div>

      <div className="space-y-3">
        {LABELS.map(({ key, labelKey, hintKey }) => (
          <div key={key} className="flex items-start justify-between gap-4">
            <div>
              <div className="text-sm font-medium">{t(labelKey)}</div>
              <div className="text-xs text-muted-foreground">{t(hintKey)}</div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={settings[key]}
              onClick={() => toggle(key)}
              disabled={pending}
              className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors disabled:opacity-50 ${
                settings[key] ? "bg-primary" : "bg-muted"
              }`}
            >
              <span
                className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${
                  settings[key] ? "translate-x-4" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        ))}
      </div>

      {saved && <p className="text-xs text-green-600">{t("Saved")}</p>}
    </div>
  );
}