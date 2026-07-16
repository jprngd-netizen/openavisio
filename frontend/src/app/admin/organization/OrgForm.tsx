"use client";

import { useState } from "react";
import { updateOrganizationAction } from "./actions";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "de", label: "Deutsch" },
];

const LEGAL_FIELDS = [
  { key: "legal_name", label: "Name / Firma / Verein", hint: "Wer betreibt diese Installation?", required: true },
  { key: "legal_street", label: "Straße und Hausnummer", required: true },
  { key: "legal_postcode", label: "PLZ", required: true },
  { key: "legal_city", label: "Ort", required: true },
  { key: "legal_country", label: "Land" },
  { key: "legal_email", label: "E-Mail", hint: "Muss tatsächlich gelesen werden (§5 DDG).", required: true },
  { key: "legal_phone", label: "Telefon" },
  { key: "legal_responsible", label: "Inhaltlich verantwortlich", hint: "Nur nötig, wenn redaktionelle Inhalte veröffentlicht werden." },
  { key: "legal_vat_id", label: "USt-IdNr.", hint: "Nur eintragen, wenn vorhanden — niemals erfinden." },
  { key: "legal_register", label: "Registereintrag", hint: "z.B. Amtsgericht Aalen, VR 1234 (Verein)." },
  { key: "dpo_contact", label: "Datenschutzbeauftragte:r", hint: "Nur, wenn eine:r bestellt ist." },
] as const;

type Org = Record<string, string | null | undefined>;

export function OrgForm({
  initialName,
  initialDescription,
  initialLanguage,
  org,
}: {
  initialName: string;
  initialDescription: string | null;
  initialLanguage: string;
  org: Org;
}) {
  const [name, setName] = useState(initialName);
  const [description, setDescription] = useState(initialDescription ?? "");
  const [language, setLanguage] = useState(initialLanguage);
  const [legal, setLegal] = useState<Record<string, string>>(
    Object.fromEntries(LEGAL_FIELDS.map((f) => [f.key, (org[f.key] as string) ?? ""])),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSaved(false);
    const result = await updateOrganizationAction({
      name: name.trim() || undefined,
      description: description.trim() || null,
      default_language: language,
      // empty means "not set" — send null so a wrong entry can actually be cleared
      ...Object.fromEntries(LEGAL_FIELDS.map((f) => [f.key, legal[f.key]?.trim() || null])),
    });
    setSaving(false);
    if (result.error) {
      setError(result.error);
    } else {
      setSaved(true);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1">
        <label className="text-sm font-medium">Name</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
          required
        />
      </div>

      <div className="space-y-1">
        <label className="text-sm font-medium">Description</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          className="w-full rounded-lg border bg-background px-3 py-2 text-sm resize-none"
        />
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">Default language</label>
        <p className="text-xs text-muted-foreground">Used for new users and AI document extraction.</p>
        <div className="flex flex-wrap gap-2">
          {LANGUAGES.map((l) => (
            <button
              key={l.code}
              type="button"
              onClick={() => setLanguage(l.code)}
              className={`px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors
                ${language === l.code
                  ? "border-primary bg-primary/10 text-primary"
                  : "hover:bg-muted"
                }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-3 rounded-lg border border-amber-300 bg-amber-50/50 p-4 dark:border-amber-800 dark:bg-amber-950/30">
        <div>
          <h3 className="text-sm font-semibold">Betreiberangaben (Impressum &amp; Datenschutz)</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            In Deutschland nach §5 DDG verpflichtend, sobald der Dienst über den rein privaten
            Gebrauch hinausgeht. Diese Angaben erscheinen im Impressum und als Verantwortlicher in
            der Datenschutzerklärung. Solange sie fehlen, weisen beide Seiten offen darauf hin.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {LEGAL_FIELDS.map((f) => (
            <div key={f.key} className="space-y-1">
              <label className="text-sm font-medium">
                {f.label}
                {"required" in f && f.required && <span className="text-destructive"> *</span>}
              </label>
              <input
                value={legal[f.key] ?? ""}
                onChange={(e) => setLegal({ ...legal, [f.key]: e.target.value })}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              />
              {"hint" in f && f.hint && <p className="text-xs text-muted-foreground">{f.hint}</p>}
            </div>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {saved && <p className="text-sm text-green-600">Saved.</p>}

      <button
        type="submit"
        disabled={saving}
        className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save"}
      </button>
    </form>
  );
}
