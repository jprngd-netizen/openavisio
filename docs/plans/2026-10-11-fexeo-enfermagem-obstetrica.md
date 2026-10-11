# Plano — R4: Instrumentos FExEO-SUS (enfermagem obstétrica)

**Origem:** decisão do Gabriel — **"A e b"**: (a) modelar os campos estruturados a partir dos
instrumentos do caderno *FExEO-SUS / CEEO-Rede Alyne* (MS+UFMG, jul/2026) e (b) ensinar o pipeline de IA a
reconhecer esse tipo de documento e rotear a extração para as seções corretas.

**Fonte:** caderno (2079 linhas). Digest: `~/.hermes/profiles/senna/cache/scratch/oa_fexeo_digest.md`.
**Regra do próprio caderno (l.188):** *"Os instrumentos não substituem o prontuário"* — instrumento ≠ prontuário.

## Decisões

- **D1.** O caderno é **fonte de schema** (campos), não de dados. Quando um item for clínico, entra como dado
  **da paciente**, nunca da especializanda/preceptora.
- **D2.** **Parte II (avaliação de competências, ICM 2024) NÃO vira prontuário** — fora de escopo. O
  classificador pode reconhecê-la, mas o `verify` **não materializa** dado clínico.
- **D3.** Reaproveitar modelos existentes ao máximo; criar **apenas `NewbornRecord`** como modelo novo.
  `MonitoringInstrument` (forma do instrumento) fica **backlog**.
- **D4.** Pipeline mantém o padrão vigente: **IA sugere → humano confirma** (nada é gravado sem verificação).
- **D5.** Migrações **aditivas** apenas; não reabrir escopo sem nova decisão registrada.

## Escopo — R4 em 3 fases

### Fase 1 — Schema/modelos (backend, migrações aditivas) — ✅ **CONCLUÍDA**

> Entregue em dois workstreams empilhados: **R4A** (`f3a4b5c6d7e8`, `Pregnancy`+`PregnancyVisit`) e
> **R4B** (`b7c8d9e0f1a2`, `NursingCare`+`NewbornRecord`). Suíte **558 passed** nos dois caminhos; base `25ac2d7`.

1. **`Pregnancy`** += `risk_classification` (habitual/intermediário/alto), `planned_pregnancy`,
   `contraceptive_at_conception`, `gravida`, `para_vaginal`, `para_cesarean`, `abortions`, `living_children`,
   `preeclampsia_risk_factors` (JSON), `preeclampsia_moderate_risk_factors` (JSON), `aspirin_prophylaxis`,
   `aspirin_start_week`, `imc_pre_gestational_class`, `perinatal_mental_health_history`,
   `domestic_violence_investigated`, `family_history` (JSON), `reference_maternity`, `linked_to_maternity`.
2. **`PregnancyVisit`** += `consultation_type`, `first_visit_before_12w`, `main_care_provider`, `remote_consult`,
   `dental_health_activity`, `complaints` (JSON), `warning_signs` (JSON), `current_intercurrences` (JSON),
   `edema_class` (ausente/+/++/+++/++++), `leopold_done`, `fundal_height_recorded_on_chart`, `bcf_change`,
   exame físico dirigido (pele/mucosas, tireoide, mamas, ausculta cardíaca, ausculta pulmonar: bool + alteração),
   `vaccination_status` (JSON), `vaccines_in_gestation` (JSON: dTpa/dT/VSR/covid/influenza),
   `orientation_topics` (JSON), `weight_gain_weekly_ok`, `birth_plan_elaborated`.
3. **`NursingCare`** += `subcategory` (`labor` | `postpartum` | `sexual_reproductive` | `general`),
   `instrument_type`, `structured_data` (JSON específico do instrumento).
4. **NOVO `NewbornRecord`** (1:1 com `PregnancyOutcome`) — I.2+I.3 (~60 campos): `birth_datetime`, `sex`,
   `delivery_type`, `gestational_age_weeks`, `classification` (AIG/PIG/GIG), `apgar_1`/`apgar_5`/`apgar_10`,
   `weight_g`, `length_cm`, `pc_cm`/`pt_cm`/`pa_cm`, `physical_exam` (JSON sistema por sistema), `reflexes` (JSON),
   `feeding`, `eliminations`, `hypoglycemia`, `hypothermia`, `immunization` (BCG/HepB),
   `congenital_malformation`, `reanimation` (JSON), `skin_to_skin_1h`, `cord_clamping`.
5. **Reuso**: `Observation` (vitais + labs por trimestre), `Condition` (intercorrências/IST/violência),
   `MedicationStatement` (suplementos/uterotônicos), `Recommendation`/`CalendarEvent` (exames/retorno/encaminhamento).

### Fase 2 — UI — ✅ **CONCLUÍDA**

> **UI-1** Gestação + Pré-natal (`644d62e`); **UI-2** Enfermagem (subformulários parto/pós-parto/saúde sexual) +
> nova seção **Recém-nascido** (`5f8123f`). `tsc` 0, `build` 0, i18n pt/en/de **2217** chaves em paridade exata.

- Enriquecer os formulários das seções: **Gestação**, **Pré-natal** (visita), **Enfermagem** (obstétrico, com
  subformulários parto / pós-parto / saúde sexual) e novo painel **RN** (vinculado ao desfecho).
- Campos opcionais onde houver dado sensível ("prefere não informar"). i18n pt/en/de em paridade.

### Fase 3 — Pipeline de IA (item b)

- Novos `document_type`: `fexeo_prenatal_monitoring`, `fexeo_labor_birth_record`,
  `fexeo_postpartum_rooming_record`, `fexeo_sexual_reproductive_visit`, `fexeo_competency_assessment` (formativo).
- Classificador distingue **acompanhamento × avaliação** (heurística: "MARCO DE DESENVOLVIMENTO",
  "ESPECIALIZANDA", "PRÁTICAS ASSOCIADAS" → formativo; medidas como PA/AU/BCF/Apgar → acompanhamento).
- Extração por entidade com `confidence`/`source_span`.
- **Roteamento no `POST /documents/{id}/verify`** por tipo → cria/víncula `Pregnancy`, `PregnancyVisit`,
  `NursingCare`, `NewbornRecord`, `PregnancyOutcome`; dedupe por data/episódio; campos formativos descartados.

## Contrato do payload `fexeo` (Fase 3)

A extração devolve, além das entidades atuais, um objeto **opcional** `fexeo` (presente só quando
`document_type` é um dos tipos FExEO clínicos). O `verify` recebe o mesmo objeto em
`VerifyDocumentRequest.fexeo` e roteia por `DocumentReference.document_classification`:

- **`fexeo_prenatal_monitoring`** → `{"pregnancy": {<patch>}, "prenatal_visit": {<campos R4A>}}`
  (+ observations/conditions/medications pelo caminho atual).
- **`fexeo_labor_birth_record`** → `{"pregnancy": {…}, "nursing_care": {"subcategory": "labor"|"postpartum", "structured_data": {…}}, "newborn": {…}, "outcome": {…}}`.
- **`fexeo_postpartum_rooming_record`** → `{"nursing_care": {"subcategory": "postpartum", …}, "newborn": {…}}`.
- **`fexeo_sexual_reproductive_visit`** → `{"nursing_care": {"subcategory": "sexual_reproductive", "structured_data": {…}}}`.
- **`fexeo_competency_assessment`** → **não materializa** nada clínico (marcar como formativo; só arquiva).

Regras: cada sub-objeto carrega **só o que o documento afirma** (nada inferido); vínculo a `Pregnancy` por
DUM/nome/data; dedupe de `PregnancyVisit` por data; campos formativos (especializanda/preceptora/marcos
NO/1–4) **sempre descartados**; continua "IA sugere → humano confirma".

## Fora de escopo

- **Parte II** (avaliação de competências) — nunca vira dado clínico.
- `MonitoringInstrument` (backlog) e engine próprio de interação (IX-1..IX-4, backlog).

## Critérios de aceitação (gate)

- Suíte pytest verde nos **DOIS** caminhos (`create_all` e `OA_TEST_SCHEMA=migrations`); `alembic heads` único;
  `tsc --noEmit` exit 0; paridade i18n pt/en/de.
- Testes novos: modelos/campos novos, endpoints, roteamento do `verify` por `document_type`, e
  **"formativo não materializa"**.

## Riscos

1. **Formativo ≠ clínico** — não poluir o prontuário com dado de ensino.
2. **PHI/LGPD** (art. 11): violência, orientação sexual, identidade de gênero, IST, aborto → minimização no
   OCR/embeddings, cuidado com logging, acesso controlado.
3. **OCR de checkboxes** ☐/códigos (1/0/99) em tabelas multicoluna → falsos positivos.
4. **Ambiguidade de escala** ("1/2/3/4" resposta vs marco de competência).
5. **Vínculo ao episódio** — usar data da consulta/parto para não criar gestação duplicada.

## Ordem de execução

Fase 1 (workstreams seriais — tree/DB compartilhados) → Fase 2 (UI) → Fase 3 (pipeline). Cada fase com gate
completo antes de avançar. Deploy de PHI só com ok explícito + backup.