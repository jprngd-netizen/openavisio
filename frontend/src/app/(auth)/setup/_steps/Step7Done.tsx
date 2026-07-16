"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";

export function Step7Done() {
  const t = useTranslations("Setup");
  const router = useRouter();

  function goToLogin() {
    document.cookie = "setup_complete=1; path=/; max-age=2147483647; SameSite=Lax";
    router.push("/login");
  }

  return (
    <div className="py-8 text-center space-y-4">
      <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto text-3xl">
        ✓
      </div>
      <h2 className="text-xl font-semibold">{t("DoneTitle")}</h2>
      <p className="text-sm text-muted-foreground">{t("DoneBody")}</p>
      <button
        type="button"
        onClick={goToLogin}
        className="mt-2 px-6 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
      >
        {t("GoToLogin")}
      </button>
    </div>
  );
}
