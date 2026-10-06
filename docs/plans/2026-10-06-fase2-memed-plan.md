---
slug: 2026-10-06-fase2-memed-plan
status: approved-for-build
intent: clear
classification: architecture
plan_path: .omo/plans/2026-10-06-fase2-memed-plan.md
mirror: docs/plans/2026-10-06-fase2-memed-plan.md
owner_decisions:
  production_model: "A — dry-run + homolog agora; go-live como runbook separado e gated"
  worker_vps_access: "nenhum — worker entrega scripts/runbook; deploy pelo orquestrador"
  emission_policy_flag: "default linked_user; alternativa any_admin; sem mudança de default"
  credits: "A — auditoria interna contando emissões + aviso no admin apontando ao 'Meu Plano' do BirdID"
  tests: "TDD na guarda de config, transição failed, filtro de redação, validação de origin e flag; tests-after em UI/runbook/docs"
---

# Plano de implementação — Fase 2 (Memed produção + hardening + deploy)

## 1. Objetivo

Transformar o domínio de prescrição da Fase 1 (homolog/fake, testado) em algo **pronto para uso diário e para produção**, fechando os gaps encontrados na exploração e deixando o go-live de produção como um **runbook separado e gated**.

Premissa corrigida durante a exploração: `backend/app/core/config.py:75-81` **já declara** os campos `MEMED_*` e o `compose.yaml` / `deploy/docker-compose.prod.yml` **já passam** as variáveis. O que falta é a **guarda fail-closed** e a consistência de ambiente — não "adicionar campos".

## 2. Escopo

**Dentro:** guarda de produção; ativação e validação das credenciais de produção; emissão assinada real via BirdID com semântica de falha real; retenção/backup/restore do PDF; observabilidade (créditos, auditoria com IP, redação sistêmica de log, rate limit); deploy na VPS SP com smoke ponta a ponta; placeholders reversíveis de distribuição.

**Fora:** SNCR direto; motor de assinatura próprio; geração de PDF próprio; layout/QR da RDC 1.000/2025 feito por nós; multi-tenant real, SaaS, billing; conformidade regulatória formal (IEC 62304, ISO 14971, ISO 13485, QMS, dossiê ANVISA).

## 3. Componentes (ledger)

| id | outcome | arquivos-chave |
|---|---|---|
| **C1** | Config Memed **fail-closed** em produção | `backend/app/core/config.py:75-110`; `.env`; `deploy/setup.sh` |
| **C2** | Ativação de produção + superfície de validação de credenciais/health | `backend/app/routers/prescriber.py:58-161`; `backend/app/services/prescriptions/memed_client.py` |
| **C3** | Emissão assinada real via BirdID + estado `failed` real + retry | `backend/app/services/prescriptions/state.py:54-59`; `routers/prescriptions.py:357-394`; `archive.py:43-191`; `MemedEmbed.tsx` |
| **C4** | Retenção/storage/backup/restore do PDF | `deploy/backup/backup.sh`; `archive.py:122-191`; `compose.yaml` |
| **C5** | Observabilidade e abuso | `backend/app/core/log_handler.py:44-58`; `core/ratelimit.py`; `routers/auth.py:38-39,87`; `routers/prescriptions.py:98-108` |
| **C6** | Deploy na VPS SP + smoke ponta a ponta | `compose.yaml`; `deploy/docker-compose.prod.yml`; `deploy/deploy.sh` |
| **C7** | Placeholders reversíveis de distribuição | `config.py`; gate de emissão em `routers/prescriptions.py` |
| **C8** | Testes e evidência | `backend/tests/`; `frontend/e2e/`; `.omo/evidence/` |

---

## 4. Fases e tarefas

### F0 — Guarda de configuração (C1) — TDD

**T0.1 — Guarda fail-closed em `_guard_production`**
- Arquivo: `backend/app/core/config.py:91-110`.
- Regras: em `ENVIRONMENT=production`, **abortar** se: alguma `MEMED_*` crítica estiver vazia; `MEMED_USE_FAKE=true`; `MEMED_ENVIRONMENT=integration`. Mensagem de erro acionável (diz qual variável falta).
- Aceite: subir com `ENVIRONMENT=production` e qualquer uma dessas condições **falha com exit ≠ 0** e mensagem clara.
- Evidência: `backend/tests/test_config_production_guard.py` (TDD — escrever o teste antes).

**T0.2 — Consistência de ambiente**
- `MEMED_ENVIRONMENT` está **ausente no `.env` vivo** → cai no default `integration`. Torna-la explícita e documentada; `deploy/setup.sh` passa a conhecê-la.
- Aceite: `.env.example` e `setup.sh` documentam `MEMED_ENVIRONMENT`; `.env` vivo com valor explícito.
- Evidência: diff do `.env.example` + teste da guarda cobrindo `integration` em produção.

### F1 — Produção Memed: ativação e validação (C2)

**T1.1 — Superfície de validação de credenciais/health**
- Arquivos: `routers/prescriber.py:58-161`, `services/prescriptions/memed_client.py`.
- Expor um endpoint autenticado (admin) que chame `check-key` + `cidades`/`especialidades` e reporte **ok/falha com a causa**, sem vazar as chaves.
- Aceite: com chave inválida, o endpoint devolve erro explícito; com válida, devolve ok.

**T1.2 — Fim do `except Exception: pass` no sync do prescritor**
- Arquivo: `routers/prescriber.py:133-137`.
- Hoje uma falha de sync da Memed **parece sucesso**. Passar a registrar o erro e a propagar um estado visível (ex.: `sync_status: error` + motivo), sem derrubar a resposta quando o cadastro local é válido.
- Aceite: teste que simula o `MemedClient` levantando → o erro aparece na resposta/estado, não é engolido.
- Evidência: `backend/tests/test_prescriber_sync_error.py`.

**T1.3 — Troca de base/script para produção (gated)**
- Scripts prod: API `https://api.memed.com.br/`; script de front `https://partners.memed.com.br/integration.js` (o `.env` atual aponta para homolog).
- **Não executar** sem as credenciais de produção. Entregar como passo do runbook (F6) + teste que verifica que a config de produção é coerente.

### F2 — Emissão assinada real e semântica de falha (C3) — TDD

**T2.1 — Estado `failed` real (gap central)**
- Hoje `failed` **nunca é setado**: `archive.py:43-191` lança e faz rollback; `routers/prescriptions.py:384-386` mapeia `ValueError`→409 e deixa o resto estourar 500 → a receita **fica presa em `draft`**, e o botão Retry da UI é inalcançável.
- Implementar a transição: falha de captura/assinatura marca a prescrição como `failed`, com motivo persistido e evento de auditoria.
- Aceite: teste que força falha de captura → status vira `failed` (não `draft`), o motivo é recuperável e o retry fica disponível.
- Evidência: `backend/tests/test_prescription_failed_transition.py` (TDD — teste primeiro).

**T2.2 — Retry alcançável e idempotente**
- `routers/prescriptions.py:357-394`: retry a partir de `failed` volta para `draft`/captura; guarda contra concorrência (versão otimista já existente).

**T2.3 — Validação de `event.origin` no embed**
- Arquivo: `frontend/src/app/patients/[id]/prescriptions/MemedEmbed.tsx`.
- Só aceitar `postMessage` do origin da Memed (homolog e prod). Rejeitar o resto.
- Aceite: teste e2e com origin inválido → mensagem ignorada; origin válido → fluxo normal.
- Evidência: spec e2e + `test_log_redaction.py`-style guard.

**T2.4 — Token BirdID: expirado/inválido no meio do fluxo**
- BirdID: token válido 1–12h, e as **falhas não têm código de API** (só mensagem de UI).
- Tratar: token expirado no início (pedir novo) vs. falha na assinatura (marcar `failed` com motivo legível).
- Aceite: teste cobrindo os dois casos com o `FakeMemedClient`.

### F3 — PDF: retenção, storage, backup e restore (C4)

**T3.1 — Retenção documentada e aplicada**
- Definir e documentar a política de retenção do PDF assinado. (A retenção da Memed **não foi encontrada** na doc — assumir que é nossa.)
- Aceite: doc + teste de que o blob sobrevive ao ciclo normal e é removido no erasure cascade.

**T3.2 — Backup completo + `AGE_PUBKEY`**
- `deploy/backup/backup.sh` já cobre `/data/documents` + dump clínico + keystore, mas o `.env` vivo tem **`AGE_PUBKEY` vazio** e o `compose.yaml` raiz (o deploy real) **não tem serviço de backup**.
- Preencher a chave, adicionar o serviço de backup ao compose raiz, agendar.
- Aceite: um ciclo de backup roda e produz artefato cifrado verificável.

**T3.3 — Ensaio de restore (obrigatório)**
- Restaurar de verdade num ambiente descartável: banco + blobs + keystore → abrir um PDF de uma prescrição assinada.
- Aceite: **evidência do restore** (log + hash do PDF recuperado) em `.omo/evidence/`.

### F4 — Observabilidade e abuso (C5)

**T4.1 — Filtro sistêmico de redação de log**
- `backend/app/core/log_handler.py:44-58` publica a **mensagem crua** no Redis/DB; hoje a proteção é só por call-site. Residual conhecido: `memed_client.py:205` loga os **64 primeiros chars da URL do PDF**.
- Implementar um backstop no handler (padrões: chaves, tokens, assinaturas de URL) + limpar o call-site.
- Aceite: teste que injeta um segredo no log e verifica que ele **não** chega ao destino.
- Evidência: `backend/tests/test_log_redaction.py` estendido (TDD).

**T4.2 — Auditoria de emissão com origem**
- `routers/prescriptions.py:98-108` não registra `ip_address`/`user_agent` (o share-link externo já registra).
- Adicionar aos eventos de emissão/captura.
- Aceite: evento de auditoria traz IP e user-agent.

**T4.3 — Rate limit nas rotas de escrita**
- Hoje só auth (`auth.py:38-39,87`). Aplicar a `memed-session` e `capture`.
- Aceite: teste que estoura o limite e recebe 429.

**T4.4 — Créditos: visibilidade operacional**
- A Memed **não expõe API de consumo**; os créditos são da Soluti/BirdID (saldo no app "Meu Plano").
- Contador interno de emissões + aviso no painel admin apontando para o "Meu Plano". **Sem scraping.**
- Aceite: contador visível e coerente com o número de emissões assinadas.

### F5 — Placeholders reversíveis de distribuição (C7)

**T5.1 — `deployment_mode`**
- Config com `personal` (default) | `clinic` | `multi_tenant`. Apenas o modo `personal` é implementado; os demais são pontos de extensão que **não alteram comportamento**.
- Aceite: default `personal`; testes existentes intactos.

**T5.2 — Flag de política de emissão**
- Default `linked_user` (comportamento atual: só o user vinculado ao Prescritor emite); alternativa `any_admin`. Lida pelo gate backend.
- Aceite: com o default, nenhuma mudança de comportamento; teste para `any_admin`.
- Evidência: `backend/tests/test_emission_policy_flag.py` (TDD).

**T5.3 — Pontos de extensão de termos/telemetria**
- Apenas hooks, **desligados por padrão**. O front já tem telemetria Umami opt-in e consentimento GDPR — não reaproveitar como "deployment mode".

### F6 — Deploy na VPS SP + runbook de go-live (C6)

**T6.1 — Deploy em homolog na VPS (ou dry-run local)**
- Migração, env, stack saudável; **sem** credenciais de produção.
- Worker **não** tem acesso à VPS: entrega script/runbook; a execução na VPS é do orquestrador.

**T6.2 — Smoke ponta a ponta em homolog**
- Fluxo: prescritor → prescrição → captura → PDF arquivado. Evidência anexada.

**T6.3 — Runbook de go-live (gated, separado)**
- Documento com: pré-requisitos (credenciais de produção + BirdID + VPS), passos, verificações, e **critério de rollback**.
- Só é executado quando o owner fornecer as credenciais. **O worker não assume que elas existem.**

### F7 — Testes e evidência (C8)

- TDD: T0.1, T2.1, T2.3, T4.1, T5.2.
- Tests-after: UI admin, runbook, docs.
- Regressão obrigatória: **322 testes backend** + **5 e2e** continuam verdes; `tsc` limpo.
- Evidência em `.omo/evidence/`.

---

## 5. Cobertura obrigatória (checklist do owner)

- [ ] Guarda fail-closed em `_guard_production` + `MEMED_ENVIRONMENT` consistente — **F0**
- [ ] `failed` realmente setado, com retry alcançável — **F2 T2.1/T2.2**
- [ ] `upsert_prescriber` não engole mais erro + superfície de health — **F1 T1.1/T1.2**
- [ ] Filtro sistêmico de redação (incl. URL do PDF) — **F4 T4.1**
- [ ] Auditoria de emissão com `ip_address`/`user_agent` — **F4 T4.2**
- [ ] Rate limit em `memed-session` e `capture` — **F4 T4.3**
- [ ] Backup: `AGE_PUBKEY`, serviço no compose raiz e **ensaio de restore** — **F3 T3.2/T3.3**
- [ ] Placeholders reversíveis, default `personal` — **F5**
- [ ] Go-live como runbook separado e gated — **F6 T6.3**

## 6. Riscos

| Risco | Mitigação |
|---|---|
| Credenciais de produção não existem (form. de parceiro ~48h) | Tudo construído em dry-run/homolog; go-live gated (decisão A) |
| BirdID falha sem código de API | Tratar por mensagem + estado `failed` com motivo; testes com o fake |
| Sem API de consumo de créditos | Contador interno + aviso no admin (não depender da Memed) |
| Retenção de PDF não documentada pela Memed | Política própria, documentada e testada |
| Regressão na captura síncrona ao introduzir `failed` | TDD na transição + suíte completa antes do merge |

## 7. Critério de aceitação

1. Emissão **assinada de verdade** com o BirdID produz prescrição com PDF arquivado criptografado; falhas viram `failed` com motivo e retry.
2. Guarda de produção aborta configuração insegura.
3. Nenhum segredo em log (backstop testado).
4. Backup roda e o **ensaio de restore** recupera um PDF assinado.
5. Stack na VPS SP saudável com smoke ponta a ponta em homolog; runbook de go-live pronto e não executado.
6. Placeholders presentes com default `personal`, sem mudar comportamento atual.
7. **322 testes backend + 5 e2e** verdes; `tsc` limpo.