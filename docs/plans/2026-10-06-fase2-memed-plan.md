---
slug: 2026-10-06-fase2-memed-plan
status: revised-after-review
revision: 2
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
review:
  round: 1
  blockers_found: 2
  majors_found: 7
  resolution: "todos os blockers e majors endereçados nesta revisão (ver §8)"
---

# Plano de implementação — Fase 2 (Memed produção + hardening + deploy)

> **Revisão 2.** A revisão adversarial da rodada 1 achou 2 blockers e 7 majors. Todos foram endereçados nesta revisão — o registro completo (achado → correção) está em **§8**.

## 1. Objetivo

Transformar o domínio de prescrição da Fase 1 (homolog/fake, testado) em algo **pronto para uso diário e para produção**, fechando os gaps encontrados na exploração e deixando o go-live de produção como um **runbook separado e gated**.

Premissa corrigida durante a exploração: `backend/app/core/config.py:75-81` **já declara** os campos `MEMED_*` e o `compose.yaml` / `deploy/docker-compose.prod.yml` **já passam** as variáveis. O que falta é a **guarda fail-closed** e a consistência de ambiente — não "adicionar campos".

**Fronteira de execução (vale para todo o plano):** o worker **não tem acesso à VPS de deploy**. Toda tarefa que exija infraestrutura real (VPS) é **orchestrator-gated**: o worker entrega o script/runbook + a evidência de dry-run local equivalente, e a execução real é do orquestrador. Essas tarefas estão marcadas **[ORQ]**.

## 2. Escopo

**Dentro:** guarda de produção; ativação e validação das credenciais de produção; emissão assinada real via BirdID com semântica de falha real e **idempotência de assinatura**; retenção/backup/restore do PDF; observabilidade (créditos, auditoria com IP, redação sistêmica de log, rate limit); deploy na VPS SP com smoke ponta a ponta; placeholders reversíveis de distribuição.

**Fora:** SNCR direto; motor de assinatura próprio; geração de PDF próprio; layout/QR da RDC 1.000/2025 feito por nós; multi-tenant real, SaaS, billing; conformidade regulatória formal (IEC 62304, ISO 14971, ISO 13485, QMS, dossiê ANVISA).

## 3. Componentes (ledger)

| id | outcome | arquivos-chave |
|---|---|---|
| **C1** | Config **fail-closed** em produção | `backend/app/core/config.py:75-110`; `.env`; `deploy/setup.sh` |
| **C2** | Ativação de produção + superfície de validação de credenciais/health | `backend/app/routers/prescriber.py:58-161`; `services/prescriptions/memed_client.py` |
| **C3** | Emissão assinada real via BirdID + estado `failed` real + retry **idempotente** | `services/prescriptions/state.py:54-59`; `routers/prescriptions.py:357-394`; `archive.py:43-191`; `MemedEmbed.tsx` |
| **C4** | Retenção/storage/backup/restore do PDF (+ guarda da chave privada) | `deploy/backup/backup.sh`; `archive.py:122-191`; `compose.yaml` |
| **C5** | Observabilidade e abuso | `core/log_handler.py:44-58`; `core/ratelimit.py`; `routers/auth.py:38-39,87`; `routers/prescriptions.py:98-108` |
| **C6** | Deploy na VPS SP + smoke ponta a ponta **[ORQ]** | `compose.yaml`; `deploy/docker-compose.prod.yml`; `deploy/deploy.sh` |
| **C7** | Placeholders reversíveis de distribuição | `config.py`; gate de emissão em `routers/prescriptions.py` |
| **C8** | Migrações, testes e evidência | `backend/alembic/versions/`; `backend/tests/`; `frontend/e2e/`; `.omo/evidence/` |

---

## 4. Fases e tarefas

### F0 — Guarda de configuração (C1) — TDD

**T0.1 — Guarda fail-closed em `_guard_production`**
- Arquivo: `backend/app/core/config.py:91-110`.
- Regras: em `ENVIRONMENT=production`, **abortar** se: alguma `MEMED_*` crítica estiver vazia; `MEMED_USE_FAKE=true`; `MEMED_ENVIRONMENT != production`; **`AGE_PUBKEY` vazio** (hoje quebrado em campo — sem ela o backup cifrado não existe); **incoerência de base/script de produção** (base de API apontando para homolog).
- Mensagem de erro acionável (nomeia a variável e o motivo).
- Aceite: subir com `ENVIRONMENT=production` e qualquer uma dessas condições **falha com exit ≠ 0** e mensagem clara.
- Evidência: `backend/tests/test_config_production_guard.py` (TDD — teste primeiro), com um caso por regra.

**T0.2 — Consistência de ambiente**
- `MEMED_ENVIRONMENT` está **ausente no `.env` vivo** → cai no default `integration`. Torna-la explícita e documentada.
- Valores aceitos, definidos explicitamente: `integration` | `production`. A guarda rejeita qualquer outro valor.
- `deploy/setup.sh` passa a conhecê-la e a perguntar/provisionar.
- Aceite: `.env.example` e `setup.sh` documentam `MEMED_ENVIRONMENT` e seus valores; `.env` vivo com valor explícito.

### F1 — Produção Memed: ativação e validação (C2)

**T1.1 — Superfície de validação de credenciais/health**
- Arquivos: `routers/prescriber.py:58-161`, `services/prescriptions/memed_client.py`.
- Expor endpoint autenticado (admin) que chame `check-key` e `cidades`/`especialidades` e reporte **ok/falha com a causa**, sem vazar as chaves.
- **Premissa verificada na Fase 1 (homolog):** `check-key` retorna `{"code":"chave-valida"}` (HTTP 200) e `GET /cidades` / `GET /especialidades` funcionam. A premissa, portanto, **não é especulativa** — mas a revalidação em **produção** é passo do runbook gated (F6 T6.3), não desta tarefa.
- Aceite: com chave inválida, o endpoint devolve erro explícito; com válida, ok. Nenhuma chave aparece na resposta nem no log.

**T1.2 — Fim do `except Exception: pass` no sync do prescritor**
- Arquivo: `routers/prescriber.py:133-137`.
- Hoje uma falha de sync da Memed **parece sucesso**. Passar a registrar o erro e a expor um estado visível (`sync_status: ok|error` + motivo), **sem** derrubar a resposta quando o cadastro local é válido.
- **Requer a migração de T0.3** (novo campo `sync_status`/`sync_error`).
- Aceite: teste que simula o `MemedClient` levantando → o erro aparece no estado persistido.
- Evidência: `backend/tests/test_prescriber_sync_error.py` (TDD).

**T1.3 — Troca de base/script para produção (gated)**
- Scripts prod: API `https://api.memed.com.br/`; script de front `https://partners.memed.com.br/integration.js` (o `.env` atual aponta para homolog).
- **Não executar** sem as credenciais de produção. Entregar como passo do runbook (F6 T6.3); a coerência da config é coberta pela guarda (T0.1).

### F1b — Migrações (C8)

**T0.3 — Migração Alembic dos novos estados**
- **Faltava no plano anterior.** As tarefas T2.1, T2.2 e T1.2 introduzem estado persistido que não existe hoje: **motivo de falha** (`failure_reason`), **estado da assinatura** (`signature_state`) e **status de sync** (`sync_status`/`sync_error`).
- Criar migração(ões) Alembic incrementais a partir do head atual `8f7e7b475af4`, nullable, com default seguro que **não altera** o comportamento das linhas existentes.
- Aceite: `alembic upgrade head` aplica e `alembic downgrade -1` reverte; a suíte de 322 testes continua verde.
- Evidência: arquivo de migração + saída do upgrade/downgrade em `.omo/evidence/`.

### F2 — Emissão assinada real e semântica de falha (C3) — TDD

**T2.1 — Estado `failed` real, persistido fora da transação que faz rollback**
- Hoje `failed` **nunca é setado**: `archive.py:43-191` lança e faz **rollback da transação**; `routers/prescriptions.py:384-386` mapeia `ValueError`→409 e deixa o resto estourar 500 → a receita **fica presa em `draft`** e o Retry da UI é inalcançável.
- **Ponto crítico (blocker da rodada 1):** marcar `failed` **dentro** do caminho que sofre rollback não funciona — a marcação seria desfeita junto. A marcação deve ser persistida numa **transação/sessão separada e autônoma**, **depois** que a exceção propaga do caminho de arquivamento.
- Implementação: capturar a exceção no nível do router/serviço de orquestração, abrir uma `AsyncSession` própria (não a que sofreu rollback), gravar `status=failed` + `failure_reason` + evento de auditoria, e só então responder o erro ao cliente.
- Aceite: teste que força falha de captura → status vira `failed` **de fato** (relido do banco em sessão nova), o motivo é recuperável e o retry fica disponível.
- Evidência: `backend/tests/test_prescription_failed_transition.py` (TDD — teste primeiro).

**T2.2 — Retry idempotente: nunca re-assinar uma prescrição já assinada**
- **Blocker da rodada 1:** lock otimista protege contra concorrência, **não** contra o caso perigoso — assinatura BirdID **bem-sucedida** com captura/arquivamento falhando depois. Um retry cego **re-assina** → **receita legal duplicada** e **novo consumo de crédito** (Soluti/BirdID).
- Implementação: persistir `signature_state` ∈ {`none`, `signed`, `archived`} + o identificador externo da prescrição na Memed. O retry decide pelo estado:
  - `none` → pode assinar (fluxo normal);
  - `signed` → **proibido re-assinar**; reconciliar com a Memed pelo identificador externo e **apenas re-arquivar** o PDF existente;
  - `archived` → nada a fazer.
- Regra dura: **o caminho de assinatura só é alcançável a partir de `signature_state=none`.**
- Aceite: teste que simula "assinou, falhou o arquivamento" → o retry **não** chama a assinatura de novo, apenas re-arquiva; contagem de assinaturas permanece 1.
- Evidência: `backend/tests/test_retry_no_double_sign.py` (TDD).

**T2.3 — Validação de `event.origin` no embed (config-driven, não hardcoded)**
- Arquivo: `frontend/src/app/patients/[id]/prescriptions/MemedEmbed.tsx`.
- **Correção da rodada 1:** o origin de produção **é desconhecido** (credenciais de parceiro pendentes) e o iframe pode não vir de `partners.memed.com.br`. Hardcodar um origin não verificado pode **quebrar o fluxo** ou dar **falsa sensação de validação**.
- Implementação: allowlist **config-driven** (env, ex.: `MEMED_ALLOWED_ORIGINS`). Em homolog, permitir o origin conhecido. **Só ativar o enforcement** depois de observar o origin real do tráfego; até lá, **logar** (não bloquear).
- Aceite: teste com origin na allowlist → processa; com origin fora → **ignora** (e, antes do enforcement, apenas registra).

**T2.4 — BirdID: distinguir token expirado de falha de assinatura**
- BirdID: token válido numa janela de **1–12h** e as **falhas não têm código de API** (só mensagem de UI).
- **Correção da rodada 1:** sem saber **quando** o token foi emitido, "expirado" e "falha de assinatura" são **indecidíveis**. Passar a **registrar localmente o instante de emissão** do token e sua validade esperada.
- Regra: se o instante atual excede a emissão + validade → tratar como **expirado** (pedir novo token, sem marcar falha); senão → **falha de assinatura** → `failed` com motivo legível.
- Aceite: teste cobrindo os dois casos **com controle do relógio** (não só o `FakeMemedClient` feliz) — a ambiguidade real precisa ser exercitada.

### F3 — PDF: retenção, storage, backup e restore (C4)

**T3.1 — Retenção documentada e aplicada**
- Definir e documentar a política de retenção do PDF assinado. (A retenção da Memed **não foi encontrada** na doc — assumir que é nossa.)
- Aceite: doc + teste de que o blob sobrevive ao ciclo normal e é removido no erasure cascade.

**T3.2 — Backup completo + `AGE_PUBKEY` + guarda da chave privada**
- `deploy/backup/backup.sh` já cobre `/data/documents` + dump clínico + keystore, mas o `.env` vivo tem **`AGE_PUBKEY` vazio** e o `compose.yaml` raiz (o deploy real) **não tem serviço de backup**.
- **Correção da rodada 1:** preencher a chave pública **não basta** — o restore (T3.3) precisa da **chave privada (identity) do age**, que não é backup do mesmo jeito que a pública. Definir explicitamente **onde a private key vive**, como é guardada (fora do host que ela protege) e **quem** pode rodar o restore. Chave privada **nunca** entra em `.env` versionado, log ou artefato de backup cifrado pela própria chave.
- Aceite: um ciclo de backup roda e produz artefato cifrado verificável **e** existe um procedimento de recuperação da private key, documentado e com o guardião nomeado.
- **[ORQ]** a posse/guarda da private key é do orquestrador/owner, não do worker.

**T3.3 — Ensaio de restore (obrigatório) [ORQ]**
- **Correção da rodada 1:** o aceite exige infra real (VPS) que o worker não acessa — e, como ainda não há prescrição assinada **de verdade**, a evidência será contra **artefato não-produção** (homolog/fake). Isso deve estar **explicitado**, não implícito.
- Passos: restaurar banco + blobs + keystore num ambiente descartável → abrir um PDF arquivado.
- Aceite: **evidência do restore** (log + hash do PDF recuperado) em `.omo/evidence/`, com a nota explícita de que o artefato é não-produção.
- Execução real na VPS: **[ORQ]**.

### F4 — Observabilidade e abuso (C5)

**T4.1 — Filtro sistêmico de redação de log**
- `backend/app/core/log_handler.py:44-58` publica a **mensagem crua** no Redis/DB; hoje a proteção é só por call-site. Residual conhecido: `memed_client.py:205` loga os **64 primeiros chars da URL do PDF**.
- **Antes de "limpar o call-site":** verificar o **formato real** da URL — se o parâmetro de assinatura não estiver nos 64 primeiros chars, a "limpeza" é cosmética e não protege nada. A verificação precede a correção.
- Backstop no handler (padrões: chaves, tokens, assinaturas de URL), **com cuidado contra over-redaction**: a redação não pode mascarar o que é necessário para diagnosticar. Preservar campos de diagnóstico (ids, códigos de status).
- Aceite: teste que injeta um segredo no log e verifica que ele **não** chega ao destino; teste de que um payload legítimo **não** é redigido em excesso.
- Evidência: `backend/tests/test_log_redaction.py` estendido (TDD).

**T4.2 — Auditoria de emissão com origem**
- `routers/prescriptions.py:98-108` não registra `ip_address`/`user_agent` (o share-link externo já registra).
- **Correção da rodada 1:** IP e user-agent são **PII**. Registrar a política de retenção e a base de consentimento desses campos, coerente com o GDPR/DPIA do projeto; não reter indefinidamente.
- Aceite: evento de auditoria traz IP e user-agent, e a retenção desses campos está documentada.

**T4.3 — Rate limit nas rotas de escrita**
- Hoje só auth (`auth.py:38-39,87`). Aplicar a `memed-session` e `capture`.
- Aceite: teste que estoura o limite e recebe 429.

**T4.4 — Créditos: visibilidade operacional**
- A Memed **não expõe API de consumo**; os créditos são da Soluti/BirdID (saldo no app "Meu Plano").
- Contador interno **de prescrições assinadas** (não de tentativas) + aviso no painel admin apontando para o "Meu Plano". **Sem scraping.**
- **Correção da rodada 1:** o contador deve se apoiar em `signature_state` (T2.2) para **não** contar retry como nova emissão — senão subconta o consumo real sempre que houver retry.

### F5 — Placeholders reversíveis de distribuição (C7)

**T5.1 — `deployment_mode`**
- Config com `personal` (default) | `clinic` | `multi_tenant`. Apenas `personal` é implementado.
- **Correção da rodada 1:** `clinic` e `multi_tenant` **não** podem ser aceitos passivamente como no-op silencioso — **rejeitar** (falhar explicitamente) qualquer valor não implementado, para que ninguém os ative achando que funcionam.
- Aceite: default `personal`; valores não implementados **erram de forma clara**; testes existentes intactos.

**T5.2 — Flag de política de emissão**
- Default `linked_user` (comportamento atual: só o user vinculado ao Prescritor emite); alternativa `any_admin`. Lida pelo gate backend.
- Aceite: com o default, **nenhuma** mudança de comportamento (teste de regressão explícito); teste para `any_admin`.
- Evidência: `backend/tests/test_emission_policy_flag.py` (TDD).

**T5.3 — Pontos de extensão de termos/telemetria**
- Apenas hooks, **desligados por padrão**. O front já tem telemetria Umami opt-in e consentimento GDPR — não reaproveitar como "deployment mode".

### F6 — Deploy na VPS SP + runbook de go-live (C6)

**T6.1 — Deploy em homolog na VPS [ORQ]**
- Migração, env, stack saudável; **sem** credenciais de produção.
- Worker **não** tem acesso à VPS: entrega o script, o runbook e a **evidência de dry-run local equivalente**. A execução na VPS é do orquestrador.
- Aceite (worker): script idempotente + dry-run local passando. Aceite (orquestrador): stack saudável na VPS.

**T6.2 — Smoke ponta a ponta em homolog [ORQ]**
- Fluxo: prescritor → prescrição → captura → PDF arquivado.
- Aceite (worker): o smoke roda localmente contra o stack local (evidência anexada). Aceite (orquestrador): o mesmo smoke na VPS.

**T6.3 — Runbook de go-live (gated, separado)**
- Documento com: pré-requisitos (credenciais de produção + BirdID + VPS), passos, verificações, **revalidação de `check-key`/dados de referência em produção** e **critério de rollback**.
- Deve ser **executável por outra pessoa** (o orquestrador): cada passo com comando, resultado esperado e o que fazer se falhar.
- Só é executado quando o owner fornecer as credenciais. **O worker não assume que elas existem.**

### F7 — Testes e evidência (C8)

- **TDD:** T0.1 (guarda), T0.3 (migração), T1.2 (sync erro), T2.1 (transição `failed`), T2.2 (retry sem dupla assinatura), T2.4 (token BirdID), T4.1 (redação), T4.3 (rate limit), T5.2 (flag). — lista coerente com as tarefas que declaram teste.
- **Tests-after:** T1.1 (health), T2.3 (origin — e2e), UI admin, T4.2/T4.4, runbook, docs.
- **Regressão:** **≥322** testes backend e **≥5** e2e continuam verdes (o plano **adiciona** testes; o piso não pode ser lido como teto); `tsc` limpo.
- Evidência em `.omo/evidence/`.

---

## 5. Cobertura obrigatória (checklist do owner)

- [ ] Guarda fail-closed em `_guard_production` (+ `AGE_PUBKEY` + coerência de base/script) e `MEMED_ENVIRONMENT` consistente — **F0**
- [ ] `failed` realmente setado (transação separada), com retry alcançável e **sem dupla assinatura** — **F2 T2.1/T2.2**
- [ ] `upsert_prescriber` não engole mais erro + superfície de health — **F1 T1.1/T1.2**
- [ ] Migrações Alembic para `failure_reason`/`signature_state`/`sync_status` — **F1b T0.3**
- [ ] Filtro sistêmico de redação (incl. formato real da URL do PDF) — **F4 T4.1**
- [ ] Auditoria de emissão com `ip_address`/`user_agent` (+ retenção/PII) — **F4 T4.2**
- [ ] Rate limit em `memed-session` e `capture` — **F4 T4.3**
- [ ] Backup: `AGE_PUBKEY`, serviço no compose raiz, **guarda da chave privada** e **ensaio de restore** — **F3 T3.2/T3.3**
- [ ] Placeholders reversíveis, default `personal`, valores não implementados rejeitados — **F5**
- [ ] Go-live como runbook separado e gated, executável por terceiros — **F6 T6.3**

## 6. Riscos

| Risco | Mitigação |
|---|---|
| Credenciais de produção não existem (form. de parceiro ~48h) | Tudo construído em dry-run/homolog; go-live gated (decisão A) |
| BirdID falha sem código de API | Rastrear emissão do token localmente (§T2.4) + estado `failed` com motivo |
| **Dupla assinatura no retry** (crédito + validade legal) | `signature_state` + proibição de re-assinar (`signed`) (§T2.2) |
| Rollback desfazendo a marcação de `failed` | Persistir em transação separada (§T2.1) |
| Chave privada do age perdida → backup irrecuperável | Guarda explícita fora do host + guardião nomeado (§T3.2) |
| Sem API de consumo de créditos | Contador por `signature_state` + aviso no admin |
| Retenção de PDF não documentada pela Memed | Política própria, documentada e testada |
| Over-redaction mascarando diagnóstico | Teste de não-redação excessiva (§T4.1) |
| Regressão na captura síncrona ao introduzir `failed` | TDD na transição + suíte completa antes do merge |

## 7. Critério de aceitação

1. Emissão **assinada de verdade** com o BirdID produz prescrição com PDF arquivado criptografado; falhas viram `failed` com motivo; **retry nunca re-assina**.
2. Guarda de produção aborta configuração insegura (incl. `AGE_PUBKEY` vazio).
3. Nenhum segredo em log (backstop testado, sem over-redaction).
4. Backup roda, a chave privada tem guarda e o **ensaio de restore** recupera um PDF arquivado.
5. Stack na VPS SP saudável com smoke ponta a ponta em homolog; runbook de go-live pronto, completo e **não executado**.
6. Placeholders presentes com default `personal`; valores não implementados rejeitados.
7. **≥322 testes backend + ≥5 e2e** verdes; `tsc` limpo.

---

## 8. Registro da revisão (rodada 1 → correções)

| # | Achado | Correção nesta revisão |
|---|---|---|
| **B1** | T2.1 marcava `failed` no caminho que sofre rollback → o registro seria desfeito e a receita voltaria a `draft` | T2.1 reescrito: persistir em **transação/sessão separada** após a exceção propagar |
| **B2** | T2.2 "idempotente" só com lock otimista; retry após "assinou mas não arquivou" re-assinaria → duplicidade legal + duplo crédito | T2.2 reescrito: `signature_state` (`none`/`signed`/`archived`) + proibição de re-assinar; reconciliação em vez de nova assinatura |
| M1 | Faltava migração Alembic para os novos estados persistidos | Nova fase **F1b / T0.3** |
| M2 | `AGE_PUBKEY` sem a chave **privada** → restore inalcançável/circular | T3.2 ampliado: guarda, localização e guardião da private key |
| M3 | Indistinguível "token expirado" vs "falha de assinatura" | T2.4: registrar o instante de emissão do token; teste com controle de relógio |
| M4 | Aceites de F3/F6 exigiam VPS que o worker não acessa | Marcados **[ORQ]**; aceite do worker = dry-run local + scripts; execução real do orquestrador |
| M5 | Origins de `postMessage` sem valor de produção conhecido | T2.3: allowlist config-driven; enforcement só após observar o tráfego real |
| M6 | Premissa do `check-key` tratada como não verificada | T1.1: registrado que **foi verificado em homolog na Fase 1**; revalidação em produção vai para o runbook |
| M7 | Guarda fail-closed não cobria `AGE_PUBKEY` (já quebrado) nem coerência de base/script | T0.1 ampliado |
| m1 | Regressão fixada em "322/5" contradizia os testes adicionados | Passa a **≥322 / ≥5** (§F7, §7) |
| m2 | Lista TDD/Tests-after incoerente | §F7 reescrita, alinhada às tarefas |
| m3 | Valores aceitos de `MEMED_ENVIRONMENT` não definidos | T0.2: `integration` \| `production`, validados na guarda |
| m4 | Contador de créditos subcontava em retry | T4.4: contar por `signature_state` |
| m5 | Redação podia mascarar diagnóstico; limpeza do call-site podia ser cosmética | T4.1: verificar o formato real da URL antes; teste de não-redação excessiva |
| m6 | IP/user-agent são PII sem política de retenção | T4.2: retenção/consentimento documentados |
| m7 | Ensaio de restore só com artefato não-produção | T3.3: explicitado |
| m8 | `deployment_mode` aceitaria valores não implementados como no-op | T5.1: rejeitar valores não implementados |