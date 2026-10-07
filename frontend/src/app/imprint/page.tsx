import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { getOrganization } from "@/lib/api";
import { OperatorDetails, hasOperatorDetails, type Operator } from "@/components/OperatorDetails";

export const dynamic = "force-dynamic";

// §5 DDG makes this mandatory for a German operator, and the app had none.
// The details belong to whoever RUNS the instance — a household, a Verein, a
// care organisation — so they come from the database, not from this repository.
export default async function ImprintPage() {
  const t = await getTranslations("Legal");

  let org: Operator & { name?: string } = {};
  try {
    org = await getOrganization();
  } catch {}

  const complete = hasOperatorDetails(org);

  return (
    <div className="min-h-screen bg-muted/40 py-12 px-4">
      <div className="mx-auto max-w-3xl space-y-8 rounded-xl border bg-card p-8 shadow-sm">
        <div className="mb-2">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground hover:underline"
          >
            <ArrowLeft className="size-4" />
            {t("ImprintBack")}
          </Link>
        </div>

        <div>
          <h1 className="mb-1 text-2xl font-bold">{t("ImprintTitle")}</h1>
          <p className="text-sm text-muted-foreground">{t("ImprintSubtitle")}</p>
        </div>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{t("ImprintOperatorHeading")}</h2>
          <OperatorDetails
            operator={org}
            missingLabel={t("ImprintMissingLabel")}
            missingCta={t("ImprintMissingCta")}
          />
        </section>

        {complete && (
          <>
            {org.legal_responsible && (
              <section className="space-y-2">
                <h2 className="text-lg font-semibold">{t("ImprintResponsibleHeading")}</h2>
                <p className="text-sm text-muted-foreground">{org.legal_responsible}</p>
              </section>
            )}

            {(org.legal_register || org.legal_vat_id) && (
              <section className="space-y-2">
                <h2 className="text-lg font-semibold">{t("ImprintRegisterHeading")}</h2>
                {org.legal_register && (
                  <p className="text-sm text-muted-foreground">{org.legal_register}</p>
                )}
                {org.legal_vat_id && (
                  <p className="text-sm text-muted-foreground">
                    {t("ImprintVatLabel")}: {org.legal_vat_id}
                  </p>
                )}
              </section>
            )}
          </>
        )}

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">{t("ImprintSoftwareHeading")}</h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {t("ImprintSoftwareBody")}
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold">{t("ImprintPrivacyHeading")}</h2>
          <p className="text-sm text-muted-foreground">
            {t("ImprintPrivacyBodyBefore")}{" "}
            <Link href="/privacy" className="underline">
              {t("ImprintPrivacyLinkText")}
            </Link>
            {t("ImprintPrivacyBodyAfter")}
          </p>
        </section>
      </div>
    </div>
  );
}