"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";

// Compact UI-language switcher. Writes the NEXT_LOCALE cookie (the same
// mechanism the Settings picker and the setup wizard use) and refreshes so the
// server re-resolves the locale. Used in the sidebar footer and the mobile
// "More" sheet, which previously had no way to change language at all.
const LANGS = [
  { code: "pt", label: "Português" },
  { code: "en", label: "English" },
  { code: "de", label: "Deutsch" },
];

export function LocaleSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function pick(code: string) {
    document.cookie = `NEXT_LOCALE=${code}; path=/; max-age=31536000; SameSite=Lax`;
    startTransition(() => router.refresh());
  }

  return (
    <div className="flex items-center gap-1" role="group" aria-label="Language">
      {LANGS.map((l) => (
        <button
          key={l.code}
          type="button"
          onClick={() => pick(l.code)}
          disabled={pending}
          aria-label={l.label}
          aria-pressed={locale === l.code}
          className={`rounded px-2 py-1 text-xs font-medium uppercase transition-colors disabled:opacity-50 ${
            locale === l.code
              ? "bg-primary/10 text-primary"
              : "text-muted-foreground hover:bg-muted hover:text-foreground"
          }`}
        >
          {l.code}
        </button>
      ))}
    </div>
  );
}