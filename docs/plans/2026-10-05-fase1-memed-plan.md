# 2026-10-05-fase1-memed-plan - Work Plan

## TL;DR (For humans)

**O que você vai ter:** Um domínio de prescrição dentro do OpenAvisio, integrado à **Memed — Sinapse Prescrição**. O prescritor configurado monta a receita no módulo oficial da Memed embutido na tela do paciente; o OpenAvisio mantém um rascunho com **autosave** e concorrência otimista, obtém um `data-token` fresco a cada emissão, e quando a Memed emite a receita o backend baixa o **PDF assinado** pelo endpoint oficial (`GET /prescricoes/{id}/url-document/full`), arquiva-o **criptografado** (envelope por paciente) como `PrescriptionDocument`, e o expõe numa seção **"Prescrições"** dedicada. A Memed resolve numeração SNCR/ANVISA e assinatura ICP-Brasil (BYOC, BirdID do prescritor).

**Por que esta abordagem:** a decisão de usar a Memed está travada e substitui o desenho antigo de integração direta ao SNCR. O evento `prescricaoImpressa` é apenas o **gatilho**; o caminho oficial para o PDF é o endpoint de backend. Escondemos o cliente Memed atrás de um `Protocol` com `FakeMemedClient` — inclusive o **download do PDF** — para que **nenhum teste toque a rede**. Não abrimos CNPJ, não construímos motor de assinatura nem gerador de PDF.

**O que NÃO vai fazer:** não integra o SNCR direto, não assina nem gera PDF por conta própria, não implementa layout RDC/QR, não cria multi-prescritor/SaaS, não faz OCR de receitas, não altera o pipeline de `Document`, e não chama a Memed real em testes. Não loga token, `api-key`, `secret-key` nem CPF.

**Esforço:** Grande (13 tarefas de implementação + 4 de verificação final).
**Risco:** Alto — o contrato de eventos `postMessage` da Memed, a disponibilidade da homologação e o número SNCR não documentado são externos; e emitir receitas contradiz o posicionamento "não é dispositivo médico".
**Decisões já travadas pelo owner (A/A/A):** (1) PDF em seção dedicada `PrescriptionDocument`, sem tocar Documentos/OCR; (2) hard-delete local com tombstone no apagamento de paciente; (3) só o User vinculado ao Prescriber configurado pode emitir.
**Revisão de alta precisão:** este plano já incorpora os apontamentos do **Momus** e de uma revisão independente (**Oracle**); a lista de críticas e respostas está em "Crítica incorporada", ao final.

Próximo passo: revisar este plano. Para executá-lo, abra uma **sessão de worker separada** com `$start-work 2026-10-05-fase1-memed-plan` — esta sessão de planejamento não executa nada.

---

> TL;DR (machine): Large/High. Phase 1 = prescription domain (4 models + 1 migration) + versioned autosave + Memed client Protocol/fake (incl. `download_pdf`) + prescriber ensure/token + signed-PDF capture via `url-document/full` + encrypted archival + prescriptions API + postMessage bridge frontend + admin prescriber UI + erasure/audit; no live Memed calls in tests, no SNCR-direct, no own PDF/signer.

## Scope

### Must have
- **Domínio/persistência:** `Prescriber`, `Prescription`, `PrescriptionItem`, `PrescriptionDocument`; uma única revisão Alembic sobre o head `g3b4c5d6e7f8`.
- **Máquina de estados** `draft → issued` (+ `failed`, `deleted`) com invariantes e **autosave versionado** (concorrência otimista com compare-and-swap, `409` em escrita obsoleta).
- **Porta `MemedClient` (Protocol) + implementação HTTP (`httpx`) + `FakeMemedClient`**, cobrindo: `check_key`, `cidades`, `especialidades`, `create_prescriber`, `get_prescriber` (token), `get_prescription_pdf_url(token, id)`, `get_digital_link(token, id)` e **`download_pdf(url)`** (o download fica atrás da porta, para o fake servir bytes sem rede).
- **Adaptador defensivo do evento `prescricaoImpressa`** (payload não verificado) que extrai o id da prescrição por chaves candidatas e falha de forma tipada e recuperável.
- **Serviço de prescritor** idempotente por `external_id`, `data-token` fresco, cache de cidades/especialidades.
- **Captura e arquivamento** do PDF assinado: obter URL com token fresco, baixar via porta, encriptar com a KEK do paciente, gravar em `PrescriptionDocument` (com limpeza do blob em falha), expor via API.
- **API de prescrições:** CRUD, autosave versionado, sessão Memed, capture, deleted, retry e download do PDF; tudo atrás de `require_patient_access`.
- **Frontend:** seção "Prescrições", lista + editor de rascunho com autosave, embed do módulo Memed e **ponte `postMessage`** (`core:moduleInit`, `prescricaoImpressa`, `prescricaoExcluida`), e rota-proxy de download do PDF.
- **UI admin de prescritor** (cadastro único, CPF criptografado).
- **Config/segredos:** `MEMED_*` em `settings`/`.env`/`compose`; supressão de logging DEBUG do `httpx`/`httpcore`; **nunca logar token, `api-key`, `secret-key` nem CPF** (enforçado por teste com sentinela).
- **Testes** unitários do domínio e do cliente Memed (fake + `httpx.MockTransport`), integração do fluxo de emissão, redação de logs, erasure — **100% offline**.
- **Erasure/auditoria:** prescrições no cascade de apagamento de paciente; PII do prescritor anonimizada no apagamento de usuário; entradas de auditoria em emitir/arquivar/excluir.

### Should have
- Cache leve (processo) das respostas `cidades`/`especialidades` para não bater na Memed a cada cadastro.
- Máscara de CPF na UI/API (`cpf_last4`) e redação em logs.
- Tratamento explícito de `prescricaoExcluida` marcando `deleted` (sem apagar o PDF arquivado).

### Could have
- Reimpressão do PDF a partir do `PrescriptionDocument` já arquivado (sem novo download).
- Link digital da receita (`link` + `codigo_desbloqueio`) exibido ao cuidador.

### Must NOT have (guardrails)
- Nenhuma chamada HTTP real à Memed em testes (`FakeMemedClient`/`httpx.MockTransport` apenas).
- Nenhuma integração direta ao SNCR/ANVISA; nenhum motor de assinatura; nenhuma geração de PDF/layout RDC/QR próprios.
- Nenhuma abertura de CNPJ; nenhum multi-prescritor/SaaS.
- Nenhuma alteração no comportamento de upload/OCR/extração/verificação do `DocumentReference`; nenhum `ocr_stage.delay` para PDFs de receita.
- Nenhum locale novo além de `pt`, `en`, `de`.
- Nenhum log de `data-token`, `api-key`, `secret-key`, CPF completo ou conteúdo do PDF.
- Não inventar um campo de número SNCR na API; não inventar endpoints da Memed além dos documentados.

### Data model

Todos os modelos seguem `backend/app/models/base.py:11-25`: `BaseModel` (id UUID, `created_at`, `updated_at`, `is_deleted`) e `OwnedResource` (+ `owner_id`). Enums como `StrEnum` no próprio arquivo do modelo, persistidos como `String(n)` — **nunca** ENUM nativo do Postgres (padrão `backend/app/models/share_link.py:19-39`).

**`Prescriber`** (`prescribers`, `BaseModel`) — singleton por Organização, **id fixo** `00000000-0000-0000-0000-000000000001` (`PRESCRIBER_SINGLETON_ID`) para forçar uma única linha:
| Coluna | Tipo | Notas |
|---|---|---|
| `user_id` | UUID FK users.id, nullable, index | User vinculado autorizado a emitir (decisão 3) |
| `external_id` | String(64), unique, not null | estável = `str(id)` (setado explicitamente no create) |
| `given_name` / `family_name` | String(120) | `nome`/`sobrenome` da Memed |
| `cpf_encrypted` | Text, nullable | `encrypt_setting` (KEK mestre); nullable para permitir anonimização |
| `cpf_last4` | String(4), nullable | exibição/máscara |
| `birth_date` | Date, nullable | `data_nascimento` (RDC 1000/25) |
| `board_code` / `board_number` / `board_state` | String(10)/String(30)/String(2) | CRM etc. |
| `email` / `phone` / `sex` | String(256)/String(30)/String(1), nullable | opcionais |
| `city_id` / `specialty_id` | Integer, nullable | IDs cacheados da Memed |
| `memed_user_id` / `memed_status` | String(64)/String(30), nullable | `data.id` e `Ativo`/`Em análise`/`Inativo` |

**`Prescription`** (`prescriptions`, `OwnedResource`) — por paciente:
| Coluna | Tipo | Notas |
|---|---|---|
| `patient_id` | UUID FK patients.id, index | |
| `prescriber_id` | UUID FK prescribers.id, index | |
| `status` | String(20), default `draft`, index | `PrescriptionStatus` |
| `version` | Integer, default 1, not null | concorrência otimista (compare-and-swap) |
| `memed_prescription_id` / `memed_prescription_uuid` | String(64), nullable | preenchidos no capture |
| `issued_at` | DateTime(timezone=True), nullable | write-once |
| `notes` | Text, nullable | anotações locais do cuidador |
| `deleted_by_memed_at` | DateTime, nullable | `prescricaoExcluida` |
| `items` | relationship, cascade all/delete-orphan | snapshot/rascunho local |
| `document` | relationship uselist=False, cascade all/delete-orphan | |

> `Prescription.signed` foi **removido** (redundante com `status == issued` + existência de `PrescriptionDocument`). O campo `PrescriptionDocument.signed` é **informativo** (vem do evento, que é não verificado); o artefato arquivado é o PDF de `url-document/full`, e `issued` **não** depende de `signed == True`. `is_deleted` (soft-delete ORM) é o descarte de rascunho pelo usuário; `status == deleted` é a exclusão **na Memed** (`prescricaoExcluida`). São conceitos distintos e ambos filtrados na listagem.

**`PrescriptionItem`** (`prescription_items`, `BaseModel`): `prescription_id` FK index, `medication_name` String(512), `posology` Text, `quantity` String(64), `sort_order` Integer default 0. É um **rascunho/anotação local**; a fonte autoritativa do conteúdo emitido é o PDF assinado da Memed (não se afirma que o snapshot == PDF).

**`PrescriptionDocument`** (`prescription_documents`, `BaseModel`): `prescription_id` FK unique, `file_name` String(512), `content_type` String(100) default `application/pdf`, `size` BigInteger, `storage_path` String(1024), `hash` String(64) (sha256 do que foi arquivado), `encrypted_dek` LargeBinary, `kek_version` SmallInteger default 1, `signed` Boolean default False (do evento), `memed_prescription_id` String(64), `digital_link` String(1024) nullable, `unlock_code` String(16) nullable, `captured_at` DateTime.

**`Patient` — ajuste obrigatório (checagem humana #3):** o `setPaciente` exige, no checklist de credenciais de produção da Memed, **nome+sobrenome, e-mail, telefone, data de nascimento e CPF** do paciente. O modelo `Patient` atual não tem esses campos → **adicionar na mesma migração**, em `patients` (nullable): `cpf_encrypted` (Text), `cpf_last4` (String(4)), `birth_date` (Date), `email` (String(256)), `phone` (String(30)). CPF cifrado com a **KEK do paciente** (`app.core.patient_keys`), mascarado em API/logs. Enviar tudo no `setPaciente`.

**Enums (StrEnum):** `PrescriptionStatus = draft | issued | failed | deleted`. `MemedEnvironment` fica só em config (`integration | production`).

**Migração:** uma revisão nova, `down_revision = "g3b4c5d6e7f8"`, criando as quatro tabelas e seus índices/constraints.

### Contracts / endpoints

**Porta `MemedClient` (Python `Protocol`)** — `backend/app/services/prescriptions/ports.py`:
- `check_key() -> bool`
- `list_cities(q: str | None) -> list[ReferenceItem]`
- `list_specialties(q: str | None) -> list[ReferenceItem]`
- `create_prescriber(payload: dict) -> PrescriberResult`
- `get_prescriber(external_id: str) -> PrescriberResult`
- `get_prescription_pdf_url(token: str, memed_prescription_id: str) -> str`
- `get_digital_link(token: str, memed_prescription_id: str) -> DigitalLinkResult`
- `download_pdf(url: str) -> bytes`

`PrescriberResult` / `DigitalLinkResult` são dataclasses com `token`/`codigo_desbloqueio` marcados `field(repr=False)`; `PrescriberResult` nunca é serializado por Pydantic.

**Endpoints de prescritor (admin, `require_admin`):**
- `GET /api/admin/prescriber` → dados com CPF mascarado.
- `PUT /api/admin/prescriber` → upsert do singleton (`PRESCRIBER_SINGLETON_ID`); ensure idempotente na Memed; CPF criptografado (obrigatório no create, preservado se omitido no update).
- `GET /api/admin/memed/reference-data?kind=cities|specialties&q=` → IDs cacheados.

**Endpoints de prescrição (`/api`, `require_patient_access`):**
- `GET /api/patients/{patient_id}/prescriptions` (filtra `is_deleted=False` **e** `status != deleted`)
- `POST /api/patients/{patient_id}/prescriptions` (cria `draft`; `contribute`)
- `GET /api/prescriptions/{id}`
- `PATCH /api/prescriptions/{id}` (autosave; body `{version, notes?, items?}`; `items` presente **substitui a lista inteira**; `409 {detail:{code:"stale_version", current_version:N}}`; `contribute`)
- `DELETE /api/prescriptions/{id}` (só em `draft`: `is_deleted=True`; `contribute`)
- `POST /api/prescriptions/{id}/memed-session` (retorna `data-token` fresco + script URL + payload do paciente; **só o Prescriber vinculado**; `Cache-Control: no-store`)
- `POST /api/prescriptions/{id}/capture` (body: payload cru do evento `prescricaoImpressa`; backend faz o parse defensivo, baixa o PDF e arquiva; **só o Prescriber vinculado**)
- `POST /api/prescriptions/{id}/memed-deleted` (body: payload cru de `prescricaoExcluida`; marca `status=deleted`)
- `POST /api/prescriptions/{id}/retry` (de `failed` volta a `draft`; `contribute`)
- `GET /api/prescriptions/{id}/document` (stream do PDF decriptado; resolve `patient_id` via `Prescription`)

### File changes by module

**Backend — domínio/persistência**
- `backend/app/models/prescription.py` (novo: 4 modelos + 2 StrEnum + `PRESCRIBER_SINGLETON_ID`)
- `backend/app/models/__init__.py` (registrar e adicionar ao `__all__`)
- `backend/alembic/versions/<newhash>_add_prescriptions.py` (novo; `down_revision = "g3b4c5d6e7f8"`)
- `backend/app/core/config.py` (campos `memed_*`)

**Backend — serviços Memed**
- `backend/app/services/prescriptions/__init__.py` (novo)
- `backend/app/services/prescriptions/ports.py` (Protocol + dataclasses de resultado com `repr=False` nos segredos)
- `backend/app/services/prescriptions/memed_client.py` (httpx; querystring `api-key`/`secret-key`; JSON:API; `download_pdf`; **suprime loggers `httpx`/`httpcore`**)
- `backend/app/services/prescriptions/fakes.py` (`FakeMemedClient` determinístico, grava chamadas, serve bytes de PDF sem rede)
- `backend/app/services/prescriptions/state.py` (máquina de estados pura + `InvalidTransition`/`StalePrescription`)
- `backend/app/services/prescriptions/prescriber.py` (ensure idempotente, token fresco, cache de referência)
- `backend/app/services/prescriptions/events.py` (`parse_prescricao_impressa`/`parse_prescricao_excluida` defensivos)
- `backend/app/services/prescriptions/archive.py` (captura + encriptação + gravação com limpeza do blob em falha)

**Backend — API**
- `backend/app/schemas/prescription.py` (Pydantic v2; espelha `schemas/medication.py`)
- `backend/app/routers/prescriptions.py` (rotas de prescrição + dependência de injeção da porta)
- `backend/app/routers/prescriber.py` (rotas admin do prescritor + reference-data)
- `backend/app/main.py` (registrar os dois routers em `prefix="/api"` e `/api/admin`)

**Backend — governança**
- `backend/app/services/erasure.py` (cascade de prescrições via join + blobs + purge de auditoria; anonimização da PII do prescritor no `erase_user`)
- `backend/app/services/governance.py` (garantir que prescrições **não** entram em `CATEGORY_MODELS`)

**Config/deploy**
- `.env.example` (documentar `MEMED_*`)
- `compose.yaml` (passar `MEMED_*` para backend/worker)
- `deploy/docker-compose.prod.yml` (idem)
- `.env` (já contém as chaves; sem mudança de conteúdo)

**Frontend**
- `frontend/src/lib/patientSections.ts` (nova seção `Prescriptions`; importar `FileSignature` de `lucide-react`)
- `frontend/src/app/patients/[id]/prescriptions/page.tsx` (lista + shell)
- `frontend/src/app/patients/[id]/prescriptions/PrescriptionList.tsx`
- `frontend/src/app/patients/[id]/prescriptions/PrescriptionEditor.tsx` (autosave debounced)
- `frontend/src/app/patients/[id]/prescriptions/MemedEmbed.tsx` (client; carrega script, ponte `postMessage`)
- `frontend/src/app/api/prescriptions/[id]/document/route.ts` (proxy binário autenticado do PDF)
- `frontend/src/lib/api.ts` (wrappers tipados; capture/memed-deleted via **server actions**)
- `frontend/src/messages/pt.json` / `en.json` / `de.json` (namespace novo de prescrições)
- `frontend/src/app/admin/prescriber/page.tsx` (UI admin de cadastro do prescritor)
- `frontend/src/components/layout/AppSidebar.tsx:253` (link admin, junto da nav admin existente)

**Testes**
- `backend/tests/test_prescription_models.py`
- `backend/tests/test_prescription_state.py`
- `backend/tests/test_memed_client.py`
- `backend/tests/test_memed_events.py`
- `backend/tests/test_prescriber_service.py`
- `backend/tests/test_prescription_archive.py`
- `backend/tests/test_prescription_api.py`
- `backend/tests/test_prescription_erasure.py`
- `backend/tests/test_log_redaction.py`
- `frontend/e2e/prescriptions.spec.ts` (stub do módulo Memed via `page.route`)

### Riscos
- **Regulatório (alto):** emitir receitas contradiz `docs/regulatory-positioning.md:26-29`. Mitigação: ADR + nota explícita; revisão formal recomendada; não é aconselhamento jurídico.
- **Número SNCR não documentado na API de integração:** não há campo conhecido; pode estar só no PDF. Ver "Decisões que precisam de checagem humana".
- **Disponibilidade da homologação:** indisponível 0h–6h (seg–sex) e fins de semana — impossibilita e2e manual nesses horários.
- **Payload/URL do PDF:** o payload de `prescricaoImpressa` é não verificado e a URL de `url-document/full` pode expirar. Mitigação: adaptador defensivo + token fresco na hora + um retry em 401/403/404 + `failed` com `retry` explícito.
- **Eventos não verificados:** `core:allmodulesareready` não existe na doc nem no fonte; `core:moduleShow` existe só no fonte. O plano depende apenas de `core:moduleInit`, `prescricaoImpressa` e `prescricaoExcluida`; `core:moduleHide` é tratado como opcional (não observado na lista validada em homolog).
- **CSP/iframe cross-origin:** a Memed precisa permitir nosso domínio como pai do iframe; validar no sandbox.
- **Vazamento de segredos:** token/CPF em logs (incl. logging DEBUG do `httpx`/`httpcore`). Mitigação: supressão de loggers + teste com sentinela.
- **CPF do paciente:** `Patient` não tem campo CPF; o módulo Memed coleta/confirma o CPF do paciente. Ver decisões de checagem humana.
- **Ambiente de teste:** exige Postgres `vaultdb_test`; sem respx — usar `httpx.MockTransport`.
- **Wiring de env:** `compose.yaml` hoje não passa `MEMED_*`; sem isso o deploy da VPS falha silenciosamente.
- **Retenção:** prescrições emitidas são registro legal; a categoria de retenção não pode purgá-las automaticamente.

### Decisões que precisam de checagem humana
1. **Número SNCR:** confirmar com a Memed se há campo de API para o número oficial (ou se ele só aparece no PDF). O plano **não** assume um campo de SNCR.
2. **Payload real de `prescricaoImpressa` e autorização da URL do PDF:** validar no sandbox; o adaptador defensivo cobre a incerteza, mas as chaves candidatas devem ser confirmadas.
3. **CPF do paciente para a receita:** confirmar se a Memed exige CPF do paciente e como o módulo o coleta (OpenAvisio não armazena CPF de paciente).
4. **Credenciais de produção** e janela de onboarding (até 48h úteis) + custo/ToS.
5. **Limites de taxa:** não documentados; confirmar com a Memed.
6. **Revisão jurídica/regulatória** da emissão de receitas dentro do OpenAvisio.
7. **CSP:** confirmar que o domínio público pode embutir o iframe da Memed.

### Respostas às checagens humanas (verificado na doc oficial, 89/89 páginas, 2026-10-05)
1. **Número SNCR:** **não existe campo na API da Memed** — "SNCR" aparece 0× na doc inteira; o número sai no **cabeçalho/rodapé do PDF**. O payload de `prescricaoImpressa` traz por item só o booleano `controle_especial`. → o plano está correto em **não** assumir campo de SNCR.
2. **Payload + URL do PDF:** o payload de `prescricaoImpressa` está **documentado** (`prescriptionData.medicamentos[]`); a URL do PDF é `GET /v1/prescricoes/{id}/url-document/full?token=<token>` — **confirmado**, `token` obrigatório. O adaptador defensivo segue justificado para as chaves do *id* da prescrição.
3. **CPF do paciente:** `setPaciente` exige só `idExterno`, `nome`, `sexo`; **CPF é opcional no comando**, mas o **checklist de produção exige** nome+sobrenome, e-mail, telefone, data de nascimento e **CPF**. → **adicionar campos de contato/CPF ao `Patient`** (e enviá-los no `setPaciente`).
4. **Credenciais de produção:** exigem **formulário de parceiro** (`/docs/obter-credenciais`) + cadastro do prescritor + `setPaciente` completo + os 2 eventos; sujeito a revisão. Custo/ToS **não publicados** — confirmar.
5. **Limites de taxa:** **sem limite documentado** — a doc afirma "acesso **ilimitado** à API" para parceiros.
6. **Revisão regulatória:** entra agora (decisão do owner).
7. **CSP/embed:** possível; se ocorrer `Blocked a frame with origin`, a página que embute o módulo deve ter **`Referrer-Policy: strict-origin-when-cross-origin`** (não `same-origin`). O OpenAvisio hoje não define `Referrer-Policy` global → o default moderno já é adequado.

## Verification strategy
> Zero intervenção humana — toda verificação é executada por agente.
- **Test decision:** **TDD** para a máquina de estados, o adaptador de eventos e a porta/cliente Memed (lógica pura e parsing, rápidos); **tests-after** para router, arquivamento, erasure e frontend.
- **Frameworks:** `pytest` + `httpx.ASGITransport` (harness existente em `backend/tests/conftest.py:41-79`); cliente Memed testado com `FakeMemedClient` **e** `httpx.MockTransport` (sem rede). Frontend: `pnpm exec tsc --noEmit`, `pnpm build`, e Playwright (`frontend/playwright.config.ts`) com o script Memed interceptado via `page.route('**/sinapse-prescricao*.js')` e `page.addInitScript` para `window.MdHub`/`MdSinapsePrescricao`.
- **Nenhum teste pode tocar a rede.** Nenhum teste usa credencial real da Memed. O download do PDF é servido pelo `FakeMemedClient` (por isso `download_pdf` fica na porta).
- **Evidence:** `.omo/evidence/task-<N>-2026-10-05-fase1-memed-plan.<ext>` — capturar o comando exato e a saída; um resumo passando é uma alegação até a saída do comando ser anexada.

## Execution strategy
### Parallel execution waves
- **Wave 1 (fundação):** 1 (docs/ADR), 2 (persistência+migração+config), 3 (máquina de estados).
- **Wave 2 (núcleo Memed):** 4 (porta+cliente+fake), 5 (serviço de prescritor+token+referência), 6 (adaptador de eventos), 7 (captura+arquivamento+link).
- **Wave 3 (API + governança):** 8 (schemas+router+auditoria), 9 (erasure+retenção).
- **Wave 4 (frontend + admin):** 10 (wrappers+sessão+página/lista+proxy do PDF), 11 (embed+ponte), 12 (editor+autosave+capture wiring), 13 (UI admin do prescritor).
- **Wave 5:** verificação final F1–F4.

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1 | - | 2 (vocabulário usado no código) | 2 |
| 2 | - | 3,4,5,6,7,8,9,10,11,12,13 | 1 |
| 3 | 2 | 7,8,12 | 4 |
| 4 | 2 | 5,6,7 | 3 |
| 5 | 3,4 | 7,8,13 | 6 |
| 6 | 4 | 7 | 5 |
| 7 | 4,5,6 | 8 | - |
| 8 | 5,7 | 10,11,12,13 | 9 |
| 9 | 2 | - | 8 |
| 10 | 8 | 11,12 | 9 |
| 11 | 10 | 12 | 13 |
| 12 | 10,11 | - | 13 |
| 13 | 5,8 | - | 11,12 |

## Todos
> Implementation + Test = ONE todo. Never separate.

- [ ] 1. Registrar o vocabulário de prescrição, o ADR e a consequência regulatória
  What to do / Must NOT do: Criar `docs/adr/036-prescription-domain-memed.md` descrevendo Prescription/Prescriber/`PrescriptionDocument`, a divisão "a Memed numera e assina; nós armazenamos", a decisão BYOC/BirdID, as três decisões do owner e a tensão explícita entre apagamento de paciente (hard-delete) e retenção legal. Adicionar os termos ao `CONTEXT.md` (nova subseção "Prescription"). Adicionar uma nota explícita em `docs/regulatory-positioning.md` de que **emitir receitas está fora da atual alegação "não é dispositivo médico" e exige revisão formal**. Não alterar código; não reescrever termos existentes; não afirmar conformidade jurídica.
  Parallelization: Wave 1 | Blocked by: - | Blocks: 2
  References (executor has NO interview context - be exhaustive): `CONTEXT.md` (glossário, seção "Clinical data"); `docs/adr/` (último é 035, usar `036-prescription-domain-memed.md`); `docs/regulatory-positioning.md:26-29` e `:60-70`; `docs/plans/2026-10-05-prontuario-receitas-plano.md:99-130` (decisão Memed + fatos verificados); `docs/plans/_brief-fase1-memed.md` (escopo/fora de escopo).
  Acceptance criteria (agent-executable): `test -f docs/adr/036-prescription-domain-memed.md`; `grep -qi "Prescription" CONTEXT.md`; `grep -qi "not a medical device" docs/adr/036-prescription-domain-memed.md`; `grep -qi "Memed" docs/regulatory-positioning.md`; `rg -n "036" docs/adr/036-prescription-domain-memed.md` confirma o número.
  QA scenarios (name the exact tool + invocation): happy — checagem de markdown válido dos três arquivos (`npx markdownlint-cli2` se disponível, senão `grep` de headings) e nenhuma mudança em `frontend/`; failure — grep garante que o ADR **não** redefine `Caregiver`/`Patient` nem afirma conformidade legal (`! grep -qi "compliant" docs/adr/036-prescription-domain-memed.md`). Evidence `.omo/evidence/task-1-2026-10-05-fase1-memed-plan.md`.
  Commit: Y | docs(domain): add Memed prescription ADR-036 and glossary terms

- [ ] 2. Adicionar a camada de persistência de prescrições: quatro modelos, enums, migração e config
  What to do / Must NOT do: Criar `backend/app/models/prescription.py` com `Prescriber`, `Prescription`, `PrescriptionItem`, `PrescriptionDocument`, o `StrEnum` `PrescriptionStatus` e a constante `PRESCRIBER_SINGLETON_ID = UUID("00000000-0000-0000-0000-000000000001")`, conforme o "Data model" acima. `Prescriber` é `BaseModel` com id fixo (singleton); `Prescription` é `OwnedResource`; `PrescriptionItem`/`PrescriptionDocument` são `BaseModel`. `Prescriber.external_id` deve ser setado explicitamente para `str(id)`. Seguir `BaseModel`/`OwnedResource` (`backend/app/models/base.py:11-25`); `String(n)` em vez de ENUM nativo (ver `backend/app/models/share_link.py:19-39`). CPF do `Prescriber` criptografado com `app.core.encryption.encrypt_setting` (KEK mestre) + `cpf_last4`. Registrar todas as classes em `backend/app/models/__init__.py` (`__all__`). Criar `backend/alembic/versions/<newhash>_add_prescriptions.py` com `down_revision = "g3b4c5d6e7f8"`. Adicionar a `backend/app/core/config.py` os campos `memed_api_url`, `memed_script_url`, `memed_api_key`, `memed_secret_key`, `memed_environment` (default `integration`). Documentar em `.env.example` e passar as variáveis para backend/worker em `compose.yaml` e `deploy/docker-compose.prod.yml`. Adicionar também, na mesma migração, as colunas de contato/CPF em `patients` (ver "`Patient` — ajuste obrigatório" no Data model). NÃO usar ENUM nativo; NÃO adicionar uma tabela de snapshot do prescritor (o próprio `Prescriber` sobrevive); NÃO enfileirar pipeline OCR; NÃO commitar valores reais de chaves.
  Parallelization: Wave 1 | Blocked by: - | Blocks: 3,4,5,6,7,8,9,10,11,12,13
  References: `backend/app/models/base.py:11-25`; `backend/app/models/document.py:12-54`; `backend/app/models/share_link.py:19-65`; `backend/app/models/medication.py:10-28`; `backend/app/models/__init__.py:1-80`; `backend/app/core/config.py:7-105`; `backend/app/core/encryption.py:70-76`; `backend/alembic/versions/g3b4c5d6e7f8_condition_merged_into.py:7-8`; `backend/alembic/env.py:14` (`import app.models`) e `:22` (`target_metadata`); `.env.example:1-90`; `compose.yaml` (bloco de env do backend/worker).
  Acceptance criteria (agent-executable): `cd backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` sai 0; `cd backend && uv run alembic heads` mostra **um** head; `cd backend && uv run python -c "from app.models import Prescriber, Prescription, PrescriptionItem, PrescriptionDocument, PRESCRIBER_SINGLETON_ID"` sai 0; `cd backend && uv run pytest tests/test_prescription_models.py -q` passa (inclui o teste de singleton: dois upserts resultam em uma linha).
  QA scenarios: happy — reflexão de `Base.metadata.tables` contém as quatro tabelas e a migração up/down/up é limpa; failure — `down_revision` errado faz `alembic heads` mostrar >1 head; `Prescriber` com id fixo garante uma única linha. Evidence `.omo/evidence/task-2-2026-10-05-fase1-memed-plan.txt`.
  Commit: Y | feat(prescriptions): add prescription persistence models and migration

- [ ] 3. Implementar a máquina de estados e a concorrência otimista
  What to do / Must NOT do: Criar `backend/app/services/prescriptions/state.py` puro (sem SQL/HTTP) com a tabela de transições e `transition(prescription, target)` que levanta `InvalidTransition`. Transições de status: `draft→issued`, `draft→failed`, `failed→draft`, e `→deleted` (por `prescricaoExcluida`) a partir de `draft`/`failed`/`issued`. `deleted` é terminal. O descarte de rascunho pelo usuário **não** é transição de status — é `is_deleted=True` (ver todo 8). Invariantes: itens só editáveis quando `status == "draft"`; `issued_at` é write-once; `issued` exige `memed_prescription_id` e um `PrescriptionDocument`; ids da Memed são write-once. Adicionar `check_version(prescription, expected)` que levanta `StalePrescription`; a escrita atômica (compare-and-swap) fica no router/serviço com `UPDATE ... WHERE id=:id AND version=:expected` e checagem de `rowcount`. NÃO colocar HTTP nem SQL no módulo de estados.
  Parallelization: Wave 1 | Blocked by: 2 | Blocks: 7,8,12
  References: modelos do todo 2; `backend/app/routers/medications.py:28-33` (padrão de estado derivado); o "Data model" deste plano (a máquina de estados nova, não a do plano superado).
  Acceptance criteria: `cd backend && uv run pytest tests/test_prescription_state.py -q` passa a matriz completa (todo par legal permitido; todo ilegal levanta) e as invariantes.
  QA scenarios: happy — `draft→issued` com documento e id aceitos; failure — `issued→draft` levanta `InvalidTransition`; `check_version` com versão antiga levanta `StalePrescription`; editar item em `issued` levanta. Evidence `.omo/evidence/task-3-2026-10-05-fase1-memed-plan.txt`.
  Commit: Y | feat(prescriptions): add prescription state machine

- [ ] 4. Definir a porta `MemedClient`, a implementação HTTP e o fake (incluindo o download do PDF)
  What to do / Must NOT do: Criar `backend/app/services/prescriptions/ports.py` com o `Protocol` `MemedClient` e as dataclasses `ReferenceItem`, `PrescriberResult`, `DigitalLinkResult` — com `token`/`codigo_desbloqueio`/CPF marcados `field(repr=False)`. Criar `memed_client.py` com `httpx.AsyncClient`, montando **sempre** `?api-key=...&secret-key=...` e, quando aplicável, `token`; paths: `GET /sinapse-prescricao/check-key`, `GET /cidades`, `GET /especialidades`, `POST /sinapse-prescricao/usuarios` (JSON:API), `GET /sinapse-prescricao/usuarios/{id}`, `GET /prescricoes/{id}/url-document/full?token=`, `GET /prescricoes/{id}/get-digital-prescription-link?token=`. `download_pdf(url)` baixa os bytes (aceitar `application/pdf` **ou** `application/octet-stream`, validar os magic bytes `%PDF`). **Suprimir os loggers `httpx`/`httpcore`** (`setLevel(logging.WARNING)`) e nunca logar a URL completa. Criar `fakes.py` com `FakeMemedClient` determinístico que grava chamadas e serve bytes de PDF em memória. NÃO chamar a rede em testes; NÃO inventar endpoints além destes; NÃO incluir segredos em `repr`/logs.
  Parallelization: Wave 2 | Blocked by: 2 | Blocks: 5,6,7
  References: `doc.memed.com.br/docs/backend/chaves`, `/docs/backend/cidades`, `/docs/backend/especialidades`, `/docs/backend/prescricao`, `/docs/como-fazer/cadastrar-prescritor`, `/docs/como-fazer/obter-dados-usuario`, `/docs/boas-praticas-integracao`; `backend/pyproject.toml:15` (httpx já disponível); `backend/app/core/config.py` (campos do todo 2); `backend/app/services/lab_codes.py` (convenção de módulo de serviço puro).
  Acceptance criteria: `cd backend && uv run pytest tests/test_memed_client.py -q` passa; um teste com `httpx.MockTransport` verifica que a querystring carrega `api-key`/`secret-key`, que `get_prescriber` lê `data.attributes.token` e que `download_pdf` retorna bytes a partir de um `MockTransport`; `repr(PrescriberResult(...))` não contém o token.
  QA scenarios: happy — parse do JSON:API retorna id/status/token; `download_pdf` retorna `%PDF...`; failure — HTTP 401 do `check-key` retorna `False`; `download_pdf` com conteúdo não-PDF levanta erro tipado. Evidence `.omo/evidence/task-4-2026-10-05-fase1-memed-plan.txt`.
  Commit: Y | feat(prescriptions): add Memed client port, HTTP client and fake

- [ ] 5. Implementar o serviço de prescritor: ensure idempotente, token fresco e dados de referência
  What to do / Must NOT do: Criar `backend/app/services/prescriptions/prescriber.py` com: `ensure_prescriber(db, client)` que faz `get_prescriber(external_id)` e, se ausente, `create_prescriber(...)`, persistindo `memed_user_id`/`memed_status` (idempotente por `external_id`, usando o singleton fixo); `fresh_token(db, client)` que **sempre** chama `get_prescriber` na hora e retorna o token sem persistir; `cached_cities`/`cached_specialties` com cache em processo de TTL curto. Montar o payload JSON:API com `board`, `data_nascimento` (dd/mm/YYYY) e `relationships` de cidade/especialidade. NÃO persistir o token; NÃO logar token/CPF; NÃO reenviar `create` se já existir.
  Parallelization: Wave 2 | Blocked by: 3,4 | Blocks: 7,8,13
  References: `doc.memed.com.br/docs/como-fazer/cadastrar-prescritor`; `/docs/como-fazer/obter-dados-usuario`; `/docs/backend/cidades`; `/docs/backend/especialidades`; `backend/app/core/patient_keys.py:22-41` (padrão de cache TTL em processo); portas do todo 4; modelos do todo 2.
  Acceptance criteria: `cd backend && uv run pytest tests/test_prescriber_service.py -q` passa: ensure cria uma vez e, na segunda chamada com o mesmo `external_id`, não chama `create`; `fresh_token` chama `get_prescriber` a cada invocação; cidades/especialidades usam cache na segunda chamada.
  QA scenarios: happy — primeiro ensure cria (`create` chamado 1x), segundo apenas lê; failure — com um token-sentinela conhecido, ele nunca aparece nos logs capturados (`caplog`) nem no `repr` dos resultados. Evidence `.omo/evidence/task-5-2026-10-05-fase1-memed-plan.txt`.
  Commit: Y | feat(prescriptions): add prescriber ensure, fresh token and reference cache

- [ ] 6. Implementar o adaptador defensivo dos eventos `prescricaoImpressa` / `prescricaoExcluida`
  What to do / Must NOT do: Criar `backend/app/services/prescriptions/events.py` com `parse_prescricao_impressa(payload: dict) -> CaptureMetadata` e `parse_prescricao_excluida(payload: dict) -> str` (id). O payload é **não verificado**: buscar o id por chaves candidatas (`prescription_id`, `prescriptionId`, `prescription_uuid`, `data.prescription_id`, `id` quando o tipo for prescrição), e `signed`/`file_name`/`file_hash` por `signed`/`file_name|fileName`/`file_hash|fileHash`. Se o id não for encontrado, levantar `UnparsableMemedEvent(keys=sorted(payload.keys()))` — **logando apenas os nomes das chaves, nunca os valores**. Não assumir nenhuma chave fixa; documentar as chaves candidatas no módulo. NÃO parsear PII do payload; NÃO falhar o request de forma irrecuperável.
  Parallelization: Wave 2 | Blocked by: 4 | Blocks: 7
  References: `doc.memed.com.br/docs/frontend/eventos-mdhub/prescricao-impressa`; `docs/plans/2026-10-05-prontuario-receitas-plano.md:125-130` (fatos validados em homolog); "Decisões que precisam de checagem humana" #2.
  Acceptance criteria: `cd backend && uv run pytest tests/test_memed_events.py -q` passa: payloads com cada chave candidata são parseados; um payload sem id levanta `UnparsableMemedEvent` cujo `str` contém as chaves mas não os valores.
  QA scenarios: happy — payload `{"prescription_id": 42, "signed": true}` → `CaptureMetadata(42, True, ...)`; failure — payload `{"foo": "bar"}` levanta erro listando `['foo']` e o valor `"bar"` não aparece na mensagem. Evidence `.omo/evidence/task-6-2026-10-05-fase1-memed-plan.txt`.
  Commit: Y | feat(prescriptions): add defensive Memed event adapter

- [ ] 7. Implementar o serviço de captura e arquivamento do PDF assinado
  What to do / Must NOT do: Criar `backend/app/services/prescriptions/archive.py` com `capture_signed_pdf(db, prescription, prescriber, metadata, client)` que: (a) `token = await fresh_token(db, client)`; (b) `url = await client.get_prescription_pdf_url(token, metadata.memed_prescription_id)`; (c) `data = await client.download_pdf(url)` (validar `%PDF`); (d) `hash = sha256(data)` **sempre**; se `metadata.file_hash` existir **e tiver forma de sha256 (64 hex)**, comparar e levantar em divergência; se existir em outro formato, registrar aviso e prosseguir sem falhar (o hash arquivado é sempre o calculado); (e) `ensure_patient_kek` + `encrypt_document`; (f) criar/flushar `PrescriptionDocument` (obter id), gravar o blob em `f"{patient_id}/{doc_id}.enc"`, setar `storage_path`, chamar `transition(..., issued)` e commitar; **em qualquer exceção, apagar o blob recém-gravado e fazer rollback** (sem órfãos). Tentar `get_digital_link(token, id)` (best-effort, não fatal). Um segundo capture para a mesma prescrição é rejeitado **antes** de gravar o blob. Adicionar `read_signed_pdf(db, prescription)`. NÃO enfileirar `ocr_stage`; NÃO gravar PDF em claro; NÃO deixar blob órfão.
  Parallelization: Wave 2 | Blocked by: 4,5,6 | Blocks: 8
  References: `backend/app/routers/documents.py:139-160` (encriptar/gravar/construir), `:179-194` (decriptar/stream); `backend/app/core/patient_keys.py:45-54`; `backend/app/core/encryption.py:79-91`; `backend/app/core/storage.py:79-91`; `doc.memed.com.br/docs/backend/prescricao` (`url-document/full`, `get-digital-prescription-link`).
  Acceptance criteria: `cd backend && uv run pytest tests/test_prescription_archive.py -q` passa: os bytes no storage são cifrados (não contêm `%PDF`), o decriptado é igual à entrada, e nenhum `ocr_stage.delay` foi chamado (`unittest.mock.patch(...).assert_not_called()`); um segundo capture é rejeitado sem novo blob; uma falha simulada na transição remove o blob gravado.
  QA scenarios: happy — round-trip de decrypt igual à entrada e `PrescriptionDocument.hash` correto; failure — `file_hash` divergente (64 hex) levanta e **não** cria o documento; `file_hash` em formato não-sha256 **não** falha (avisa e prossegue); falha pós-gravação não deixa arquivo órfão no storage. Evidence `.omo/evidence/task-7-2026-10-05-fase1-memed-plan.txt`.
  Commit: Y | feat(prescriptions): capture and archive signed PDF into encrypted storage

- [ ] 8. Expor a API de prescrições e de prescritor: CRUD, autosave versionado, sessão, capture, deleted, retry e download
  What to do / Must NOT do: Criar `backend/app/schemas/prescription.py` (Pydantic v2; espelhando `backend/app/schemas/medication.py`) e `backend/app/routers/prescriptions.py` com os endpoints do "Contracts". `PrescriptionUpdateRequest = {version: int, notes: str | None, items: list[PrescriptionItemRequest] | None}`; quando `items` vem, **substitui a lista inteira**; `PATCH` faz compare-and-swap (`UPDATE ... WHERE id=:id AND version=:expected`, checa `rowcount`) e retorna `409 {detail:{code:"stale_version", current_version:N}}`. `DELETE` só em `draft` (seta `is_deleted=True`). `capture` recebe o payload cru do evento, chama o adaptador e o serviço de arquivamento; `memed-deleted` recebe o payload cru e marca `status=deleted`. `memed-session` retorna `Cache-Control: no-store`. Leitura com `require_patient_access(..., view)`; escrita com `contribute`; `memed-session`, `capture`, `memed-deleted` exigem adicionalmente `user.id == prescriber.user_id` (senão 403); se não houver `Prescriber` configurado, retornam `409 {detail:{code:"prescriber_not_configured"}}`. Injetar a porta `MemedClient` via `Depends` para override com o fake nos testes. Criar `backend/app/routers/prescriber.py` com `GET/PUT /api/admin/prescriber` (`require_admin`) e `GET /api/admin/memed/reference-data`. Registrar ambos em `backend/app/main.py`. Escrever `AuditLog` inline em emitir/arquivar/excluir. NÃO chamar a rede dentro do request sem passar pelo serviço; NÃO permitir editar itens após `issued`; NÃO retornar CPF completo nem `cpf_encrypted`.
  Parallelization: Wave 3 | Blocked by: 5,7 | Blocks: 10,11,12,13
  References: `backend/app/routers/medications.py:1-124`; `backend/app/deps.py:19-61`; `backend/app/auth/access.py:17-84`; `backend/app/schemas/medication.py:1-45`; `backend/app/schemas/common.py:10-18`; `backend/app/models/audit.py:11-23`; `backend/app/services/erasure.py:123-131` (formato do tombstone); `backend/app/main.py:63-84`; `backend/app/routers/admin.py` (padrão `require_admin`).
  Acceptance criteria: `cd backend && uv run pytest tests/test_prescription_api.py -q` passa: criar rascunho → autosave incrementa `version` → autosave obsoleto retorna `409` com `current_version` → `capture` com fake produz `issued` + `PrescriptionDocument` → usuário sem grant recebe `404` → não-prescritor recebe `403` em `capture` → `GET /document` retorna o PDF → a resposta de `GET /admin/prescriber` não contém o CPF completo.
  QA scenarios: happy — fluxo `draft→autosave→capture→download` com fake; failure — `PATCH` com `version` antigo retorna `409` e não muta; `GET /document` sem grant retorna `404`; `memed-session` retorna `Cache-Control: no-store`. Evidence `.omo/evidence/task-8-2026-10-05-fase1-memed-plan.txt`.
  Commit: Y | feat(prescriptions): add prescriptions and prescriber API

- [ ] 9. Integrar prescrições ao apagamento de paciente e à retenção
  What to do / Must NOT do: Em `backend/app/services/erasure.py:erase_patient`, coletar via **join** (`PrescriptionItem`/`PrescriptionDocument` não têm `patient_id`: juntar por `Prescription.patient_id`) e hard-delete `PrescriptionItem`, `PrescriptionDocument`, `Prescription` do paciente, incluindo os `storage_path` dos documentos na lista de blobs apagados e os ids em `all_entity_ids` (purga de `AuditLog`). Em `erase_user`, se o usuário for o `Prescriber.user_id` vinculado: **desvincular** (`user_id = None`) **e anonimizar a PII do prescritor** (`given_name`/`family_name` → `[erased]`, `cpf_encrypted = None`, `cpf_last4 = None`, `birth_date = None`, `email = None`, `phone = None`), preservando `board_code`/`board_number`/`board_state` (dado profissional público que consta nas vias externas). Em `backend/app/services/governance.py`, **não adicionar** categoria de prescrição a `BUILTIN_CATEGORIES`/`CATEGORY_MODELS` (assim a retenção nunca as purga) e registrar essa decisão. NÃO crypto-shredar referências a números já emitidos externamente (impossível); documentar que as vias externas sobrevivem.
  Parallelization: Wave 3 | Blocked by: 2 | Blocks: -
  References: `backend/app/services/erasure.py:34-146` (cascade), `:149-236` (user erasure); `backend/app/services/governance.py:21-42` (`BUILTIN_CATEGORIES`/`CATEGORY_MODELS`), `:78-128` (purge); `backend/app/workers/scheduler.py:134-146`; `docs/adr/017-patient-erasure-cascade-hard-delete.md`; `docs/adr/031-per-patient-kek-crypto-shredding.md`.
  Acceptance criteria: `cd backend && uv run pytest tests/test_prescription_erasure.py -q` passa: apagar um paciente remove prescrições, itens, documentos e os arquivos de storage; apagar o usuário prescritor desvincula e anonimiza a PII do `Prescriber` (board preservado); `"prescription" not in CATEGORY_MODELS` e `run_retention_purge` não toca prescrições.
  QA scenarios: happy — cascade remove todas as linhas novas e os blobs; failure — asserta que o `Prescriber` sobrevive com PII anonimizada e `board_number` preservado, e que a retenção não purga prescrições. Evidence `.omo/evidence/task-9-2026-10-05-fase1-memed-plan.txt`.
  Commit: Y | feat(prescriptions): integrate prescriptions with erasure and retention

- [ ] 10. Frontend: wrappers de API, seção do paciente, página de lista e proxy de download do PDF
  What to do / Must NOT do: Adicionar wrappers tipados em `frontend/src/lib/api.ts` (junto dos de medicação, `:82-85`): `getPrescriptions`, `createPrescription`, `getPrescription`, `updatePrescription` (autosave com `version`), `deletePrescription`, `getMemedSession`, `capturePrescription`, `markPrescriptionDeleted`, `retryPrescription`. `capture`/`memed-deleted` são **server actions** (JSON; sem rota-proxy). Adicionar `{ key: "Prescriptions", segment: "prescriptions", Icon: FileSignature, tint }` a `frontend/src/lib/patientSections.ts:16-24`, importando `FileSignature` de `lucide-react`. Criar `frontend/src/app/patients/[id]/prescriptions/page.tsx` (server component modelado em `medications/page.tsx`) e `PrescriptionList.tsx` (client, lista + status + link para o PDF). Criar `frontend/src/app/api/prescriptions/[id]/document/route.ts` (route handler binário, autenticando via `auth()` e encaminhando Bearer, modelo `frontend/src/app/api/documents/[docId]/file/route.ts:1-34`). Adicionar as strings em `pt.json`/`en.json`/`de.json` (namespace novo; sem locale novo). NÃO chamar a Memed do browser nesta tarefa; NÃO adicionar locale.
  Parallelization: Wave 4 | Blocked by: 8 | Blocks: 11,12
  References: `frontend/src/lib/api.ts:1-40,82-85`; `frontend/src/lib/patientSections.ts:16-24`; `frontend/src/app/patients/[id]/medications/page.tsx:1-54`; `frontend/src/app/patients/[id]/page.tsx:98-115`; `frontend/src/components/layout/AppSidebar.tsx:173-185,207-219`; `frontend/src/components/layout/PatientSectionSwitcher.tsx:25`; `frontend/src/app/api/documents/[docId]/file/route.ts:1-34`; `frontend/src/messages/pt.json:660` (`class_prescription` já existe); `frontend/AGENTS.md`.
  Acceptance criteria: `cd frontend && pnpm exec tsc --noEmit` passa; a página renderiza a lista; o item "Prescriptions" aparece na overview, na sidebar e no switcher mobile; `GET /api/prescriptions/{id}/document` devolve o PDF com o Bearer do servidor.
  QA scenarios: happy — `pnpm build` passa e a seção aparece nos três pontos de navegação; failure — sem locale novo (`ls frontend/src/messages` continua com 3 arquivos); o proxy retorna 401 sem sessão. Evidence `.omo/evidence/task-10-2026-10-05-fase1-memed-plan.txt`.
  Commit: Y | feat(frontend): add prescriptions API wrappers, section, list and PDF proxy

- [ ] 11. Frontend: embed do módulo Memed e ponte `postMessage`
  What to do / Must Not do: Criar `frontend/src/app/patients/[id]/prescriptions/MemedEmbed.tsx` (client). Fluxo: `getMemedSession(prescriptionId)` → `{ token, scriptUrl, patient }` → injetar o script da Memed com `data-token` e `data-container` (via `next/script` ou criação dinâmica de `<script>`) → `window.addEventListener("message", ...)` para `core:moduleInit`/`core:moduleHide`; em `core:moduleInit`, quando `module.name === 'plataforma.prescricao'`, enviar `MdHub.command.send('plataforma.prescricao','setPaciente', patient)` (e, se disponível, `'setWorkplace'` em best-effort com try/catch — o comando **não** está na lista de referências verificadas), e registrar **uma vez** `MdHub.event.add('prescricaoImpressa', ...)` e `MdHub.event.add('prescricaoExcluida', ...)`. Abrir o módulo com `MdHub.command.send('plataforma.prescricao','show')` (conforme o fato verificado). Em `prescricaoImpressa`, encaminhar o **payload cru** para `capturePrescription(prescriptionId, payload)`; em `prescricaoExcluida`, encaminhar para `markPrescriptionDeleted(prescriptionId, payload)`. Tratar `core:allmodulesareready` como **não verificado** (não depender dele). NÃO colocar o token em log/URL/estado persistente; NÃO usar eventos DOM; NÃO assumir chaves fixas do payload no cliente (o backend faz o parse defensivo).
  Parallelization: Wave 4 | Blocked by: 10 | Blocks: 12
  References: `doc.memed.com.br/docs/frontend/mdsinapseprescricao-mdhub`; `/docs/frontend/comandos-mdhub/set-patient`; `/docs/frontend/comandos-mdhub/hide`; `/docs/frontend/eventos-mdhub/prescricao-impressa`; `/docs/boas-praticas-integracao`; `/docs/modos-de-carregamento`; `/docs/modos-de-exibicao`; `docs/plans/2026-10-05-prontuario-receitas-plano.md:115-130`; `frontend/src/components/DocumentViewer.tsx:59` (único iframe existente).
  Acceptance criteria: `cd frontend && pnpm exec tsc --noEmit` passa; teste Playwright intercepta `page.route('**/sinapse-prescricao*.js')` com um stub, usa `page.addInitScript` para `window.MdHub`/`MdSinapsePrescricao` e dispara `MessageEvent` `core:moduleInit` (verifica `setPaciente` + `show`) e `prescricaoImpressa` (verifica o POST de capture mockado).
  QA scenarios: happy — eventos stubados resultam em `setPaciente` + `capture`, sem requisição de rede ao script real; failure — o token não aparece em `console.log` nem em atributos persistidos; um evento desconhecido não quebra o handler. Evidence `.omo/evidence/task-11-2026-10-05-fase1-memed-plan.txt`.
  Commit: Y | feat(frontend): embed Memed module with postMessage bridge

- [ ] 12. Frontend: editor de rascunho com autosave, retry e wiring de capture/deleted
  What to do & Must NOT do: Criar `frontend/src/app/patients/[id]/prescriptions/PrescriptionEditor.tsx` (client) com edição de itens (adicionar/remover/ordenar) e autosave **debounced** via `PATCH /api/prescriptions/{id}` incluindo `version`; em `409`, exibir conflito com uma ação **"recarregar"** que busca a versão atual (`getPrescription`) e permite reaplicar — **sem** descartar o texto do usuário. Exibir um botão de **retry** quando `status == failed` (chama `retryPrescription`). O botão de emitir fica desabilitado se o usuário não for o Prescriber vinculado (a UI trata o `403`). Usar os server actions do todo 10 (sem rota-proxy de capture). NÃO engolir `409`; NÃO enviar binário do browser (o backend baixa o PDF).
  Parallelization: Wave 4 | Blocked by: 10,11 | Blocks: -
  References: `frontend/src/app/patients/[id]/documents/UploadPanel.tsx:30-51` (padrão de UI assíncrona); `frontend/src/lib/api.ts` (wrappers do todo 10); `frontend/e2e/smoke.spec.ts` (padrão Playwright); `docs/plans/2026-10-05-fase1-dominio-prescricao.md:138` (referência de escopo do editor, sem herdar o desenho SNCR).
  Acceptance criteria: `cd frontend && pnpm exec tsc --noEmit` passa; um teste Playwright edita um rascunho, espera o debounce e asserta um `PATCH` com `version` incrementando; um `409` forçado mostra o conflito + "recarregar" sem perder o texto; `failed` mostra o botão de retry.
  QA scenarios: happy — autosave dispara uma vez após o debounce e atualiza a versão; failure — `409` renderiza conflito e preserva o texto; retry em `failed` volta a `draft`. Evidence `.omo/evidence/task-12-2026-10-05-fase1-memed-plan.txt`.
  Commit: Y | feat(frontend): add draft autosave editor, conflict handling and retry

- [ ] 13. Frontend: UI admin de cadastro do prescritor
  What to do / Must NOT do: Criar `frontend/src/app/admin/prescriber/page.tsx` (server+client) para cadastrar/editar o singleton `Prescriber`: nome, sobrenome, CPF, data de nascimento, conselho (código/número/UF), cidade e especialidade (buscando `GET /api/admin/memed/reference-data`), e-mail/telefone/sexo, e seleção do User vinculado (deve emitir). No update, deixar o CPF em branco **preserva** o valor existente. Exibir o CPF mascarado (`cpf_last4`) após salvar. Adicionar o link na nav admin em `frontend/src/components/layout/AppSidebar.tsx:253` (junto dos itens admin-only). Usar os wrappers de `frontend/src/lib/api.ts`. NÃO exibir nem logar o CPF completo após o salvamento; NÃO permitir salvar sem os campos obrigatórios da Memed no create.
  Parallelization: Wave 4 | Blocked by: 5,8 | Blocks: -
  References: `frontend/src/app/admin/organization/page.tsx` e `frontend/src/app/admin/license/page.tsx` (padrão de página admin); `frontend/src/app/admin/system/page.tsx`; `frontend/src/lib/api.ts:149-177` (wrappers admin); `frontend/src/app/patients/[id]/manage/page.tsx` (seleção de usuários); `frontend/src/components/layout/AppSidebar.tsx:253` (nav admin); endpoints do todo 8.
  Acceptance criteria: `cd frontend && pnpm exec tsc --noEmit` passa; um teste Playwright preenche o formulário, salva e vê o CPF mascarado; campos obrigatórios ausentes bloqueiam o submit no create; salvar sem CPF no update preserva o valor.
  QA scenarios: happy — cadastro salva e reflete `memed_status`; failure — CPF completo não aparece no DOM nem em console após salvar; submit sem `birth_date`/`board` é bloqueado. Evidence `.omo/evidence/task-13-2026-10-05-fase1-memed-plan.txt`.
  Commit: Y | feat(frontend): add admin prescriber settings UI

- [x] 14. Publicar a cópia canônica do plano em `docs/plans/2026-10-05-fase1-memed-plan.md` — **feito** (2026-10-05: cópia publicada e commitada).
  What to do / Must NOT do: copiar o conteúdo de `.omo/plans/2026-10-05-fase1-memed-plan.md` para `docs/plans/2026-10-05-fase1-memed-plan.md` (documentação do repo). NÃO alterar o conteúdo; NÃO tratar como mudança de código. (O agente de planejamento é restrito a `.omo/*.md`; esta cópia é executada na sessão de worker ou manualmente.)
  Parallelization: pós-planejamento | Blocked by: - | Blocks: -
  References: `.omo/plans/2026-10-05-fase1-memed-plan.md` (fonte canônica).
  Acceptance criteria: `cmp .omo/plans/2026-10-05-fase1-memed-plan.md docs/plans/2026-10-05-fase1-memed-plan.md` sai 0 (ou documenta-se a única diferença: a nota de cabeçalho da cópia).
  QA scenarios: happy — o arquivo existe e bate com a fonte; failure — divergência de conteúdo falha o `cmp`. Evidence `.omo/evidence/task-14-2026-10-05-fase1-memed-plan.txt`.
  Commit: Y | docs(plans): publish Memed phase-1 plan copy

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [ ] F1. Plan compliance audit — cada critério de aceite dos todos foi realmente executado e a evidência registrada; nenhuma chamada Memed real existe nos testes (`rg -n "integrations.api.memed|api.memed" backend/tests` vazio); nenhum segredo/token/CPF é logado (o teste `test_log_redaction.py` com sentinela passa, e `rg -n "logger.*token|print.*token|logger.*cpf" backend/app` está vazio); os loggers `httpx`/`httpcore` estão em WARNING.
- [ ] F2. Code quality review — `cd backend && uv run ruff check . && uv run pytest -q`; `cd frontend && pnpm exec tsc --noEmit && pnpm lint && pnpm build`.
- [ ] F3. Real manual QA — com `FakeMemedClient` e módulo Memed stubado (`page.route`), exercitar `draft→autosave→capture→download` ponta a ponta no stack de dev e anexar o transcript; validar a seção "Prescrições", o conflito `409`, o retry e a UI admin.
- [ ] F4. Scope fidelity — confirmar ausência de SNCR-direto, motor de assinatura, geração de PDF/layout RDC, CNPJ, multi-prescritor, OCR de receita e mudanças no pipeline de `Document`; confirmar que o número SNCR não foi inventado, que a seção dedicada não cria `DocumentReference` e que nenhum endpoint/porta carrega o token sem ser explicitamente passado.

## Commit strategy
Um commit convencional por todo (`docs(domain):`, `feat(prescriptions):`, `feat(frontend):`). Migração e modelos no mesmo commit dos respectivos testes. Todos 3–4 podem compartilhar commit apenas se ambos verdes. Nenhum commit pode conter chave/token real da Memed ou CPF em claro. Atualizar `.env.example` no commit do todo 2.

## Success criteria
- `cd backend && uv run alembic heads` mostra um head sobre `g3b4c5d6e7f8`; migração up/down/up limpa.
- `cd backend && uv run pytest -q` verde com os novos `test_prescription_*.py`/`test_memed_*.py`/`test_log_redaction.py`, todos offline.
- Uma prescrição pode ser criada, autosalva com detecção de conflito (`409` com `current_version`), e emitida via `FakeMemedClient` (incluindo `download_pdf`), produzindo um `PrescriptionDocument` criptografado, `status=issued`, hash correto e entradas de auditoria; uma falha de captura não deixa blob órfão e pode ser retomada via `retry`.
- O apagamento de paciente remove prescrições, itens, documentos e blobs; a receita não é purgada pela retenção; apagar o usuário prescritor desvincula e anonimiza a PII do `Prescriber` (board preservado).
- `pnpm build` passa e a seção "Prescrições" aparece na overview/sidebar/switcher; o editor autosalva com versionamento e trata `409`; a ponte `postMessage` é exercitada com o módulo stubado sem tocar a rede; o PDF é baixado pelo proxy autenticado.
- Nenhum teste toca a rede; nenhum log contém token, `api-key`, `secret-key` ou CPF (verificado por sentinela).

### Crítica incorporada (revisão de alta precisão — Momus + Oracle)
Ambos os revisores retornaram **CHANGES_REQUESTED**. Cada ponto e a resposta no plano:

| Crítica | Severidade | Resposta no plano final |
|---|---|---|
| Porta `get_prescription_pdf_url`/`get_digital_link` não recebia o `token` obrigatório (`?token=`) | blocker | Assinaturas agora são `(token, memed_prescription_id)`; `capture` obtém `token = fresh_token(...)` (todo 4/7) |
| Download do PDF fora da porta → teste tocaria rede / `FakeMemedClient` não cobria | blocker | `download_pdf(url) -> bytes` adicionado à porta; fake serve bytes (todo 4/7) |
| Faltava rota-proxy do PDF no frontend (Bearer do servidor) | blocker | Adicionada `frontend/src/app/api/prescriptions/[id]/document/route.ts` (todo 10) |
| Payload de `prescricaoImpressa` não verificado e instruções com chaves fixas | blocker | Novo adaptador defensivo `events.py` com chaves candidatas + erro tipado listando só os nomes das chaves (todo 6) |
| Referência pendente a `prescriber_snapshot` inexistente | blocker | Removida; o `Prescriber` sobrevive e a PII é anonimizada no `erase_user` (todos 2/9) |
| Singleton `Prescriber` sem constraint | blocker | `PRESCRIBER_SINGLETON_ID` fixo + teste de upsert único (todo 2) |
| Semântica de delete contraditória (`draft`-only vs `issued→deleted`) | blocker | `DELETE` = `is_deleted` só em `draft`; `status=deleted` só via `prescricaoExcluida`; máquina de estados ajustada (todos 3/8) |
| Retenção vs erasure incoerente; teste de retenção vazio | major | Prescrições deliberadamente fora de `CATEGORY_MODELS`; teste asserta a ausência (todo 9) |
| PII do prescritor sobrevive ao `erase_user` | major | Anonimização de nome/CPF/nascimento/email/phone, preservando `board_*` (todo 9) |
| Teste da ponte `postMessage` ainda baixaria o script real | major | `page.route('**/sinapse-prescricao*.js')` + `addInitScript` (todo 11) |
| Redação de segredos sem teste significativo (substring `"token"`) | major | `test_log_redaction.py` com token/CPF-sentinela + `repr=False` + assert de resposta sem CPF (todos 4/5/8) |
| `httpx`/`httpcore` em DEBUG logariam `api-key`/`secret-key` | major | Loggers suprimidos para WARNING no cliente (todo 4) |
| Proveniência do `file_hash` indefinida | major | Hash sempre calculado do PDF arquivado; comparação com o do evento só quando presente (todo 7) |
| Corrida/retry do capture sem recuperação | major | Um retry em 401/403/404 + endpoint `retry` e botão na UI (todos 7/8/12) |
| Corpo do `PATCH` (autosave) indefinido | major | `{version, notes?, items?}` com `items` substituindo a lista; `409` com `current_version` (todo 8) |
| Blob órfão se a transição falhar após a gravação | major | Grava após flush e apaga o blob no `except` (todo 7) |
| Proxy vs server action inconsistente no capture | major | `capture`/`memed-deleted` são server actions; só o PDF usa rota-proxy (todos 10/11) |
| CPF do paciente ausente no `Patient` para `setPaciente` | major | **Resolvido (checagem humana #3):** a doc de credenciais de produção exige CPF/contato no `setPaciente` → adicionar `cpf_encrypted`/`cpf_last4`/`birth_date`/`email`/`phone` a `patients` na mesma migração (todo 2; ver "Data model") |
| `PrescriberResult` com token no `repr` | minor | `field(repr=False)` (todo 4) |
| UX de conflito `409` sem recuperação | minor | Ação "recarregar" sem descartar texto (todo 12) |
| `retry` classificado como "Could have" | minor | Promovido a Must have (todos 8/12) |
| Snapshot de itens podendo divergir do PDF | minor | Explicitado como rascunho local; PDF é a fonte autoritativa (Data model) |
| `status=deleted` vs `is_deleted` confusos | minor | Conceitos separados e documentados (Data model/todo 3) |
| Coleta de itens/documentos no erasure sem `patient_id` | minor | Exigido join explícito por `Prescription.patient_id` (todo 9) |
| `MdHub.module.show` vs `MdHub.command.send(...,'show')` | minor | Padronizado em `MdHub.command.send('plataforma.prescricao','show')` (todo 11) |
| `external_id = str(id)` sem momento de geração | minor | Setado explicitamente no create (todo 2) |
| Ícone `FileSignature` não importado | minor | Import explícito de `lucide-react` (todo 10) |
| Nav admin sem arquivo nomeado | minor | `AppSidebar.tsx:253` (todo 13) |
| `env.py:14` errado para registro de modelos | minor | Corrigido para `env.py:13` (todo 2) |
| Comando de build pesado em tarefa só de docs | minor | Substituído por checagem de markdown/grep (todo 1) |
| Citação do plano SNCR superado para invariantes | minor | Removida; invariantes definidas neste plano (todo 3) |
| `memed-session` sem `no-store` | minor | `Cache-Control: no-store` (todo 8) |
| `test_prescription_archive.py` fora da lista de arquivos | minor | Adicionado à lista de testes |
| `Prescription.signed` redundante | minor | Campo removido (Data model) |
| `PrescriptionDocument` sem `patient_id` no endpoint de download | minor | `patient_id` resolvido via `Prescription` (todo 8) |
| Duplicação proxy/rota para capture | minor | Resolvida (server actions) (todos 10/11) |

**Rodada de confirmação (após as correções):** o Momus retornou **APPROVED**; a revisão independente (Oracle) confirmou todos os 17 blockers/majors e os 20 minors como RESOLVED e apontou 1 major novo + minors, agora também incorporados:

| Crítica (confirmação) | Severidade | Resposta no plano final |
|---|---|---|
| `file_hash` do evento comparado a sha256 sem verificar o algoritmo (poderia falhar todo capture) | major | Compara só quando o hash tem forma sha256 (64 hex); outro formato → aviso e prossegue (todo 7) |
| `env.py:13` errado (o correto é `:14`) | minor | Corrigido para `env.py:14` (todo 2) |
| Listagem filtra só `is_deleted=False`, não `status != deleted` | minor | Contrato atualizado para filtrar ambos (Contracts) |
| `setWorkplace` sem referência verificada | minor | Passa a best-effort opcional com try/catch (todo 11) |
| `Prescriber` não configurado → `AttributeError` | minor | `memed-session`/`capture`/`memed-deleted` retornam `409 prescriber_not_configured` (todo 8) |
| `signed=False` podia chegar a `issued` | minor | `signed` documentado como informativo; `issued` depende do PDF arquivado (Data model) |
| `core:moduleHide` não observado em homolog | minor | Tratado como opcional; o plano depende só de `core:moduleInit`, `prescricaoImpressa`, `prescricaoExcluida` (Riscos) |