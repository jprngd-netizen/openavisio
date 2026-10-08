import {
  FileText,
  Stethoscope,
  Activity,
  HeartPulse,
  ClipboardList,
  FlaskConical,
  Syringe,
  HardHat,
  ShieldAlert,
  FileSignature,
  Printer,
  Smile,
  CalendarClock,
  Brain,
  Target,
  Accessibility,
  AlertTriangle,
  TestTubes,
  Ban,
  AudioLines,
  Droplet,
  Plane,
  ShieldCheck,
  CalendarDays,
  HandCoins,
  BadgeCheck,
  Gavel,
  FileWarning,
  Search,
  ScrollText,
  MoreHorizontal,
  type LucideIcon,
} from "lucide-react";

// Taxonomy for the "Prontuário Ocupacional" (occupational health record).
// Grouped, ordered single source of truth for the index page, the per-section
// placeholder pages and the overview/menu entry point. `key` maps to a key in
// the `Occupational` i18n namespace; `slug` is a stable, short, English,
// kebab-case route segment.
export type OccItem = { slug: string; key: string; Icon: LucideIcon };
export type OccGroup = { slug: string; key: string; Icon: LucideIcon; items: OccItem[] };

export const OCCUPATIONAL_SECTIONS: OccGroup[] = [
  {
    slug: "identification",
    key: "GroupIdentification",
    Icon: FileText,
    items: [{ slug: "cover", key: "Cover", Icon: FileText }],
  },
  {
    slug: "anamnesis-exam",
    key: "GroupAnamnesisExam",
    Icon: Stethoscope,
    items: [
      { slug: "clinical-history", key: "ClinicalHistory", Icon: Stethoscope },
      { slug: "physical-exam", key: "PhysicalExam", Icon: Activity },
      { slug: "vital-data", key: "VitalData", Icon: HeartPulse },
      { slug: "quality-of-life", key: "QualityOfLife", Icon: Smile },
      { slug: "characterization", key: "Characterization", Icon: ClipboardList },
      { slug: "follow-up", key: "FollowUp", Icon: CalendarClock },
    ],
  },
  {
    slug: "health-programs",
    key: "GroupHealthPrograms",
    Icon: HeartPulse,
    items: [
      { slug: "health-program", key: "HealthProgram", Icon: HeartPulse },
      { slug: "mental-health-program", key: "MentalHealthProgram", Icon: Brain },
      { slug: "focused-care", key: "FocusedCare", Icon: Target },
      { slug: "workplace-violence", key: "WorkplaceViolence", Icon: ShieldAlert },
      { slug: "disability-rehabilitation", key: "DisabilityRehabilitation", Icon: Accessibility },
      { slug: "critical-activities", key: "CriticalActivities", Icon: AlertTriangle },
    ],
  },
  {
    slug: "exams",
    key: "GroupExams",
    Icon: FlaskConical,
    items: [
      { slug: "complementary-exams", key: "ComplementaryExams", Icon: FlaskConical },
      { slug: "summons-exams", key: "SummonsExams", Icon: ClipboardList },
      { slug: "additional-exams", key: "AdditionalExams", Icon: TestTubes },
      { slug: "exam-blocks", key: "ExamBlocks", Icon: Ban },
      { slug: "audiometry-analysis", key: "AudiometryAnalysis", Icon: AudioLines },
      { slug: "hematology-series-analysis", key: "HematologySeriesAnalysis", Icon: Droplet },
    ],
  },
  {
    slug: "attendances",
    key: "GroupAttendances",
    Icon: Activity,
    items: [
      { slug: "occupational-medical-exam", key: "OccupationalMedicalExam", Icon: Stethoscope },
      { slug: "clinical-attendance", key: "ClinicalAttendance", Icon: Activity },
      { slug: "special-exam", key: "SpecialExam", Icon: FlaskConical },
      { slug: "critical-activity-screening", key: "CriticalActivityScreening", Icon: AlertTriangle },
      { slug: "traveler-health", key: "TravelerHealth", Icon: Plane },
      { slug: "medical-attendance", key: "MedicalAttendance", Icon: ClipboardList },
      { slug: "medical-regulation", key: "MedicalRegulation", Icon: ShieldCheck },
    ],
  },
  {
    slug: "leave-benefits",
    key: "GroupLeaveBenefits",
    Icon: CalendarDays,
    items: [
      { slug: "leaves", key: "Leaves", Icon: CalendarDays },
      { slug: "benefits", key: "Benefits", Icon: HandCoins },
      { slug: "preventive-exam-allowance", key: "PreventiveExamAllowance", Icon: BadgeCheck },
      { slug: "benefit-type-contestation", key: "BenefitTypeContestation", Icon: Gavel },
    ],
  },
  {
    slug: "vaccination",
    key: "GroupVaccination",
    Icon: Syringe,
    items: [
      { slug: "vaccines", key: "Vaccines", Icon: Syringe },
      { slug: "serology-exams", key: "SerologyExams", Icon: TestTubes },
    ],
  },
  {
    slug: "work-accident",
    key: "GroupWorkAccident",
    Icon: HardHat,
    items: [
      { slug: "report-work-accident", key: "ReportWorkAccident", Icon: FileWarning },
      { slug: "occupational-nexus-investigation", key: "OccupationalNexusInvestigation", Icon: Search },
      { slug: "mortality-permanent-disability", key: "MortalityPermanentDisability", Icon: AlertTriangle },
    ],
  },
  {
    slug: "declarations-others",
    key: "GroupDeclarationsOthers",
    Icon: ScrollText,
    items: [
      { slug: "transfer-report", key: "TransferReport", Icon: FileSignature },
      { slug: "others", key: "Others", Icon: MoreHorizontal },
      { slug: "suicide-attempts-deaths", key: "SuicideAttemptsDeaths", Icon: AlertTriangle },
    ],
  },
];

// Bonus entry: "Impressão de Prontuário". It has no page of its own — the index
// links it straight to /patients/{id}/export (the existing export route).
export const OCCUPATIONAL_PRINT_ITEM: OccItem = { slug: "print-record", key: "PrintRecord", Icon: Printer };

// Flattened lookup used by the per-section page to resolve a slug. Only items
// with a real page (i.e. the grouped ones) are resolvable; print-record has no
// page and is intentionally absent, so its route would 404.
export const OCCUPATIONAL_ITEM_BY_SLUG: Record<string, { group: OccGroup; item: OccItem }> = Object.fromEntries(
  OCCUPATIONAL_SECTIONS.flatMap((group) => group.items.map((item) => [item.slug, { group, item }])),
);
