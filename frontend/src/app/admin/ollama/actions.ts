"use server";

import { auth } from "@/auth";
import { getTranslations } from "next-intl/server";

export async function saveAiModelsAction(config: {
  extract_model: string | null;
  classify_model: string | null;
  chat_model: string | null;
  vision_model: string | null;
}): Promise<{ error?: string }> {
  const t = await getTranslations("Admin");
  const session = await auth();
  const token = (session as any)?.accessToken as string | undefined;
  if (!token) return { error: t("NotAuthenticated") };

  const res = await fetch(
    `${process.env.API_URL || "http://localhost:8000"}/api/admin/ollama/models`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(config),
    }
  );

  if (!res.ok) return { error: t("SaveFailed", { status: res.status }) };
  return {};
}
