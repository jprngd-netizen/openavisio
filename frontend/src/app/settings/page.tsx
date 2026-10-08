import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { getLocale, getTranslations } from "next-intl/server";
import { cookies } from "next/headers";
import { getMe, getMyPasskeys } from "@/lib/api";
import { PasswordForm } from "./PasswordForm";
import { ProfileForm } from "./ProfileForm";
import { LanguagePicker } from "./LanguagePicker";
import { WeekStartPicker } from "./WeekStartPicker";
import { PasskeysSection } from "./PasskeysSection";
import { formatDate } from "@/lib/utils";

const ROLE_KEYS: Record<string, string> = {
  admin: "RoleAdmin",
  manager: "RoleManager",
  user: "RoleUser",
};

export default async function SettingsPage() {
  const [session, locale, profile, cookieStore, passkeys] = await Promise.all([
    auth(),
    getLocale(),
    getMe().catch(() => null),
    cookies(),
    getMyPasskeys().catch(() => []),
  ]);
  const t = await getTranslations("Settings");
  const isSystem = !cookieStore.has("NEXT_LOCALE");
  const weekStart = cookieStore.get("WEEK_START")?.value === "monday" ? "monday" : "sunday";
  const user = session?.user as any;
  const roleLabel = ROLE_KEYS[user?.role]
    ? t(ROLE_KEYS[user?.role] as any)
    : user?.role ?? "—";

  return (
    <AppLayout>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("Title")}</h1>
        <p className="text-sm text-muted-foreground mt-1">{t("Subtitle")}</p>
      </div>

      {/* Account info */}
      <div className="rounded-xl border bg-card p-6 max-w-lg space-y-3">
        <h2 className="font-medium text-sm">{t("Account")}</h2>
        <dl className="grid grid-cols-[120px_1fr] gap-y-2 text-sm">
          <dt className="text-muted-foreground">{t("Email")}</dt>
          <dd className="font-medium">{user?.email ?? "—"}</dd>
          <dt className="text-muted-foreground">{t("Role")}</dt>
          <dd>
            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary">
              {roleLabel}
            </span>
          </dd>
          {profile?.last_login_at && (
            <>
              <dt className="text-muted-foreground">{t("LastLogin")}</dt>
              <dd className="text-muted-foreground text-xs">{formatDate(profile.last_login_at)}</dd>
            </>
          )}
        </dl>
      </div>

      {/* Profile */}
      <div className="rounded-xl border bg-card p-6 max-w-lg space-y-4">
        <div>
          <h2 className="font-medium text-sm">{t("Profile")}</h2>
          <p className="text-xs text-muted-foreground mt-0.5">{t("ProfileSubtitle")}</p>
        </div>
        <ProfileForm
          initialFirstName={profile?.first_name ?? null}
          initialLastName={profile?.last_name ?? null}
        />
      </div>

      {/* Language */}
      <div className="rounded-xl border bg-card p-6 max-w-lg space-y-3">
        <div>
          <h2 className="font-medium text-sm">{t("Language")}</h2>
          <p className="text-xs text-muted-foreground mt-0.5">{t("LanguageSubtitle")}</p>
        </div>
        <LanguagePicker current={locale} isSystem={isSystem} />
      </div>

      {/* First day of the week (calendar) */}
      <div className="rounded-xl border bg-card p-6 max-w-lg space-y-3">
        <div>
          <h2 className="font-medium text-sm">{t("WeekStart")}</h2>
          <p className="text-xs text-muted-foreground mt-0.5">{t("WeekStartSubtitle")}</p>
        </div>
        <WeekStartPicker current={weekStart} />
      </div>

      {/* Security */}
      <div className="rounded-xl border bg-card p-6 max-w-lg space-y-4">
        <div>
          <h2 className="font-medium text-sm">{t("Security")}</h2>
          <p className="text-xs text-muted-foreground mt-0.5">{t("SecuritySubtitle")}</p>
        </div>
        <PasswordForm />
      </div>

      {/* Passkeys */}
      <div className="rounded-xl border bg-card p-6 max-w-lg space-y-4">
        <div>
          <h2 className="font-medium text-sm">{t("Passkeys")}</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {t("PasskeysSubtitle")}
          </p>
        </div>
        <PasskeysSection initialPasskeys={passkeys} />
      </div>
    </AppLayout>
  );
}
