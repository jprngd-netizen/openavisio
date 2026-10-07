"use server";

import { getTranslations } from "next-intl/server";

const API = process.env.API_URL || "http://localhost:8000";

export async function registerAction(
  token: string,
  firstName: string,
  lastName: string,
  password: string,
  consent: boolean
): Promise<{ error?: string }> {
  const t = await getTranslations("Auth");
  let res: Response;
  try {
    res = await fetch(`${API}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token,
        first_name: firstName,
        last_name: lastName,
        password,
        consent,
      }),
    });
  } catch {
    return { error: t("CouldNotReachServer") };
  }

  if (res.status === 201) return {};
  if (res.status === 409) return { error: t("AccountExists") };
  if (res.status === 422) return { error: t("ConsentRequiredServer") };
  if (res.status === 400) {
    const data = await res.json().catch(() => ({}));
    const detail: string = data?.detail ?? "";
    if (detail.toLowerCase().includes("expired")) return { error: t("InvitationExpiredServer") };
    return { error: t("InvalidInvitationLink") };
  }
  return { error: t("SomethingWentWrong") };
}
