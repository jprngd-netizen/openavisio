"use client";

import { useState, useEffect } from "react";
import Script from "next/script";
import { useTranslations } from "next-intl";
import { getMemedSession, capturePrescription, markPrescriptionDeleted } from "@/lib/api";

// ── Memed postMessage origin validation ──────────────────────────────────
// Config-driven allowlist for iframe origins. In homolog/dev, set
// NEXT_PUBLIC_MEMED_ALLOWED_ORIGINS to the known iframe origin(s).
// Enforcement is opt-in: by default, unknown origins are logged but NOT blocked.
const MEMED_ALLOWED_ORIGINS = (process.env.NEXT_PUBLIC_MEMED_ALLOWED_ORIGINS || "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);
const MEMED_ENFORCE_ORIGIN =
  process.env.NEXT_PUBLIC_MEMED_ENFORCE_ORIGIN === "true";

declare const MdHub:
  | {
      command: { send: (module: string, command: string, ...args: unknown[]) => void };
      event: { add: (event: string, handler: (...args: unknown[]) => void) => void };
    }
  | undefined;

interface MemedSession {
  data_token: string;
  script_url: string;
  patient: Record<string, unknown>;
}

export function MemedEmbed({ prescriptionId }: { prescriptionId: string }) {
  const t = useTranslations("Prescriptions");
  const [session, setSession] = useState<MemedSession | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  // Fetch the Memed session (token, script URL, patient data) on mount
  useEffect(() => {
    let cancelled = false;
    getMemedSession(prescriptionId)
      .then((s: MemedSession) => {
        if (!cancelled) {
          setSession(s);
          setState("ready");
        }
      })
      .catch((e: Error) => {
        if (!cancelled) {
          setError(e.message ?? t("MemedLoadError"));
          setState("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [prescriptionId]);

  // Set up the postMessage bridge for Memed events
  useEffect(() => {
    const s = session;
    if (!s) return;
    const patient = s.patient;

    let eventsRegistered = false;

    function handleMessage(event: MessageEvent) {
      const data = event.data;
      if (!data || typeof data !== "object") return;

      // Origin validation: allowlist check with log-only default
      const origin = event.origin;
      if (
        origin &&
        MEMED_ALLOWED_ORIGINS.length > 0 &&
        !MEMED_ALLOWED_ORIGINS.includes(origin)
      ) {
        console.log(
          `[MemedEmbed] Ignoring message from unknown origin: ${origin}`,
        );
        if (MEMED_ENFORCE_ORIGIN) {
          return; // Blocked — origin not in allowlist and enforcement is on
        }
      }

      const type = (data as Record<string, unknown>).type;

      if (type === "core:moduleInit") {
        const mod = (data as Record<string, unknown>).module as
          | Record<string, unknown>
          | undefined;
        if (mod && mod.name === "plataforma.prescricao") {
          // Send patient data to the module
          try {
            MdHub?.command.send("plataforma.prescricao", "setPaciente", patient);
          } catch {
            // Non-fatal
          }

          // setWorkplace is best-effort — not in the verified reference list
          try {
            MdHub?.command.send("plataforma.prescricao", "setWorkplace", {});
          } catch {
            // Non-fatal
          }

          // Register event handlers once
          if (!eventsRegistered) {
            eventsRegistered = true;
            try {
              MdHub?.event.add("prescricaoImpressa", (payload: unknown) => {
                capturePrescription(prescriptionId, payload).catch(() => {});
              });
            } catch {
              // Non-fatal
            }
            try {
              MdHub?.event.add("prescricaoExcluida", (payload: unknown) => {
                markPrescriptionDeleted(prescriptionId, payload).catch(() => {});
              });
            } catch {
              // Non-fatal
            }
          }

          // Open the module
          try {
            MdHub?.command.send("plataforma.prescricao", "show");
          } catch {
            // Non-fatal
          }
        }
      }
    }

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [session, prescriptionId]);

  if (state === "loading") {
    return <div className="text-center py-8 text-muted-foreground">{t("MemedLoading")}</div>;
  }

  if (state === "error" || !session) {
    return (
      <div className="rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
        {error ?? t("MemedLoadError")}
      </div>
    );
  }

  return (
    <>
      <p className="mb-2 text-xs text-muted-foreground">{t("MemedInteractionsNote")}</p>
      <Script
        src={session.script_url}
        data-token={session.data_token}
        data-container="memed-container"
        strategy="afterInteractive"
      />
      <div id="memed-container" className="min-h-[600px] rounded-xl border bg-card" />
    </>
  );
}