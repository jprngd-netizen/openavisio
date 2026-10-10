# Plano de implementação — Escopo grande (R3): Obstetrícia e Interação medicamentosa

> Baseado nas decisões de **Gabriel** (owner) em **2026-10-10**:
> **DEC-1b** obstetrícia = episódio obstétrico completo · **DEC-2b** interação = base externa ·
> **DEC-3** taxonomia de `encounter_type` aprovada (aplicada no WS-10).
> Complementa — não substitui — `docs/plans/2026-10-09-prontuario-clinico-hardening.md`.
> Estado: R1 (safety clínico) concluída; R2 (WS-6/7/8/10) já planejada no plano-mestre.
> Branch de trabalho: a definir por workstream, empilhadas sobre `feat/prontuario-hardening`.

## 0. Nota de gate

Estas duas frentes só entram em implementação com este plano aprovado — decisão tomada pelo
owner (DEC-1b/DEC-2b), detalhamento de requisitos produzido aqui. Sub-decisões abertas ficam
marcadas (OB-*, IX-*) e precisam de resolução antes da fase correspondente.

---

## Parte A — Obstetrícia (episódio obstétrico completo)

### A.1 Work breakdown

| ID | Workstream | Entrega ponta-a-ponta | Conclusão | Esforço |
|----|-----------|-----------------------|-----------|---------|
| OB-1 | Recurso `Pregnancy` (episódio gestacional) | Modelo + migração + API + seção "Gestação" na UI | Gestação criada, com DUM/DPP/IG calculada e status | ~4 |
| OB-2 | Consultas de pré-natal | `Encounter` vinculado à gestação + campos obstétricos (IG, AU, BCF, apresentação, edema/PA) | Pré-natal registrado e visível na timeline da gestação | ~4 |
| OB-3 | Desfecho / parto | Registro de desfecho (parto vaginal/cesárea/aborto) + dados do RN, encerrando o episódio | Episódio fechado com desfecho e RN documentado | ~3 |
| OB-4 | Integrações clínicas | Diagnósticos gestacionais como `Condition` vinculados à gestação; vitais de acompanhamento (peso/PA) e exames (via WS-8) ligados ao episódio | Intercorrências (DMG, pré-eclâmpsia) e exames rastreáveis ao episódio | ~3 |

### A.2 Modelo (proposto)

- `Pregnancy(OwnedResource)`: `patient_id`; `status` (StrEnum: active/completed/miscarriage/terminated);
  `lmp_date` (`Date`, DUM), `estimated_due_date` (`Date`, DPP — Naegele: DUM + 280 dias), `ended_at` (`Date`);
  `gravida`/`para` (histórico obstétrico, poderiam ir no `Patient` — **OB-DEC-1**).
- `PregnancyVisit` — **ou** reusar `Encounter` com `pregnancy_id` FK opcional (**OB-DEC-2**: tabela própria
  vs vínculo em `Encounter`). Campos obstétricos: `gestational_age_weeks` (derivado ou digitado),
  `fundal_height_cm`, `fetal_heart_rate_bpm`, `presentation`, `edema`, `proteinuria`.
- `PregnancyOutcome`: tipo de parto, data, RN (peso, APGAR, intercorrências) — ou embutido no `Pregnancy`.

### A.3 Dependências

| De | Para | O quê | Duro/Mole |
|----|------|-------|-----------|
| WS-5 (datas tipadas) | OB-1/2/3 | `Date`/`DateTime` tipados | **Duro** |
| WS-8 (vínculo exame↔consulta) | OB-4 | Atribuição de exames ao atendimento gestacional | Mole |
| WS-3 (diagnósticos↔Condition) | OB-4 | Intercorrências como Condition | Mole |
| WS-4 (vitais) | OB-2 | PA/peso no pré-natal | Mole |

### A.4 Verificação

- Cálculo de IG e DPP (Naegele) com testes de unidade (datas limítrofes).
- Criar gestação → adicionar consultas de pré-natal → registrar desfecho; tudo persistido e rastreável.
- Diagnóstico gestacional vinculado aparece na lista de problemas com origem.
- Suíte ≥ baseline + novos; caminho de migração verde (`test_migration_parity`).

### A.5 Riscos e decisões

| ID | Descrição | Dono | Prazo |
|----|-----------|------|-------|
| OB-DEC-1 | Onde guardar GOP (gravida/para) — no `Patient` ou derivar das gestações? | Gabriel | antes da OB-1 |
| OB-DEC-2 | Pré-natal como tabela própria vs `Encounter` com `pregnancy_id` | Gabriel | antes da OB-2 |
| OB-DEC-3 | Terminologia dos desfechos (incluir abortamento/ectópica/óbito fetal?) | Gabriel | antes da OB-3 |
| OB-RSK-1 | IG/DPP: regra (DUM vs USG precoce) — USG corrige a DPP quando divergente | Gabriel | OB-1 |
| OB-RSK-2 | PHI: seguir envelope encryption/access grants (ADR-031), como os demais recursos | Gabriel | contínuo |

---

## Parte B — Interação medicamentosa (base externa)

### B.1 Work breakdown

| ID | Workstream | Entrega ponta-a-ponta | Conclusão | Esforço |
|----|-----------|-----------------------|-----------|---------|
| IX-1 | Catálogo → código de fármaco | Mapear o texto de `medication_display` para um identificador estável (ex.: RxCUI) | Itens de prescrição resolvidos a um código de fármaco | ~3 |
| IX-2 | Cliente de interação + cache | Serviço que consulta a base externa e cacheia resultado por par de fármacos | Dado um par, retorna interação (severidade/descrição) ou "sem dados" | ~4 |
| IX-3 | Alerta na prescrição (advisory) | Banner de interação na UI de prescrever, atrás de **feature flag** | Prescrever par interagente mostra aviso; nunca bloqueia | ~3 |
| IX-4 | Degradação e observabilidade | Timeout/retry, fallback silencioso, métricas de acerto/erro | Falha da base externa não quebra a prescrição nem trava a UI | ~2 |

### B.2 Abordagem

- **Fonte externa** — **IX-DEC-1** (a decidir): RxNav/RxNorm Drug-Drug Interaction API (aberta, base dos EUA),
  vs DrugBank (licença), vs fonte brasileira (ANVISA/bulas) — e, se a Memed já expõe interações, avaliar
  reuso antes de adicionar dependência própria (**IX-DEC-2**).
- **Sem PHI para terceiros**: enviar apenas nomes/códigos de fármacos, nunca dados do paciente.
- **Advisory, nunca bloqueante**: a evidência clínica e o julgamento do prescritor prevalecem; o alerta informa.
- Reaproveitar a normalização existente (`allergy_alert.normalize_substance`) para o casamento e reusar o
  ponto de extensão já marcado em `medication_reconciliation.find_duplicates` (WS-2).

### B.3 Dependências e sequenciamento

| Fase | Workstreams | Depende de | Gate |
|------|-------------|-----------|------|
| 1 | IX-1 (mapeamento) | — | cobertura de mapeamento medida sobre o catálogo real |
| 2 | IX-2 | IX-1 | retorno correto em pares conhecidos + cache |
| 3 | IX-3 | IX-2 | alerta visível atrás de flag |
| 4 | IX-4 | IX-2/3 | teste de falha/timeout sem travar prescrição |

### B.4 Rollout e rollback

- **Rollout**: feature flag desligada por padrão; ligar só para o próprio Gabriel primeiro; observabilidade
  do serviço externo antes de generalizar. Nada é bloqueado se a flag estiver off.
- **Rollback**: desligar a flag (volta ao comportamento atual = só duplicidade). Nenhum dado de schema
  depende do serviço externo, então o rollback é imediato.

### B.5 Verificação

- Testes de unidade do mapeamento e do casamento de interação (com fixtures, sem rede real no CI).
- Teste de integração com a base externa `marked`/`skipif` (rede), mais um teste de degradação (timeout → sem alerta).
- Aceite: prescrição com par sabidamente interagente mostra o aviso; par sem interação não mostra;
  serviço externo fora não altera o fluxo de prescrição.

### B.6 Riscos e decisões

| ID | Descrição | Dono | Prazo |
|----|-----------|------|-------|
| IX-DEC-1 | Qual base externa de interação (licença/cobertura/custo) | Gabriel | antes da IX-2 |
| IX-DEC-2 | Reusar o que a Memed expõe antes de adicionar dependência própria | Gabriel | antes da IX-2 |
| IX-RSK-1 | Falsos positivos/negativos erodem confiança no alerta | Gabriel | contínuo |
| IX-RSK-2 | Mapeamento incompleto (nomes livres → código) gera furos silenciosos | Gabriel | IX-1 |
| IX-RSK-3 | Disponibilidade/rate-limit do provedor externo | Gabriel | IX-4 |
| IX-RSK-4 | PHI: garantir que só o fármaco (não o paciente) sai para a rede | Gabriel | contínuo |

---

## Sequenciamento global sugerido

```
R2 (já planejada): WS-6 selo/versão · WS-7 imunizações · WS-8 vínculos · WS-10 continuidade
   ↓
R3 (este plano): Parte B (interação, menor e isolada por flag) pode correr em paralelo
                 Parte A (obstetrícia) é maior — começar por OB-1
   ↓
WS-12 (paridade migração↔modelo completa) — antes de novos deploys
```

**Recomendação**: intercalar — landar a R2 primeiro (já especificada), depois Parte B (interação,
isolada por flag) e Parte A (obstetrícia, maior). Rodar os workstreams de schema **em série**
(subagentes compartilham working tree + banco de teste + linha do Alembic).

---

*Este plano não executa nada. Implementação/QA/release seguem skills próprias. Onde há "modelo proposto"
é desenho de engenharia, não guideline clínico — depende de validação do Gabriel.*

---

## Adendo — decisões de 2ª rodada (2026-10-10)

**Princípio de projeto — o registro é retrato da data.** O registro de uma consulta (e sua versão
selada, WS-6) mostra o que era **fato naquela data**; nunca é reescrito por valor derivado/atual.
- IG e GOP no registro de uma consulta são calculados **na data do atendimento**, não na data atual.
- Diagnósticos já são snapshot no vínculo consulta↔Condition (WS-3) e na versão selada (WS-6). ✓
- Painéis vivos (meds ativas, GOP corrente) ficam **fora** do registro histórico — são estado corrente.
- Registros de enfermagem entram no mesmo regime (datados e congelados).

**Decisões fechadas:**
- **OB-DEC-1** = **GOP derivado** das gestações (sem campo manual no `Patient`).
- **OB-DEC-2** = **tabela própria de pré-natal** (`PregnancyVisit`), não reusar `Encounter`.
- **OB-DEC-3** = **desfechos completos** — parto vaginal/cesárea **+ abortamento (espontâneo/induzido)
  + ectópica + óbito fetal** (terminologia adequada).
- **NOVO ESCOPO** — **seção de cuidados de enfermagem (geral + obstétrica)**: anotações datadas por
  atendimento, sob o princípio do retrato da data. Workstream novo (OB-5).
- **IX-DEC-1 / IX-DEC-2** = fechadas pela pesquisa → `docs/research/2026-10-10-drug-interaction.md`.

**Interação — desenho recomendado (pesquisa):** RxNav DDI **descontinuado** (02/01/2024) e DrugBank só
pago → descartados como fonte de interação. **Primário**: alerta **nativo da Memed** (camada humana, PT)
+ **IMSES/CRF-MG** (base BR, grátis, só graves) para medicação em texto livre. **Fallback sempre-on e
sem PHI**: **DDInter 2.0** (CC BY-NC-SA, uso pessoal) espelhado no repo. Mapeamento texto-livre→princípio
ativo via **dados abertos ANVISA**. Cache por par, timeout curto, severidade só-grave, **advisory**,
nenhuma PHI para terceiros.

**Status:** R1 em produção (v0.8.0); R2 pronta para deploy (v0.9.0); WS-12 concluída — a suíte agora
cobre o caminho de migração (`OA_TEST_SCHEMA=migrations`), fechando o RSK-5.

