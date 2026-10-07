"use server";

import { auth } from "@/auth";
import { updateMe } from "@/lib/api";
import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { verifyChallenge } from "@/lib/passkey-challenge";
import { getTranslations } from "next-intl/server";

const API = process.env.API_URL || "http://localhost:8000";

export async function updateProfileAction(
  firstName: string,
  lastName: string
): Promise<{ error?: string }> {
  const t = await getTranslations("Settings");
  try {
    await updateMe({ first_name: firstName || undefined, last_name: lastName || undefined });
    revalidatePath("/settings");
    return {};
  } catch {
    return { error: t("CouldNotSaveProfile") };
  }
}

export async function changePasswordAction(
  currentPassword: string,
  newPassword: string
): Promise<{ error?: string }> {
  const t = await getTranslations("Settings");
  const session = await auth();
  const token = (session as any)?.accessToken as string | undefined;

  if (!token) {
    return { error: t("SessionExpired") };
  }

  let res: Response;
  try {
    res = await fetch(
      `${process.env.API_URL || "http://localhost:8000"}/api/auth/me/password`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      }
    );
  } catch {
    return { error: t("CouldNotReachServer") };
  }

  if (res.status === 204) return {};

  if (res.status === 400) {
    return { error: t("CurrentPasswordIncorrect") };
  }

  return { error: t("SomethingWentWrong") };
}

export async function registerPasskeyAction(
  credential: unknown,
  label: string
): Promise<{ error?: string; passkey?: any }> {
  const t = await getTranslations("Settings");
  const session = await auth();
  const token = (session as any)?.accessToken as string | undefined;
  if (!token) return { error: t("SessionExpired") };

  const cookieStore = await cookies();
  const signed = cookieStore.get("passkey-challenge")?.value;
  if (!signed) return { error: t("ChallengeExpired") };

  const challenge = verifyChallenge(signed, process.env.NEXTAUTH_SECRET!);
  if (!challenge) return { error: t("ChallengeInvalid") };

  cookieStore.delete("passkey-challenge");

  let res: Response;
  try {
    res = await fetch(`${API}/api/auth/passkey/register/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ credential, expected_challenge: challenge, label }),
    });
  } catch {
    return { error: t("CouldNotReachServer") };
  }

  if (!res.ok) return { error: t("RegisterPasskeyFailed") };

  const passkey = await res.json();
  revalidatePath("/settings");
  return { passkey };
}

export async function renamePasskeyAction(
  id: string,
  label: string
): Promise<{ error?: string }> {
  const t = await getTranslations("Settings");
  const session = await auth();
  const token = (session as any)?.accessToken as string | undefined;
  if (!token) return { error: t("SessionExpiredShort") };

  const res = await fetch(`${API}/api/auth/passkey/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ label }),
  });
  if (!res.ok) return { error: t("RenamePasskeyFailed") };
  return {};
}

export async function deletePasskeyAction(id: string): Promise<{ error?: string }> {
  const t = await getTranslations("Settings");
  const session = await auth();
  const token = (session as any)?.accessToken as string | undefined;
  if (!token) return { error: t("SessionExpiredShort") };

  const res = await fetch(`${API}/api/auth/passkey/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return { error: t("DeletePasskeyFailed") };
  revalidatePath("/settings");
  return {};
}
