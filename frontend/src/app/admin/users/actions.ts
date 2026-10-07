"use server";

import { auth } from "@/auth";
import { revalidatePath } from "next/cache";
import { getTranslations } from "next-intl/server";

const API = process.env.API_URL || "http://localhost:8000";

async function adminFetch(path: string, body: unknown) {
  const t = await getTranslations("Admin");
  const session = await auth();
  const token = (session as any)?.accessToken as string | undefined;
  if (!token) return { error: t("NotAuthenticated") };

  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) return { error: t("RequestFailed", { status: res.status }) };
  revalidatePath("/admin/users");
  return {};
}

export async function setRoleAction(userId: string, role: string) {
  return adminFetch(`/api/admin/users/${userId}/role`, { role });
}

export async function setActiveAction(userId: string, isActive: boolean) {
  return adminFetch(`/api/admin/users/${userId}/active`, { is_active: isActive });
}

export async function eraseUserAction(userId: string, confirmEmail: string) {
  const t = await getTranslations("Admin");
  const session = await auth();
  const token = (session as any)?.accessToken as string | undefined;
  if (!token) return { error: t("NotAuthenticated") };

  const res = await fetch(`${process.env.API_URL || "http://localhost:8000"}/api/admin/users/${userId}/erase`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ confirm_email: confirmEmail }),
  });

  if (res.status === 409) {
    const data = await res.json().catch(() => ({}));
    return { error: data.detail?.message ?? t("UserOwnsPatients") };
  }
  if (res.status === 422) {
    const data = await res.json().catch(() => ({}));
    return { error: data.detail ?? t("ConfirmationEmailMismatch") };
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: data.detail ?? t("RequestFailed", { status: res.status }) };
  }

  revalidatePath("/admin/users");
  return {};
}
