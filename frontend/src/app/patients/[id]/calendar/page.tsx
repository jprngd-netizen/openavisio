import { AppLayout } from "@/components/layout/AppLayout";
import { getPatient } from "@/lib/api";
import { Breadcrumb } from "@/components/Breadcrumb";
import { CalendarGrid } from "./CalendarGrid";

export default async function CalendarPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let patient: any = null;
  try { patient = await getPatient(id); } catch {}

  return (
    <AppLayout>
      <Breadcrumb
        crumbs={patient ? [{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }] : []}
        current="Calendar"
      />
      <CalendarGrid patientId={id} birthDate={patient?.birth_date} />
    </AppLayout>
  );
}
