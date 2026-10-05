import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  // de + en + pt; add more later by copying en.json
  locales: ["de", "en", "pt"],
  defaultLocale: "pt",
  localePrefix: "never",
});
