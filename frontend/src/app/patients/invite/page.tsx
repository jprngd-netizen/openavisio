import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { AcceptButton } from "./AcceptButton";
import { UserCheck } from "lucide-react";
import { getTranslations } from "next-intl/server";

const API = process.env.API_URL || "http://localhost:8000";

async function getInviteInfo(token: string) {
  const res = await fetch(`${API}/api/patients/caregiver-invite/info?token=${encodeURIComponent(token)}`, {
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}

export default async function CaregiverInvitePage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const t = await getTranslations("Access");
  const { token } = await searchParams;
  const session = await auth();

  if (!token) {
    return (
      <AppLayout>
        <div className="max-w-md mx-auto mt-16 text-center">
          <p className="text-muted-foreground">{t("InvalidInviteLink")}</p>
        </div>
      </AppLayout>
    );
  }

  const info = await getInviteInfo(token);

  return (
    <AppLayout>
      <div className="max-w-md mx-auto mt-16">
        <div className="rounded-xl border bg-card p-8 text-center space-y-6">
          <div className="flex justify-center">
            <div className="rounded-full bg-primary/10 p-4">
              <UserCheck className="size-8 text-primary" />
            </div>
          </div>

          {info ? (
            <>
              <div className="space-y-1">
                <p className="text-muted-foreground text-sm">
                  {t("InvitedBy", { org: info.org_name })}
                </p>
                <h1 className="text-2xl font-bold">
                  {info.patient_given_name} {info.patient_family_name}
                </h1>
                <p className="text-sm text-muted-foreground">
                  {t("AccessLevelLabel")}{" "}
                  <span className="font-medium capitalize">{info.access_level}</span>
                </p>
              </div>

              {session ? (
                <AcceptButton inviteToken={token} />
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">
                    {t("SignInPrompt")}
                  </p>
                  <a
                    href={`/login?callbackUrl=${encodeURIComponent(`/patients/invite?token=${token}`)}`}
                    className="inline-block rounded-lg bg-primary text-primary-foreground px-6 py-2.5 text-sm font-medium hover:bg-primary/90"
                  >
                    {t("SignIn")}
                  </a>
                </div>
              )}
            </>
          ) : (
            <div className="space-y-2">
              <h1 className="text-xl font-bold">{t("InvalidOrExpiredInvite")}</h1>
              <p className="text-muted-foreground text-sm">
                {t("InviteLinkInvalid")}
              </p>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}