import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;
// A date-only value some producers store as an instant: midnight UTC.
const DATE_ONLY_UTC = /^(\d{4})-(\d{2})-(\d{2})T00:00:00(?:\.0+)?(?:Z|\+00:00)$/;

export function formatDate(dateStr: string | null | undefined, locale?: string): string {
  if (!dateStr) return "—";
  try {
    // A calendar date must not move with the timezone. Parsing "1985-03-02" as
    // an instant puts it at UTC midnight, which in any negative-offset zone
    // (e.g. America/Sao_Paulo) renders as the *previous* day — the birth date
    // off-by-one. Build it from its parts instead; a value stored as midnight
    // UTC is treated the same way.
    const m = DATE_ONLY.exec(dateStr) ?? DATE_ONLY_UTC.exec(dateStr);
    if (m) {
      return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).toLocaleDateString(locale);
    }
    return new Date(dateStr).toLocaleDateString(locale);
  } catch {
    return dateStr;
  }
}

/** Whole years between a birth date (a calendar date) and `now` — timezone-proof. */
export function ageFromBirthDate(birthDate: string | null | undefined, now: Date = new Date()): number | null {
  if (!birthDate) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(birthDate);
  if (!m) return null;
  const year = Number(m[1]);
  const month = Number(m[2]) - 1;
  const day = Number(m[3]);
  let age = now.getFullYear() - year;
  if (now.getMonth() < month || (now.getMonth() === month && now.getDate() < day)) age -= 1;
  return age >= 0 ? age : null;
}

export function statusBadgeColor(status: string): string {
  const map: Record<string, string> = {
    active: "bg-green-100 text-green-800",
    completed: "bg-blue-100 text-blue-800",
    stopped: "bg-gray-100 text-gray-800",
    failed: "bg-red-100 text-red-800",
    pending: "bg-yellow-100 text-yellow-800",
    extracted: "bg-purple-100 text-purple-800",
    verified: "bg-green-100 text-green-800",
    resolved: "bg-gray-100 text-gray-800",
    revoked: "bg-red-100 text-red-800",
  };
  return map[status?.toLowerCase()] ?? "bg-gray-100 text-gray-800";
}
