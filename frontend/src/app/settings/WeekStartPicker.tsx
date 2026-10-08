"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

// First day of the week, stored in a cookie like the language preference so it
// works without a round-trip and applies to every calendar. Monday-first is the
// German default; every other locale expects Sunday first, so the picker writes
// the explicit choice and the calendar page reads it back.
export function WeekStartPicker({ current }: { current: "sunday" | "monday" }) {
  const t = useTranslations("Settings");
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function pick(code: "sunday" | "monday") {
    document.cookie = `WEEK_START=${code}; path=/; max-age=31536000; SameSite=Lax`;
    startTransition(() => router.refresh());
  }

  return (
    <div className="flex flex-wrap gap-2">
      {(["sunday", "monday"] as const).map((code) => (
        <button
          key={code}
          onClick={() => pick(code)}
          disabled={pending}
          className={`px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors disabled:opacity-50
            ${current === code ? "border-primary bg-primary/10 text-primary" : "hover:bg-muted"}`}
        >
          {t(code === "sunday" ? "Sunday" : "Monday")}
        </button>
      ))}
    </div>
  );
}
