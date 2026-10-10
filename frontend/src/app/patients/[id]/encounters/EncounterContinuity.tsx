"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { scheduleFollowUp, createReferral, deleteReferral } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { CalendarClock, Plus, X, Send, Trash2 } from "lucide-react";

const inputCls = "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";
const labelCls = "text-sm font-medium";

const REFERRAL_STATUSES = ["draft", "sent", "completed", "cancelled"] as const;

function statusLabel(status: string): string {
  return `Status${status.charAt(0).toUpperCase()}${status.slice(1)}`;
}

/**
 * WS-10: continuity of care for a single consultation — schedule a return
 * appointment (a linked CalendarEvent) and record referrals (encaminhamento).
 */
export function EncounterContinuity({ patientId, encounter }: { patientId: string; encounter: any }) {
  const t = useTranslations("Enc");
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");

  const [showFollow, setShowFollow] = useState(false);
  const [followDate, setFollowDate] = useState("");
  const [followTitle, setFollowTitle] = useState("");
  const [followPurpose, setFollowPurpose] = useState("");

  const [showReferral, setShowReferral] = useState(false);
  const [specialty, setSpecialty] = useState("");
  const [reason, setReason] = useState("");
  const [refDate, setRefDate] = useState("");

  const followUps: any[] = encounter.follow_ups ?? [];
  const referrals: any[] = encounter.referrals ?? [];

  function submitFollowUp(e: React.FormEvent) {
    e.preventDefault();
    if (!followDate) return;
    setError("");
    startTransition(async () => {
      try {
        await scheduleFollowUp(encounter.id, {
          start_at: followDate,
          title: followTitle.trim() || null,
          purpose: followPurpose.trim() || null,
        });
        setShowFollow(false);
        setFollowDate("");
        setFollowTitle("");
        setFollowPurpose("");
        router.refresh();
      } catch {
        setError(t("FollowUpError"));
      }
    });
  }

  function submitReferral(e: React.FormEvent) {
    e.preventDefault();
    if (!specialty.trim()) return;
    setError("");
    startTransition(async () => {
      try {
        await createReferral(patientId, {
          encounter_id: encounter.id,
          target_specialty: specialty.trim(),
          reason: reason.trim() || null,
          date: refDate || null,
          status: "draft",
        });
        setShowReferral(false);
        setSpecialty("");
        setReason("");
        setRefDate("");
        router.refresh();
      } catch {
        setError(t("ReferralError"));
      }
    });
  }

  function removeReferral(id: string) {
    startTransition(async () => {
      await deleteReferral(id);
      router.refresh();
    });
  }

  return (
    <div className="mt-3 space-y-3 border-t pt-3">
      {error && (
        <div className="rounded-lg bg-destructive/10 text-destructive px-3 py-2 text-xs">{error}</div>
      )}

      {/* Scheduled returns */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <CalendarClock className="h-4 w-4 text-muted-foreground" />
            <span className={labelCls}>{t("FollowUp")}</span>
          </div>
          <button
            type="button"
            onClick={() => setShowFollow((v) => !v)}
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            <Plus className="h-3.5 w-3.5" />
            {t("ScheduleFollowUp")}
          </button>
        </div>

        {followUps.length === 0 && <p className="text-xs text-muted-foreground">{t("FollowUpEmpty")}</p>}
        {followUps.map((f) => (
          <span
            key={f.id}
            className="mr-2 inline-flex items-center gap-1.5 rounded-full bg-cyan-500/10 px-2.5 py-1 text-xs font-medium text-cyan-700 dark:text-cyan-400"
          >
            {t("FollowUpScheduled", { date: formatDate(f.start_at) })}
            {f.title ? ` · ${f.title}` : ""}
          </span>
        ))}

        {showFollow && (
          <form onSubmit={submitFollowUp} className="space-y-2 rounded-lg border bg-muted/30 p-3">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">{t("FollowUpDate")}</label>
                <input
                  type="datetime-local"
                  required
                  value={followDate}
                  onChange={(e) => setFollowDate(e.target.value)}
                  className={inputCls}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">{t("FollowUpTitleLabel")}</label>
                <input
                  value={followTitle}
                  onChange={(e) => setFollowTitle(e.target.value)}
                  placeholder={t("FollowUpTitlePlaceholder")}
                  className={inputCls}
                />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">{t("FollowUpPurpose")}</label>
              <input
                value={followPurpose}
                onChange={(e) => setFollowPurpose(e.target.value)}
                className={inputCls}
              />
            </div>
            <div className="flex items-center gap-2">
              <button
                type="submit"
                disabled={pending}
                className="rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-xs font-medium hover:bg-primary/90 disabled:opacity-50"
              >
                {pending ? t("FollowUpSaving") : t("FollowUpSave")}
              </button>
              <button
                type="button"
                onClick={() => setShowFollow(false)}
                className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-muted"
              >
                {t("Cancel")}
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Referrals */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Send className="h-4 w-4 text-muted-foreground" />
            <span className={labelCls}>{t("Referrals")}</span>
          </div>
          <button
            type="button"
            onClick={() => setShowReferral((v) => !v)}
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            <Plus className="h-3.5 w-3.5" />
            {t("AddReferral")}
          </button>
        </div>

        {referrals.length === 0 && <p className="text-xs text-muted-foreground">{t("ReferralsEmpty")}</p>}
        {referrals.map((r) => (
          <div key={r.id} className="flex items-center justify-between gap-2 rounded-lg border bg-card px-3 py-2">
            <div className="min-w-0">
              <span className="text-sm font-medium">{r.target_specialty}</span>
              <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                {t(statusLabel(r.status))}
              </span>
              {r.date && <span className="ml-2 text-xs text-muted-foreground">{formatDate(r.date)}</span>}
              {r.reason && <div className="truncate text-xs text-muted-foreground">{r.reason}</div>}
            </div>
            <button
              type="button"
              onClick={() => removeReferral(r.id)}
              disabled={pending}
              title={t("ReferralDelete")}
              className="inline-flex shrink-0 items-center justify-center rounded-md border px-2 py-1 text-muted-foreground transition-colors hover:border-destructive hover:text-destructive disabled:opacity-50"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}

        {showReferral && (
          <form onSubmit={submitReferral} className="space-y-2 rounded-lg border bg-muted/30 p-3">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">{t("ReferralSpecialty")}</label>
                <input
                  required
                  value={specialty}
                  onChange={(e) => setSpecialty(e.target.value)}
                  placeholder={t("ReferralSpecialtyPlaceholder")}
                  className={inputCls}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">{t("ReferralDate")}</label>
                <input
                  type="date"
                  value={refDate}
                  onChange={(e) => setRefDate(e.target.value)}
                  className={inputCls}
                />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">{t("ReferralReason")}</label>
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className={inputCls}
              />
            </div>
            <div className="flex items-center gap-2">
              <button
                type="submit"
                disabled={pending}
                className="rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-xs font-medium hover:bg-primary/90 disabled:opacity-50"
              >
                {pending ? t("ReferralSaving") : t("ReferralSave")}
              </button>
              <button
                type="button"
                onClick={() => setShowReferral(false)}
                className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-muted"
              >
                {t("Cancel")}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
