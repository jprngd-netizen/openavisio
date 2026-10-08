import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const API = process.env.API_URL || "http://localhost:8000";

// Stream the server-generated record PDF (record + the original documents'
// pages) so the browser downloads it. `auth()` is called directly here, same
// as the document/photo routes.
export async function GET(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const token = ((await auth()) as any)?.accessToken ?? null;
  if (!token) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const search = req.nextUrl.searchParams.toString();
  const res = await fetch(`${API}/api/patients/${id}/export/pdf${search ? `?${search}` : ""}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    return NextResponse.json({ error: "Export failed" }, { status: res.status });
  }
  const blob = await res.arrayBuffer();
  return new NextResponse(blob, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="patient-${id}.pdf"`,
    },
  });
}
