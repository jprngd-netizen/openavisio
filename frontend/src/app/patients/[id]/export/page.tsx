import {
  getPatient,
  getEncounters,
  getConditions,
  getMedications,
  getObservations,
  getDocuments,
  getPrescriptions,
} from "@/lib/api";
import { notFound } from "next/navigation";
import { getTranslations, getLocale } from "next-intl/server";
import { formatDate } from "@/lib/utils";
import { MEASUREMENT_TYPES } from "@/lib/measurementTypes";
import { ExportPanel } from "./ExportPanel";

// The seven chart sections, in render order. The slug doubles as the
// `?sections=` value and the `Export.Sections.*` i18n key.
const SECTIONS = [
  "encounters",
  "conditions",
  "medications",
  "measurements",
  "lab-results",
  "documents",
  "prescriptions",
] as const;
type Section = (typeof SECTIONS)[number];

// Known coded values that have a translated export label. Anything else is
// shown raw so an unexpected value is never swallowed.
const ENCOUNTER_TYPES = new Set(["Consulta", "Retorno", "Teleconsulta", "Urgencia", "Evolucao", "Procedimento"]);
const SEVERITIES = new Set(["mild", "moderate", "severe"]);
const CONDITION_STATUSES = new Set(["active", "inactive", "resolved"]);
const VITAL_CODES = new Set<string>(MEASUREMENT_TYPES.map((m) => m.code));

export default async function PatientExportPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ sections?: string | string[] }>;
}) {
  const { id } = await params;
  const sp = await searchParams;
  const rawParam = Array.isArray(sp.sections) ? sp.sections.join(",") : sp.sections;

  // No `sections` param at all = export everything; an empty string = nothing.
  const selected: Section[] =
    rawParam === undefined
      ? [...SECTIONS]
      : rawParam
          .split(",")
          .map((s) => s.trim())
          .filter((s): s is Section => (SECTIONS as readonly string[]).includes(s));
  const has = (s: Section) => selected.includes(s);

  const [patient, t, locale] = await Promise.all([
    getPatient(id).catch(() => null),
    getTranslations("Export"),
    getLocale(),
  ]);
  if (!patient) notFound();

  // Fetch only the selected sections; a failing section degrades to empty
  // rather than blanking the whole document.
  const [encounters, conditions, medications, measurements, labResults, documents, prescriptions] = await Promise.all([
    has("encounters") ? getEncounters(id).catch(() => [] as any[]) : Promise.resolve([] as any[]),
    has("conditions") ? getConditions(id).catch(() => [] as any[]) : Promise.resolve([] as any[]),
    has("medications") ? getMedications(id).catch(() => [] as any[]) : Promise.resolve([] as any[]),
    has("measurements") ? getObservations(id, { category: "measurement" }).catch(() => [] as any[]) : Promise.resolve([] as any[]),
    has("lab-results") ? getObservations(id, { category: "lab" }).catch(() => [] as any[]) : Promise.resolve([] as any[]),
    has("documents") ? getDocuments(id).catch(() => [] as any[]) : Promise.resolve([] as any[]),
    has("prescriptions") ? getPrescriptions(id).catch(() => [] as any[]) : Promise.resolve([] as any[]),
  ]);

  const generatedOn = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date());
  const genderLabels: Record<string, string> = { male: "Male", female: "Female", other: "Other" };
  const genderRaw = patient.gender ? String(patient.gender).toLowerCase() : null;
  const gender = genderRaw ? (genderLabels[genderRaw] ? t(genderLabels[genderRaw]) : patient.gender) : null;

  const encounterType = (raw: string | null | undefined) =>
    raw && ENCOUNTER_TYPES.has(raw) ? t(`EncounterType.${raw}`) : raw || "";
  const vitalLabel = (code: string, fallback: string | null) =>
    VITAL_CODES.has(code) ? t(`Vitals.${code}`) : fallback || code;
  const severityLabel = (raw: string | null | undefined) =>
    raw && SEVERITIES.has(raw) ? t(`Severity.${raw}`) : raw || "";
  const conditionStatus = (raw: string | null | undefined) =>
    raw && CONDITION_STATUSES.has(raw) ? t(`ConditionStatus.${raw}`) : raw || "";
  const prescriptionStatus = (raw: string | null | undefined) => {
    const key = raw ? `Status${raw.charAt(0).toUpperCase()}${raw.slice(1)}` : "StatusDraft";
    return t(`Prescription.${key}`);
  };

  const sectionTitle = (s: Readonly<{ slug: Section; label: string }>) => s.label;

  return (
    <div className="mx-auto max-w-[900px] bg-white p-6 text-black print:max-w-none print:p-0">
      {/* @page margin only; everything else is Tailwind print: variants */}
      <style>{`@page { margin: 15mm }`}</style>

      <ExportPanel patientId={id} selected={selected} />

      <header className="mb-6 border-b border-black/15 pb-4">
        <h1 className="text-2xl font-bold">{patient.given_name} {patient.family_name}</h1>
        <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-black/70">
          {patient.birth_date && (
            <span>
              <span className="font-medium text-black/50">{t("BirthDate")}: </span>
              {formatDate(patient.birth_date, locale)}
            </span>
          )}
          {gender && (
            <span>
              <span className="font-medium text-black/50">{t("Sex")}: </span>
              {gender}
            </span>
          )}
          <span>
            <span className="font-medium text-black/50">{t("GeneratedOn")}: </span>
            {generatedOn}
          </span>
        </div>
      </header>

      {has("encounters") && (
        <Section title={sectionTitle({ slug: "encounters", label: t("Sections.encounters") })}>
          {encounters.length === 0 ? (
            <NoData t={t} />
          ) : (
            <div className="space-y-4">
              {encounters.map((e: any) => {
                const vitals = (e.measurements ?? []).filter((m: any) => m.value_quantity != null);
                const blocks: [string, any][] = [
                  [t("Encounter.ChiefComplaint"), e.chief_complaint],
                  [t("Encounter.History"), e.history],
                  [t("Encounter.PhysicalExam"), e.physical_exam],
                  [t("Encounter.Assessment"), e.assessment],
                  [t("Encounter.Plan"), e.plan],
                  [t("Encounter.Notes"), e.notes],
                ].filter(([, v]) => v) as [string, any][];
                return (
                  <article key={e.id} className="break-inside-avoid rounded-lg border border-black/15 p-3">
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <span className="font-semibold">{formatDate(e.encounter_date, locale)}</span>
                      {e.encounter_type && <span className="text-sm text-black/70">{encounterType(e.encounter_type)}</span>}
                      {(e.cid10_code || e.cid10_display) && (
                        <span className="text-xs text-black/60">
                          {e.cid10_code || ""}
                          {e.cid10_code && e.cid10_display ? " · " : ""}
                          {e.cid10_display || ""}
                        </span>
                      )}
                    </div>

                    {vitals.length > 0 && (
                      <div className="mt-2">
                        <div className="text-xs font-semibold text-black/60">{t("Encounter.Vitals")}</div>
                        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                          {vitals.map((m: any, i: number) => (
                            <span key={m.id ?? m.code ?? i}>
                              <span className="text-black/50">{vitalLabel(m.code, m.code_display)}: </span>
                              {m.value_quantity}
                              {m.value_unit ? ` ${m.value_unit}` : ""}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {blocks.length > 0 && (
                      <dl className="mt-2 space-y-1.5">
                        {blocks.map(([label, value]) => (
                          <div key={label}>
                            <dt className="text-xs font-semibold text-black/60">{label}</dt>
                            <dd className="whitespace-pre-wrap text-sm">{value}</dd>
                          </div>
                        ))}
                      </dl>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </Section>
      )}

      {has("conditions") && (
        <Section title={sectionTitle({ slug: "conditions", label: t("Sections.conditions") })}>
          {conditions.length === 0 ? (
            <NoData t={t} />
          ) : (
            <Table
              head={[t("Condition.Name"), t("Condition.Onset"), t("Condition.Severity"), t("Condition.Status")]}
            >
              {conditions.map((c: any) => (
                <tr key={c.id} className="border-t border-black/10">
                  <td className="py-1.5 pr-3 font-medium">{c.code_display}</td>
                  <td className="py-1.5 pr-3">{formatDate(c.onset_date_time, locale)}</td>
                  <td className="py-1.5 pr-3">{severityLabel(c.severity)}</td>
                  <td className="py-1.5">{conditionStatus(c.clinical_status)}</td>
                </tr>
              ))}
            </Table>
          )}
        </Section>
      )}

      {has("medications") && (
        <Section title={sectionTitle({ slug: "medications", label: t("Sections.medications") })}>
          {medications.length === 0 ? (
            <NoData t={t} />
          ) : (
            <Table head={[t("Medication.Name"), t("Medication.Dosage"), t("Medication.Period"), t("Medication.Status")]}>
              {medications.map((m: any) => (
                <tr key={m.id} className="border-t border-black/10">
                  <td className="py-1.5 pr-3 font-medium">{m.medication_display}</td>
                  <td className="py-1.5 pr-3">{m.dosage_text || (m.dose_quantity ? `${m.dose_quantity} ${m.dose_unit || ""}` : "—")}</td>
                  <td className="py-1.5 pr-3">{medicationPeriod(m, locale, t)}</td>
                  <td className="py-1.5">{m.is_active ? t("Medication.Active") : t("Medication.Ended")}</td>
                </tr>
              ))}
            </Table>
          )}
        </Section>
      )}

      {has("measurements") && (
        <Section title={sectionTitle({ slug: "measurements", label: t("Sections.measurements") })}>
          {measurements.length === 0 ? (
            <NoData t={t} />
          ) : (
            <Table head={[t("Measurement.Type"), t("Measurement.Date"), t("Measurement.Value")]}>
              {measurements.map((o: any) => (
                <tr key={o.id} className="border-t border-black/10">
                  <td className="py-1.5 pr-3 font-medium">{o.code_display || o.code}</td>
                  <td className="py-1.5 pr-3">{formatDate(o.effective_date_time, locale)}</td>
                  <td className="py-1.5">
                    {o.value_quantity != null ? `${o.value_quantity}${o.value_unit ? ` ${o.value_unit}` : ""}` : o.value_string || "—"}
                  </td>
                </tr>
              ))}
            </Table>
          )}
        </Section>
      )}

      {has("lab-results") && (
        <Section title={sectionTitle({ slug: "lab-results", label: t("Sections.lab-results") })}>
          {labResults.length === 0 ? (
            <NoData t={t} />
          ) : (
            <Table head={[t("Lab.Test"), t("Lab.Panel"), t("Lab.Result"), t("Lab.Reference"), t("Lab.Date")]}>
              {labResults.map((o: any) => (
                <tr key={o.id} className="border-t border-black/10">
                  <td className="py-1.5 pr-3 font-medium">{o.code_display || o.code}</td>
                  <td className="py-1.5 pr-3">{o.panel || "—"}</td>
                  <td className="py-1.5 pr-3">
                    {o.value_quantity != null ? `${o.value_quantity}${o.value_unit ? ` ${o.value_unit}` : ""}` : o.value_string || "—"}
                  </td>
                  <td className="py-1.5 pr-3">
                    {labReference(o)}
                  </td>
                  <td className="py-1.5">{formatDate(o.effective_date_time, locale)}</td>
                </tr>
              ))}
            </Table>
          )}
        </Section>
      )}

      {has("documents") && (
        <Section title={sectionTitle({ slug: "documents", label: t("Sections.documents") })}>
          {documents.length === 0 ? (
            <NoData t={t} />
          ) : (
            <Table head={[t("Document.FileName"), t("Document.Type"), t("Document.IssuedDate")]}>
              {documents.map((d: any) => (
                <tr key={d.id} className="border-t border-black/10">
                  <td className="py-1.5 pr-3 font-medium">{d.file_name || "—"}</td>
                  <td className="py-1.5 pr-3">{d.type || d.document_classification || "—"}</td>
                  <td className="py-1.5">{formatDate(d.issued_date ?? d.created_at, locale)}</td>
                </tr>
              ))}
            </Table>
          )}
        </Section>
      )}

      {has("prescriptions") && (
        <Section title={sectionTitle({ slug: "prescriptions", label: t("Sections.prescriptions") })}>
          {prescriptions.length === 0 ? (
            <NoData t={t} />
          ) : (
            <div className="space-y-3">
              {prescriptions.map((p: any) => (
                <article key={p.id} className="break-inside-avoid rounded-lg border border-black/15 p-3">
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
                    <span className="font-semibold">{t("Prescription.Status")}: {prescriptionStatus(p.status)}</span>
                    <span className="text-black/70">{t("Prescription.Date")}: {formatDate(p.issued_at ?? p.created_at, locale)}</span>
                    {p.notes && <span className="text-black/70">{p.notes}</span>}
                  </div>
                  {(p.items ?? []).length > 0 ? (
                    <table className="mt-2 w-full text-xs">
                      <thead>
                        <tr className="text-left text-black/50">
                          <th className="py-1 pr-3 font-medium">{t("Prescription.Medication")}</th>
                          <th className="py-1 pr-3 font-medium">{t("Prescription.Posology")}</th>
                          <th className="py-1 font-medium">{t("Prescription.Quantity")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {p.items.map((item: any, i: number) => (
                          <tr key={item.id ?? i} className="border-t border-black/10">
                            <td className="py-1 pr-3 font-medium">{item.medication_name || "—"}</td>
                            <td className="py-1 pr-3">{item.posology || "—"}</td>
                            <td className="py-1">{item.quantity ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <p className="mt-1 text-xs text-black/60">{t("Prescription.NoItems")}</p>
                  )}
                </article>
              ))}
            </div>
          )}
        </Section>
      )}

      <footer className="mt-8 border-t border-black/15 pt-3 text-center text-xs text-black/60">
        {t("Footer", { datetime: generatedOn })}
      </footer>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-6 break-inside-avoid">
      <h2 className="mb-2 border-b border-black/15 pb-1 text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function NoData({ t }: { t: (key: string) => string }) {
  return <p className="text-sm text-black/60">{t("NoData")}</p>;
}

function Table({ head, children }: { head: string[]; children: React.ReactNode }) {
  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="text-left text-xs text-black/50">
          {head.map((h, i) => (
            <th key={i} className="py-1 pr-3 font-medium">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  );
}

function medicationPeriod(m: any, locale: string, t: (key: string) => string) {
  if (!m.effective_start && !m.effective_end) return "—";
  const start = m.effective_start ? formatDate(m.effective_start, locale) : "—";
  const end = m.effective_end ? formatDate(m.effective_end, locale) : t("Medication.Ongoing");
  return `${start} – ${end}`;
}

function labReference(o: any) {
  if (o.reference_range) return o.reference_range;
  if (o.ref_low != null && o.ref_high != null) return `${o.ref_low}–${o.ref_high}`;
  if (o.ref_high != null) return `< ${o.ref_high}`;
  if (o.ref_low != null) return `> ${o.ref_low}`;
  return "—";
}
