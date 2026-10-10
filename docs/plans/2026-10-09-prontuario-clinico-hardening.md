# Plano de implementação — Endurecimento clínico do prontuário

> Baseado no parecer de revisão clínica do prontuário (`pasted-text-2026-10-09`) e nas
> decisões de escopo de **Gabriel** (product owner + médico) em **2026-10-09**:
> **1-C** (todos os 9 itens), **2-B** (implementar versão+selo da evolução),
> **3-C** (incluir todos os contrafactuais).
> Complementa — não substitui — `docs/plans/2026-10-09-prontuario-clinico.md`
> (que registrou a decisão de fundo: prontuário clínico, deocupacionalizado).
> Branch de trabalho: `feat/prontuario-receitas`. `alembic head` = `o7b8c9d0e1f2`.

## 0. Nota de gate (entrada)

O insumo original é um **parecer/rascunho**, não um spec aprovado. O gate foi fechado
pelo próprio Gabriel (as três decisões acima), que é o decision-maker autorizado.
Isso é o que autoriza este plano a existir; sem essas três respostas, o plano não
poderia ser produzido (condição de parada da skill `implementation-planning`).

**Não reabrir escopo sem nova decisão registrada.** Escopo aprovado = 11 workstreams.

**Status 2026-10-10:** **R1 (safety clínico) concluída** — WS-5, WS-5b (correção de paridade
migração↔modelo), WS-1, WS-2, WS-3, WS-4, WS-9 na branch `feat/prontuario-hardening`
(tag `v0.8.0`); suíte 422 → 474 verdes. **R2 concluída** (WS-6 selo/versão, WS-7 imunizações+familiares,
WS-10 continuidade, WS-8 vínculos exame/prescrição↔consulta); suíte 474 → 502 verdes. Escopo grande
(obstetrícia DEC-1b, interação DEC-2b) tem plano próprio em
`2026-10-10-escopo-grande-obstetricia-interacao.md`. **WS-12 (paridade migração↔modelo) concluído**
na branch `feat/hardening-ws12-migration-parity`: a suíte passa a exercitar o schema de migração via
`OA_TEST_SCHEMA=migrations` (default continua `create_all`); migração corretiva `a9b8c7d6e5f4`
reconcilia o drift `NOT NULL` modelo↔migração; o drift cosmético remanescente (colunas legadas do
estágio S5 + nomes `uq_`/`ix_`) está documentado como aceito em `docs/runbooks/migration-parity.md`.
RSK-5 mitigada por `test_migration_parity` + WS-12.

## 1. Work Breakdown

Fatias verticais (valor ponta-a-ponta), não camadas. Esforço em **dev-dias** (projeto
essencialmente solo: Gabriel + delegação de agentes, ex. `sentinela`).

| ID | Workstream | Entrega ponta-a-ponta | Critério de conclusão | Risco | Esforço |
|----|-----------|-----------------------|-----------------------|-------|---------|
| WS-1 | Alergias estruturadas + alerta | Recurso de alergia (substância/reção/severidade/criticidade/status) + alerta no ato de prescrever + banner na consulta | Alergia cadastrada de forma estruturada; prescrever substância conflitante dispara alerta | **Alto** | ~4 |
| WS-2 | Reconciliação de medicações ativas | Visão "medicações ativas agora" no encounter + detecção de duplicidade | Lista de meds ativas a 1 clique da consulta; duplicidade sinalizada | **Alto** | ~3 |
| WS-3 | N diagnósticos + vínculo consulta↔`Condition` | Assessment permite múltiplos CIDs e gera/atualiza `Condition` com proveniência | ≥2 diagnósticos na consulta; diagnóstico criado aparece na lista de problemas com origem | **Alto** | ~5 |
| WS-4 | Vitais ampliados + painel de PA + validação | PA como painel com componentes; + FR, glicemia capilar, dor (EVA), perímetro cefálico/percentis; validação de plausibilidade | Novos códigos gravados; sys/dia compartilham um painel; valor implausível é rejeitado/avisado | Médio | ~4 |
| WS-5 | Datas tipadas (foundation) | Migrar `String` ISO → `DateTime`/`Date` com tz (encounter, condition, patient, observation, med, calendar) | Colunas tipadas + backfill dos dados legados; ordenação e hora corretas | Médio | ~5 |
| WS-6 | Autor/selo/versão da evolução | Profissional responsável + conselho no encounter; versão imutável selada (hash) da nota | Evolução emitida gera versão selada imutável; edição cria nova versão | Médio | ~5 |
| WS-7 | Imunizações + familiares estruturados | Recurso `Immunization`; antecedentes familiares por grau de parentesco | Vacinas registradas; familiar com grau de parentesco estruturado | Médio/baixo | ~4 |
| WS-8 | Vínculos `encounter_id` | FK opcional de exame (resultado/`document_reference`) e prescrição à consulta | Recupera "o que foi pedido/interpretado/prescrito naquele atendimento" | Médio/baixo | ~3 |
| WS-9 | Safety banner na capa | Capa exibe alergias, medicações ativas e problemas ativos | Banner clínico visível na capa, sem depender de outra seção | Baixo | ~2 |
| WS-10 | Desfecho/continuidade | Taxonomia de `encounter_type`; retorno agendado (vínculo `CalendarEvent`); encaminhamento | Consulta gera retorno no calendário e encaminhamento registrado | Médio | ~4 |
| WS-11 | Contrafactuais (3-C) | Grupo sanguíneo/Rh, gestação/obstetrícia, escalas clínicas (PHQ-9/GAD-7, dor), telemedicina (meio+consentimento), atestados/laudos vinculados | Cada item registrado e consultável; escalas com escore calculado | Médio | ~8 |
| WS-12 | Paridade migração↔modelo | Reconciliar drift schema↔modelos e fazer a suíte exercitar o caminho de migração (hoje só `create_all`) | `alembic check` sem drift relevante; suíte passa contra schema de migração | **Alto** | ~3 |

### Detalhe dos workstreams

#### WS-1: Alergias estruturadas + alerta
- **Escopo**: novo recurso (FHIR-like `AllergyIntolerance`) em vez de `ClinicalHistory.allergies` texto livre. Campos mínimos: substância (`code`+`display`), reação, severidade, criticidade, status, onset. INCLUI alerta no fluxo de prescrição e destaque no encounter. EXCLUI interação medicamentosa (ver WS-2/DEC-2).
- **Dependências**: WS-5 (onset tipado). Soft: catálogo de substâncias.
- **Arquivos-âncora**: `backend/app/models/clinical_history.py:27`, `backend/app/routers/clinical_history.py`, `frontend/src/app/patients/[id]/antecedents/AntecedentsView.tsx:79`, fluxo de prescrição `frontend/src/app/patients/[id]/prescriptions/`.
- **Aceitação**: criar alergia estruturada via API/UI; prescrever substância conflitante dispara alerta; teste de domínio + teste de fluxo.
- **Verificação**: pytest novo + Playwright (prescrever com alergia ativa).

#### WS-2: Reconciliação de medicações ativas
- **Escopo**: consulta que junta `MedicationStatement` (status ativo) e prescrições emitidas; view "meds ativas" no encounter + banner; detecção de duplicidade por substância. EXCLUI checagem de interação com base externa na v1 (DEC-2).
- **Dependências**: WS-5 (datas de vigência). Soft: WS-1 (mesmo catálogo de substâncias).
- **Arquivos-âncora**: `backend/app/models/medication.py`, `backend/app/routers/medications.py`.
- **Aceitação**: encounter lista meds ativas; medicação duplicada sinalizada; teste de serviço de reconciliação.
- **Verificação**: pytest + teste de UI.

#### WS-3: N diagnósticos + vínculo consulta↔Condition
- **Escopo**: trocar o CID único do `Encounter` por múltiplos diagnósticos; criar `Encounter↔Condition` com proveniência (espelha `ConditionSource`); ao registrar diagnóstico na consulta, criar/atualizar `Condition` (lista de problemas). EXCLUI reescrever o merge existente de `Condition`.
- **Dependências**: WS-5 (onset/recorded tipados). 
- **Arquivos-âncora**: `backend/app/models/encounter.py:24-27`, `backend/app/schemas/encounter.py`, `backend/app/models/condition.py`, `backend/app/routers/conditions.py`, `frontend/src/app/patients/[id]/encounters/EncountersView.tsx`.
- **Aceitação**: ≥2 diagnósticos por consulta; diagnóstico criado na consulta aparece em `/conditions` com origem; teste de domínio + migração do CID legado para a primeira condição.
- **Verificação**: pytest + Playwright.

#### WS-4: Vitais ampliados + painel de PA + validação
- **Escopo**: modelar PA como painel com componentes (sys/dia no mesmo momento, ex. FHIR `85354-9`); adicionar FR, glicemia capilar, dor (EVA), perímetro cefálico (+ percentil se pediatria); validação de plausibilidade server+client. IMC já é derivado no cliente.
- **Dependências**: WS-5 (`effective_date_time` tipado).
- **Arquivos-âncora**: `backend/app/models/observation.py`, `frontend/src/lib/measurementTypes.ts` (inclui `bmi`), `frontend/src/app/patients/[id]/encounters/EncountersView.tsx:59`, i18n `Measurement.*` em `frontend/src/messages/{pt,en,de}.json`.
- **Aceitação**: novos códigos persistidos; sys/dia ligados por grupo de componente; PA 3000/200 ou Temp 400 rejeitados com aviso; testes de validação de faixa.
- **Verificação**: pytest (validação) + Playwright (gráfico/histórico).

#### WS-5: Datas tipadas (foundation)
- **Escopo**: migrar `String(50)`/`String(20)` ISO → `DateTime(timezone=True)`/`Date`.
  Campos: `Encounter.encounter_date`, `Condition.recorded_date/onset_date_time/abatement_date_time`, `Patient.birth_date`, `Observation.effective_date_time`, `MedicationStatement.date_asserted/effective_start/effective_end`, `CalendarEvent.start_at/end_at`.
  Legado sem tz: assumir `America/Sao_Paulo` (UTC-03) para datetimes; `Date` para datas puras.
- **Dependências**: nenhuma (é a base). **Bloqueia** WS-1/2/3/4/6/7/10/11 (evita migração dupla).
- **Arquivos-âncora**: modelos listados + `backend/alembic/versions/`.
- **Aceitação**: `alembic heads` único; backfill sem erro em todo o dataset existente; ordenação com hora correta.
- **Verificação**: migração aplicada em dev + teste de parse/backfill.

#### WS-6: Autor/selo/versão da evolução (decisão 2-B)
- **Escopo**: `Encounter` ganha profissional responsável + `board_code/number/state` (reusar o padrão do `Prescriber`); nova `EncounterVersion` imutável com hash/selo por versão emitida; edição cria nova versão. Reusar padrão de hash/selo de `PrescriptionDocument` (`models/prescription.py:157`).
- **Dependências**: WS-5 (timestamps tipados), WS-3 (a versão deve selar também os diagnósticos).
- **Arquivos-âncora**: `backend/app/models/encounter.py`, `backend/app/models/prescription.py` (padrão), `backend/app/routers/encounters.py`.
- **Aceitação**: emitir evolução gera versão selada imutável; editar cria versão nova; hash verificável.
- **Verificação**: pytest (imutabilidade/hash) + teste de rota.

#### WS-7: Imunizações + familiares estruturados
- **Escopo**: recurso `Immunization` (vacina, dose, data, lote, via); `family_history` estruturado por grau de parentesco (1º/2º grau etc.).
- **Dependências**: WS-5.
- **Arquivos-âncora**: `backend/app/models/clinical_history.py`, `frontend/src/app/patients/[id]/antecedents/AntecedentsView.tsx`.
- **Aceitação**: vacina registrada e listada; familiar com grau estruturado; i18n pt/en/de.
- **Verificação**: pytest + UI.

#### WS-8: Vínculos `encounter_id`
- **Escopo**: FK opcional de exame (resultado/`document_reference`, ex. `Observation.document_reference_id`) e `Prescription` à consulta.
- **Dependências**: WS-3, WS-10 (atribuição de solicitação à consulta).
- **Arquivos-âncora**: `backend/app/models/observation.py`, `backend/app/models/prescription.py`.
- **Aceitação**: recupera exames/prescrições por atendimento.
- **Verificação**: pytest.

#### WS-9: Safety banner na capa
- **Escopo**: capa clínica com alergias, medicações ativas e problemas ativos.
- **Dependências**: WS-1, WS-2, WS-3.
- **Arquivos-âncora**: `frontend/src/app/patients/[id]/cover/`, `frontend/src/messages/{pt,en,de}.json`.
- **Aceitação**: banner na capa com os 3 blocos; nada hardcoded.
- **Verificação**: Playwright.

#### WS-10: Desfecho/continuidade
- **Escopo**: taxonomia de `encounter_type` (ambulatorial/emergência/telemedicina/…); retorno agendado vinculado a `CalendarEvent`; encaminhamento (referral) a partir da consulta. `cross-domain`: reusa `CalendarEvent` (`models/calendar.py`).
- **Dependências**: WS-5.
- **Aceitação**: consulta agenda retorno no calendário e registra encaminhamento; `encounter_type` restrito a taxonomia.
- **Verificação**: pytest + Playwright.

#### WS-11: Contrafactuais (decisão 3-C)
- **Escopo** (sub-itens):
  - Grupo sanguíneo/Rh no `Patient`.
  - Gestação/obstetrícia (episódio obstétrico — profundidade a decidir, DEC-1).
  - Escalas clínicas: PHQ-9, GAD-7 e escala de dor (EVA) com escore calculado.
  - Telemedicina: meio + consentimento no encounter.
  - Atestados/laudos avulsos vinculados ao episódio.
- **Dependências**: WS-5; escalas reusam modelo de `Observation`.
- **Aceitação**: cada item registrado e consultável; escalas retornam escore.
- **Verificação**: pytest + UI.

## 2. Mapa de dependências

| De | Para | O quê | Contrato | Duro/Mole |
|----|------|-------|----------|-----------|
| WS-5 | WS-1,2,3,4,6,7,10,11 | Colunas de data tipadas | Migração de schema (colunas novas + backfill) | **Duro** |
| WS-1,2,3 | WS-9 | Dados para o banner | Endpoints de alergia/meds/condições | **Duro** |
| WS-3 | WS-6 | A versão sela diagnósticos | `EncounterVersion` inclui condições | **Duro** |
| WS-3,10 | WS-8 | Atribuição exame/prescrição à consulta | FK `encounter_id` | Mole |
| WS-1/2 | — | Catálogo de substâncias compartilhado | Tabela/lista de substâncias | Mole |

### Caminho crítico

```
WS-5 (fundação de datas) → WS-3 (diagnósticos↔Condition) → WS-9 (safety banner)
   = cadeia mínima obrigatória; WS-6 e WS-11 correm em paralelo e são os maiores
```

WS-5 atrasa **toda** a cadeia de schema: é o gargalo. WS-11 é o maior esforço isolado
e deve começar cedo em paralelo para não virar cauda longa.

## 3. Sequenciamento e paralelização

| Fase | Workstreams | Depende de | Gate de saída |
|------|-------------|-----------|---------------|
| Fase 1 | WS-5 (fundação de datas) | — | `alembic heads` único; backfill OK; suíte verde |
| Fase 2 | WS-1, WS-2, WS-3, WS-4 (paralelo) | WS-5 | Cada um com teste de domínio + rota; i18n pt/en/de |
| Fase 3 | WS-6, WS-7, WS-10, WS-11 (paralelo) | WS-5 (WS-6 também WS-3) | Selo imutável; recursos novos com testes |
| Fase 4 | WS-8 | WS-3, WS-10 | FK + recuperação por atendimento |
| Fase 5 | WS-9 (safety banner) | WS-1, WS-2, WS-3 | Banner na capa; e2e Playwright |

## 4. Propriedade e coordenação

| Papel | Responsável | Workstreams |
|-------|-------------|-------------|
| Decisor clínico/produto | **Gabriel** | Aprovação de escopo, DEC-1/DEC-2 |
| Implementação | **Gabriel + agentes** (delegação a `sentinela`/`magnus`) | Todos |
| Verificação | Revisor independente (agente) | Todos |

- **Checkpoints de integração**: fim de cada fase — suíte completa (`uv run pytest -q`,
  hoje 422 verdes) + `pnpm exec tsc --noEmit` + `pnpm run build` + paridade i18n.
- **Cadência**: um workstream por vez em revisão; sem misturar fases no mesmo PR.

## 5. Estratégia de rollout e rollback

Contexto: app self-hosted pessoal (VPS SP, `health.gabrielsalem.com.br`, `:9340/9341`),
dados são PHI. Não há rollout por % de usuários; o "staged" é **de migração**.

### Estágios (por fase com migração)

| Estágio | Escopo | Gate para avançar | Sinal de observabilidade | Gatilho de rollback |
|---------|--------|-------------------|--------------------------|---------------------|
| S1 Aditivo | Colunas/tabelas novas, nullable | Migração aplica limpa em dev; suíte verde | `alembic heads` único; logs sem erro | Erro de migração |
| S2 Backfill | Preenche colunas novas a partir das antigas | 100% das linhas legadas parseadas | Contagem divergente = 0 | Parse falhando em massa |
| S3 Leitura dupla | App lê novo; escreve nos dois | Dados batem entre colunas | Comparação antigo×novo | Divergência de dado |
| S4 Cutover | App passa a usar só o novo | Período de observação estável | Suíte verde pós-cutover | Regressão funcional |
| S5 Limpeza | Dropa colunas antigas | Após corte confirmado | — | — |

### Rollback por estágio

| Estágio | Procedimento | Rollback de dados | Tempo |
|---------|--------------|-------------------|-------|
| S1–S3 | Reverter deploy; colunas antigas intactas | Não aplicável | minutos |
| S4 | Reverter deploy p/ leitura dupla; colunas antigas ainda presentes | Não aplicável | minutos |
| S5 | Restaurar dump pré-limpeza | Sim (restore) | conforme backup |

### Migração de dados (WS-5 e demais schema)

- **Backfill**: parser ISO → `DateTime`/`Date`; legado sem tz assumido `America/Sao_Paulo`.
- **Compatibilidade**: colunas novas nullable, antigas mantidas até S5; forward-compatible.
- **Cutover**: S4 só após backfill 100% reconciliado.
- **Reconciliação**: comparar valor antigo×novo linha a linha antes de dropar.
- **Backup obrigatório** antes de S1 em produção (PHI — Política de governança/ADR-031).

## 6. Rastreabilidade de verificação

| Requisito (parecer) | WS | Critério de aceitação | Verificação |
|---------------------|----|-----------------------|-------------|
| 1. Alergias estruturadas + alerta | WS-1 | Alergia estruturada + alerta ao prescrever | pytest + Playwright |
| 2. Reconciliação de meds ativas | WS-2 | Lista de meds ativas + duplicidade sinalizada | pytest + UI |
| 3. Assessment→Condition; N CIDs | WS-3 | ≥2 diagnósticos; condição com origem | pytest + Playwright |
| 4. PA painel + RR/glicemia/dor/percentis + validação | WS-4 | Painel único; faixa validada | pytest + Playwright |
| 5. Autor/selo/versão da evolução | WS-6 | Versão imutável selada | pytest |
| 6. Datas tipadas | WS-5 | Backfill 100%; ordenação com hora | teste de migração |
| 7. Imunizações; familiares por parentesco | WS-7 | Vacina + grau estruturados | pytest + UI |
| 8. Exames/prescrições ligados à consulta | WS-8 | Recuperação por atendimento | pytest |
| 9. Safety banner na capa | WS-9 | 3 blocos na capa | Playwright |
| 2.5 Desfecho/continuidade | WS-10 | Retorno + encaminhamento | pytest + Playwright |
| Contrafactuais (3-C) | WS-11 | Cada item registrado | pytest + UI |
| Regressão geral | — | Suíte completa verde | `uv run pytest -q` (≥422 + novos) |
| Build/frontend | — | Compila e tipa | `tsc --noEmit` + `build` |
| i18n | — | Paridade pt/en/de | checagem de paridade |
| e2e no boundary real | — | Fluxo prescrever-com-alergia | **Playwright (fecha lacuna do plano anterior)** |

## 7. Decisões em aberto e riscos

| ID | Descrição | Impacto | Dono | Prazo | Status |
|----|-----------|---------|------|-------|--------|
| DEC-1 | Profundidade da modelagem obstétrica (episódio/pré-natal vs flag simples) | Define esforço do WS-11 | Gabriel | — | **resolvido 2026-10-10: episódio obstétrico completo (DEC-1b)** → plano `2026-10-10-escopo-grande-obstetricia-interacao.md` |
| DEC-2 | Checagem de interação medicamentosa: só duplicidade (v1) vs base externa | Dependência de terceiro / escopo do WS-2 | Gabriel | — | **resolvido 2026-10-10: base externa (DEC-2b)** → plano `2026-10-10-escopo-grande-obstetricia-interacao.md` |
| DEC-3 | Origem da taxonomia de `encounter_type` (valores controlados) | Relatórios/WS-10 | Gabriel | — | **resolvido 2026-10-10: aprovado** (aplicar no WS-10) |
| RSK-1 | Parser de datas legadas falha em formato livre | Dados perdidos/viciados no backfill | Gabriel | Fase 1 | aberto |
| RSK-2 | PHI: novos recursos precisam de envelope encryption + access grants (ADR-031) | Segurança/governança | Gabriel | contínuo | aberto |
| RSK-3 | Paridade i18n pt/en/de em toda UI nova | Regressão de produto | Gabriel | contínuo | aberto |
| RSK-4 | Escopo total (11 WS) = risco de entrega; sem fatiamento vira cauda longa | Cronograma | Gabriel | Fase 0 | aberto |
| RSK-5 | **Suíte usa `create_all`, migrações nunca são exercitadas** → drift schema↔modelos fica invisível. Já causou um bug real (WS-5b: `calendar_events.start_at` legada NOT NULL quebra inserts no caminho de migração = produção). Há também drift pré-existente no app (nomes de `uq_`/`ix_`, nullable de `created_at`). | Produção usa migrações; deploy pode quebrar | Gabriel | antes do deploy R1 | **corrigido (WS-5b + WS-12)** |

## 8. Pressupostos

| Pressuposto | Feito por | Data | Se inválido… |
|-------------|-----------|------|--------------|
| Projeto solo: Gabriel + delegação de agentes | Gabriel | 2026-10-09 | Replanejar capacidade/paralelismo |
| Postgres + Alembic linear (`head=o7b8c9d0e1f2`) | — | 2026-10-09 | Reescrever WS-5 |
| Modelagem "FHIR-like" local (sem servidor FHIR) | — | 2026-10-09 | Mudar contratos de recursos |
| Legado sem tz = `America/Sao_Paulo` | — | 2026-10-09 | Reparsear datas |
| "Tudo" (1-C/2-B/3-C) é o escopo fechado | Gabriel | 2026-10-09 | Novo gate de escopo |

## 9. Recomendação de fatiamento (entrega incrementável)

Escopo aprovado é amplo. Sugiro **3 releases** para reduzir risco (RSK-4), sem cortar nada
do escopo aprovado:
- **R1 (safety clínico)**: WS-5 → WS-1/2/3/4 → WS-9.
- **R2 (registro legal + continuidade)**: WS-6, WS-7, WS-8, WS-10.
- **R3 (completude)**: WS-11.

---

*Este plano não executa nada. Implementação, QA e release seguem skills próprias
(`backend-engineering`/`frontend-engineering`, `qa-methodology`, `release-engineering`).
Onde há "recomendação de modelagem" o insumo original já advertia ser opinião de
engenharia, não evidência robusta de guideline clínico.*
