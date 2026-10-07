"use server";

import { auth } from "@/auth";
import { revalidatePath } from "next/cache";
import { getTranslations } from "next-intl/server";

const API = process.env.API_URL || "http://localhost:8000";

async function token() {
  const session = await auth();
  return (session as any)?.accessToken as string | undefined;
}

export async function createPurposeAction(input: {
  name: string;
  description: string;
  identification_mode: string;
  expires_at: string | null;
}): Promise<{ id?: string; error?: string }> {
  const tr = await getTranslations("Admin");
  const t = await token();
  if (!t) return { error: tr("NotAuthenticated") };

  const res = await fetch(`${API}/api/sharing-purposes`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${t}` },
    body: JSON.stringify({
      name: input.name,
      description: input.description || null,
      identification_mode: input.identification_mode,
      expires_at: input.expires_at,
    }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: typeof data?.detail === "string" ? data.detail : tr("Failed", { status: res.status }) };
  }
  const data = await res.json();
  revalidatePath("/admin/sharing");
  return { id: data.id };
}

export async function closePurposeAction(purposeId: string): Promise<{ error?: string }> {
  const tr = await getTranslations("Admin");
  const t = await token();
  if (!t) return { error: tr("NotAuthenticated") };

  const res = await fetch(`${API}/api/sharing-purposes/${purposeId}/close`, {
    method: "POST",
    headers: { Authorization: `Bearer ${t}` },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: typeof data?.detail === "string" ? data.detail : tr("Failed", { status: res.status }) };
  }
  revalidatePath("/admin/sharing");
  revalidatePath(`/admin/sharing/${purposeId}`);
  return {};
}
