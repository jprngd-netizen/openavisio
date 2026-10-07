import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { getTranslations, getLocale } from "next-intl/server";
import { getOrganization } from "@/lib/api";
import { OperatorDetails, type Operator } from "@/components/OperatorDetails";

export const dynamic = "force-dynamic";

export default async function PrivacyPage() {
  // The controller is the OPERATOR of this instance, so the details come from the
  // database. They used to be `[ORGANISATIONS-NAME]` placeholders shipped to
  // production — a notice that looks legal and is not (#112).
  const t = await getTranslations("Legal");
  const locale = await getLocale();
  const authorityUrl =
    locale === "de"
      ? "https://www.baden-wuerttemberg.datenschutz.de"
      : "https://www.gov.br/anpd";

  let org: Operator = {};
  try {
    org = await getOrganization();
  } catch {}

  return (
    <div className="min-h-screen bg-muted/40 py-12 px-4">
      <div className="max-w-3xl mx-auto bg-card rounded-xl shadow-sm border p-8 space-y-8">
        <div className="mb-2">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground hover:underline"
          >
            <ArrowLeft className="size-4" />
            {t("PrivacyBack")}
          </Link>
        </div>

        <div>
          <h1 className="text-2xl font-bold mb-1">{t("PrivacyTitle")}</h1>
          <p className="text-sm text-muted-foreground">
            {t("PrivacySubtitleBefore")} ·{" "}
            <Link href="/imprint" className="underline hover:text-foreground">
              {t("PrivacyImprintLinkText")}
            </Link>
          </p>
        </div>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{t("PrivacyS1Heading")}</h2>
          <p className="text-sm text-muted-foreground leading-relaxed">{t("PrivacyS1Body")}</p>
          <OperatorDetails
            operator={org}
            missingLabel={t("ImprintMissingLabel")}
            missingCta={t("ImprintMissingCta")}
          />
          {org.dpo_contact && (
            <p className="text-sm text-muted-foreground">
              <span className="font-medium">{t("PrivacyDpoLabel")}:</span> {org.dpo_contact}
            </p>
          )}
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{t("PrivacyS2Heading")}</h2>
          <p className="text-sm leading-relaxed">{t("PrivacyS2Body")}</p>
          <ul className="text-sm space-y-2 list-disc list-inside text-muted-foreground">
            <li><strong>{t("PrivacyS2Item1Title")}</strong> — {t("PrivacyS2Item1Body")}</li>
            <li><strong>{t("PrivacyS2Item2Title")}</strong> — {t("PrivacyS2Item2Body")}</li>
            <li><strong>{t("PrivacyS2Item3Title")}</strong> — {t("PrivacyS2Item3Body")}</li>
            <li><strong>{t("PrivacyS2Item4Title")}</strong> — {t("PrivacyS2Item4Body")}</li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{t("PrivacyS3Heading")}</h2>
          <ul className="text-sm space-y-1 list-disc list-inside text-muted-foreground">
            <li>{t("PrivacyS3Item1")}</li>
            <li>{t("PrivacyS3Item2")}</li>
            <li>{t("PrivacyS3Item3")}</li>
            <li>{t("PrivacyS3Item4")}</li>
            <li>{t("PrivacyS3Item5")}</li>
            <li>{t("PrivacyS3Item6")}</li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{t("PrivacyS4Heading")}</h2>
          <p className="text-sm leading-relaxed text-muted-foreground">{t("PrivacyS4Body")}</p>
          <ul className="text-sm space-y-1 list-disc list-inside text-muted-foreground">
            <li>{t("PrivacyS4Item1")}</li>
            <li>{t.rich("PrivacyS4Item2", { code: (chunks) => <code>{chunks}</code> })}</li>
          </ul>
        </section>

        <section className="space-y-3">
          {process.env.UMAMI_URL && (
            <>
              <h2 className="text-lg font-semibold">{t("PrivacyUmamiHeading")}</h2>
              <p>{t("PrivacyUmamiBody", { url: process.env.UMAMI_URL?.replace("https://", "") })}</p>
            </>
          )}

          <h2 className="text-lg font-semibold">{t("PrivacyS5Heading")}</h2>
          <ul className="text-sm space-y-1 list-disc list-inside text-muted-foreground">
            <li>{t("PrivacyS5Item1")}</li>
            <li>{t("PrivacyS5Item2")}</li>
            <li>{t("PrivacyS5Item3")}</li>
            <li>{t("PrivacyS5Item4")}</li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{t("PrivacyS6Heading")}</h2>
          <p className="text-sm text-muted-foreground leading-relaxed">{t("PrivacyS6Body")}</p>
          <ul className="text-sm space-y-2 list-disc list-inside text-muted-foreground">
            <li><strong>{t("PrivacyS6Item1Title")}</strong> — {t("PrivacyS6Item1Body")}</li>
            <li><strong>{t("PrivacyS6Item2Title")}</strong> — {t("PrivacyS6Item2Body")}</li>
            <li><strong>{t("PrivacyS6Item3Title")}</strong> — {t("PrivacyS6Item3Body")}</li>
            <li><strong>{t("PrivacyS6Item4Title")}</strong> — {t("PrivacyS6Item4Body")}</li>
            <li><strong>{t("PrivacyS6Item5Title")}</strong> — {t("PrivacyS6Item5Body")}</li>
            <li><strong>{t("PrivacyS6Item6Title")}</strong> — {t("PrivacyS6Item6Body")}</li>
          </ul>
          <p className="text-sm text-muted-foreground">
            {t("PrivacyS6ContactBefore")}{" "}
            <strong>{t("PrivacyS6ContactEmailPlaceholder")}</strong>
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{t("PrivacyS7Heading")}</h2>
          <p className="text-sm leading-relaxed text-muted-foreground">{t("PrivacyS7Body")}</p>
          <div className="text-sm text-muted-foreground">
            <p className="font-medium">{t("PrivacyS7AuthorityName")}</p>
            <p>{t("PrivacyS7AuthorityAddress")}</p>
            {t("PrivacyS7AuthorityPhone") && <p>{t("PrivacyS7AuthorityPhone")}</p>}
            <p>
              Website:{" "}
              <a
                href={authorityUrl}
                className="underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                {t("PrivacyS7AuthorityWebsite")}
              </a>
            </p>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{t("PrivacyS8Heading")}</h2>
          <p className="text-sm leading-relaxed text-muted-foreground">{t("PrivacyS8Body")}</p>
        </section>

        <div className="pt-4 border-t text-xs text-muted-foreground">
          {t("PrivacyFooterBefore")} <strong>{t("PrivacyFooterDomain")}</strong>.{" "}
          {t("PrivacyFooterAfter")}
        </div>
      </div>
    </div>
  );
}