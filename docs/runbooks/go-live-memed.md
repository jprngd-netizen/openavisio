# Go-Live Runbook — Memed Prescrição (Produção)

> **GATED:** Este runbook **só pode ser executado** quando o owner fornecer as
> credenciais de produção da Memed, as credenciais do BirdID e acesso à VPS de
> produção. O worker não assume que estas existem — se alguma faltar, pare aqui.
>
> **Executável por:** outra pessoa (orquestrador/owner). Cada passo tem comando,
> resultado esperado e ação em caso de falha.

## Pré-requisitos

Antes de começar, confirme que todos os itens abaixo estão disponíveis:

| # | Item | Onde obter | Fornecido por |
|---|---|---|---|
| P1 | VPS de produção (SSH root) | Infraestrutura | Owner/DevOps |
| P2 | Domínio configurado (DNS A record apontando para a VPS) | Provedor DNS | Owner |
| P3 | Credenciais de produção da Memed (`MEMED_API_KEY`, `MEMED_SECRET_KEY`) | [Painel de parceiros Memed](https://doc.memed.com.br/docs/obter-credenciais) | Owner (parceiro Memed) |
| P4 | BirdID token de produção (assinatura digital) | [BirdID](https://birdid.com.br) | Owner |
| P5 | `AGE_PUBKEY` + chave **privada** do age (backup cifrado) | Gerar com `age-keygen` | Owner |
| P6 | `DOCUMENT_ENCRYPTION_KEY` (master KEK) | Gerar com `openssl rand -base64 32` | Owner |
| P7 | Tag de release (ex.: `v0.2.0`) | `git tag -a` + `git push origin` | Dev |
| P8 | Homolog validado (smoke verde em homolog) | Passo 0 deste runbook | Dev |

> **⚠ P3 e P4 são bloqueantes.** Sem as credenciais de produção da Memed e o
> BirdID, a emissão de prescrições não funciona. O formulário de parceiro Memed
> pode levar ~48h — solicite com antecedência.

---

## Passo 0 — Verificação pré-voo (homolog)

> **Obrigatório:** o smoke deve passar em homolog **antes** de tocar em produção.

```bash
# 0.1 — Smoke na homolog
./deploy/smoke-homolog.sh --base-url https://homolog.exemplo.com
```

**Resultado esperado:** `All smoke tests PASSED.`

**Se falhar:**
- Stack não está rodando → `ssh homolog-box "cd /opt/openavisio && docker compose ps"`
- Sem seed → `curl -X POST https://homolog.exemplo.com/api/dev/seed`
- Prescriber não configurado → configurar no admin UI
- Reportar ao dev antes de prosseguir

---

## Passo 1 — Preparar o ambiente de produção na VPS

### 1.1 — SSH para a VPS

```bash
ssh root@<vps-ip>
```

**Resultado esperado:** shell root na VPS.

**Se falhar:** verificar SSH key, IP, firewall (porta 22).

### 1.2 — Clonar o repositório

```bash
cd /opt
git clone https://github.com/jprngd-netizen/openavisio.git
cd openavisio
```

**Resultado esperado:** diretório `/opt/openavisio/` com o código.

**Se falhar:** verificar conectividade com o host do repositório, permissões.

### 1.3 — Fazer checkout do tag

```bash
git fetch --tags origin
git checkout v0.X.X
```

**Resultado esperado:** `HEAD` no tag desejado.

**Se falhar:** o tag existe? `git tag -l 'v*'`

### 1.4 — Configurar `.env.production`

> **⚠ NUNCA versionar este arquivo.** Contém segredos de produção.

```bash
cp .env.example .env.production
chmod 600 .env.production
```

Editar `.env.production` com os valores reais:

```bash
# Editar com nano/vi:
nano .env.production
```

**Valores obrigatórios:**

| Variável | Valor | Fonte |
|---|---|---|
| `APP_SECRET` | string aleatória 64 hex | `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | string aleatória 64 hex | `openssl rand -hex 32` |
| `BOOTSTRAP_TOKEN` | string aleatória 64 hex | `openssl rand -hex 32` |
| `AISERVICE_TOKEN` | string aleatória 64 hex | `openssl rand -hex 32` |
| `DOCUMENT_ENCRYPTION_KEY` | base64 32 bytes | `openssl rand -base64 32` |
| `DOMAIN` | `prescricao.exemplo.com` | Seu domínio |
| `ENVIRONMENT` | `production` | Fixo |
| `MEMED_API_URL` | `https://api.memed.com.br/` | **Produção** (⚠ NÃO homolog) |
| `MEMED_SCRIPT_URL` | `https://partners.memed.com.br/integration.js` | **Produção** (⚠ NÃO homolog) |
| `MEMED_API_KEY` | _(fornecido pelo owner)_ | Painel Memed |
| `MEMED_SECRET_KEY` | _(fornecido pelo owner)_ | Painel Memed |
| `MEMED_ENVIRONMENT` | `production` | Fixo |
| `AGE_PUBKEY` | `age1...` | `age-keygen -o age-key.txt && age-keygen -y age-key.txt` |
| `CORS_ORIGINS` | `https://prescricao.exemplo.com` | Seu domínio |
| `NEXTAUTH_URL` | `https://prescricao.exemplo.com` | Seu domínio |
| `WEBAUTHN_RP_ID` | `prescricao.exemplo.com` | Seu domínio |
| `WEBAUTHN_ORIGIN` | `https://prescricao.exemplo.com` | Seu domínio |

**Resultado esperado:** `.env.production` populado com todos os valores.

**Se falhar:** verificar cada variável — a guarda `_guard_production` (T0.1) aborta
se alguma `MEMED_*` crítica estiver vazia ou se `AGE_PUBKEY` estiver vazio.

### 1.5 — Linkar `.env.production` como `.env`

```bash
ln -sf .env.production .env
```

**Resultado esperado:** `ls -la .env` mostra o symlink.

### 1.6 — Verificar Docker e Compose

```bash
docker --version && docker compose version
```

**Resultado esperado:** Docker 24+ e compose plugin.

**Se falhar:** `apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin`

---

## Passo 2 — Revalidar `check-key` e dados de referência em produção

> **Crítico:** antes de subir o stack, validar que as credenciais de produção
> funcionam contra a API de produção da Memed.

### 2.1 — Testar `check-key` diretamente

```bash
curl -s -X POST "https://api.memed.com.br/v1/check-key" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "<MEMED_API_KEY>",
    "secret_key": "<MEMED_SECRET_KEY>"
  }'
```

**Resultado esperado:**
```json
{"code": "chave-valida"}
```

**Se falhar:**
- `chave-invalida` → as credenciais estão erradas. Verificar no painel de parceiros.
- `erro-conexao` → a VPS consegue alcançar `api.memed.com.br`? Verificar firewall/DNS.
- timeout → proxy ou firewall bloqueando saída.

### 2.2 — Testar `cidades` (dados de referência)

```bash
curl -s "https://api.memed.com.br/v1/cidades?api_key=<MEMED_API_KEY>&secret_key=<MEMED_SECRET_KEY>" | head -c 500
```

**Resultado esperado:** JSON array de cidades (não vazio).

**Se falhar:** verificar credenciais; se o endpoint mudou, consultar doc da Memed.

### 2.3 — Testar `especialidades` (dados de referência)

```bash
curl -s "https://api.memed.com.br/v1/especialidades?api_key=<MEMED_API_KEY>&secret_key=<MEMED_SECRET_KEY>" | head -c 500
```

**Resultado esperado:** JSON array de especialidades (não vazio).

**Se falhar:** mesmo que 2.2.

### 2.4 — Verificar script de frontend (`integration.js`)

```bash
curl -sI "https://partners.memed.com.br/integration.js" | head -5
```

**Resultado esperado:** HTTP 200, `content-type: application/javascript`.

**Se falhar:** verificar URL; se o caminho mudou, consultar doc da Memed.

---

## Passo 3 — Subir o stack

### 3.1 — Iniciar os serviços

```bash
docker compose up -d
```

**Resultado esperado:** todos os serviços com status `healthy` ou `started`.

**Se falhar:** `docker compose logs --tail=50` para diagnosticar.

### 3.2 — Aguardar healthcheck do backend

```bash
watch -n 5 'docker compose ps'
```

**Resultado esperado:** `backend` mostra `healthy` em até 2 minutos.

**Se falhar:**
```bash
docker compose logs backend --tail=80
```
Procurar por:
- Erro de conexão com Postgres → verificar `POSTGRES_PASSWORD`
- `alembic upgrade head` falhou → verificar migrações
- `_guard_production` abortou → verificar `.env.production` (T0.1)

### 3.3 — Verificar health endpoint

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

**Resultado esperado:**
```json
{"database": "ok", "redis": "ok"}
```

**Se falhar:** verificar logs do backend.

---

## Passo 4 — Smoke de produção

### 4.1 — Rodar smoke contra produção

```bash
./deploy/smoke-homolog.sh \
  --base-url http://localhost:8000 \
  --admin-email admin@exemplo.com \
  --admin-pass <senha>
```

> **Nota:** o smoke aponta para `localhost:8000` porque roda dentro da VPS.
> Se o proxy reverso já estiver configurado, usar a URL externa.

**Resultado esperado:** `All smoke tests PASSED.`

**Se falhar:** verificar cada fase do smoke individualmente.

### 4.2 — Verificar prescriber configurado

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@exemplo.com","password":"<senha>"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost:8000/api/admin/prescriber \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Resultado esperado:** dados do prescritor (nome, conselho, etc.).

**Se falhar:** configurar prescritor no admin UI → Prescriber settings.

### 4.3 — Verificar health da Memed (T1.1)

```bash
curl -s http://localhost:8000/api/admin/memed-health \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Resultado esperado:** `{"status": "ok", "check_key": "chave-valida", ...}`

**Se falhar:** as credenciais de produção podem estar incorretas ou a API da Memed
pode estar indisponível. Verificar Passo 2.

---

## Passo 5 — Configurar proxy reverso (NPM / Caddy)

### 5.1 — Apontar DNS

Criar registro A: `prescricao.exemplo.com` → IP da VPS.

**Resultado esperado:** `dig prescricao.exemplo.com` retorna o IP.

**Se falhar:** aguardar propagação de DNS (pode levar minutos/horas).

### 5.2 — Configurar Nginx Proxy Manager (ou equivalente)

- **Domain:** `prescricao.exemplo.com`
- **Scheme:** `http`
- **Forward IP:** `localhost` (ou IP interno da VPS)
- **Forward Port:** `80`
- **SSL:** Let's Encrypt

**Resultado esperado:** `https://prescricao.exemplo.com` carrega o frontend.

**Se falhar:** verificar logs do NPM, firewall (portas 80/443 abertas).

### 5.3 — Atualizar `.env.production` com domínio final

```bash
# Se o domínio mudou do passo 1.4:
nano .env.production
# Atualizar DOMAIN, NEXTAUTH_URL, CORS_ORIGINS, WEBAUTHN_*
docker compose up -d
```

---

## Passo 6 — Verificação completa

### 6.1 — Login no frontend

Abrir `https://prescricao.exemplo.com` no browser.

**Resultado esperado:** página de login carrega com HTTPS válido.

**Se falhar:** verificar proxy reverso, logs do frontend.

### 6.2 — Configurar prescritor

Admin UI → Prescriber settings → preencher dados do prescritor.

**Resultado esperado:** prescritor salvo com sucesso.

### 6.3 — Testar emissão de prescrição (homolog da Memed em produção)

> **Nota:** este passo usa o ambiente de produção da Memed mas com um paciente
> de teste. A prescrição emitida será real — consumirá 1 crédito.

1. Criar um paciente de teste
2. Criar uma prescrição (rascunho)
3. Clicar "Assinar e emitir"
4. Completar o fluxo no iframe da Memed

**Resultado esperado:** prescrição emitida com status `issued`, PDF arquivado.

**Se falhar:**
- Iframe não carrega → verificar `MEMED_SCRIPT_URL` e `MEMED_ALLOWED_ORIGINS`
- Assinatura falha → verificar BirdID, token
- Captura falha → verificar logs: `docker compose logs backend --tail=50`

### 6.4 — Verificar PDF arquivado

```bash
# Pelo ID da prescrição (obter do banco ou UI)
curl -s http://localhost:8000/api/prescriptions/<id>/document \
  -H "Authorization: Bearer $TOKEN" -o /tmp/test-prescription.pdf
file /tmp/test-prescription.pdf
```

**Resultado esperado:** `PDF document, version 1.X`

**Se falhar:** o PDF não foi arquivado — verificar `capture_signed_pdf` nos logs.

### 6.5 — Verificar backup inicial

```bash
docker compose logs backup --tail=20
```

**Resultado esperado:** `[backup] ok — ...` com os três streams.

**Se falhar:**
- `AGE_PUBKEY` vazio → setar em `.env.production` e reiniciar
- Postgres não disponível → verificar health do postgres

---

## Passo 7 — Rollback (critérios e procedimento)

### Quando fazer rollback

Fazer rollback **imediatamente** se qualquer um dos seguintes ocorrer:

| Critério | Exemplo | Consequência |
|---|---|---|
| **R1** — Prescrição emitida mas PDF **não** arquivado | Status `issued` sem `PrescriptionDocument` | Perda da receita legal |
| **R2** — `check-key` falha em produção | API Memed retorna `chave-invalida` | Nenhuma prescrição pode ser emitida |
| **R3** — Erro 500 no fluxo de captura | `capture` endpoint lança exceção não tratada | Usuário não consegue finalizar |
| **R4** — Backup não roda | `backup` container unhealthy | Sem proteção contra perda de dados |
| **R5** — Vazamento de segredo em log | Chave API aparece em log visível ao admin | Incidente de segurança |

### Procedimento de rollback

```bash
# 1. Notificar owner imediatamente
echo "ROLLBACK: <motivo> em $(date -Iseconds)" >> /var/log/openavisio-rollback.log

# 2. Redeploy do tag anterior
cd /opt/openavisio
git checkout v0.1.0          # ou último tag estável
docker compose up -d --build

# 3. Verificar health
curl -s http://localhost:8000/health

# 4. Verificar que o stack anterior está saudável
docker compose ps

# 5. Se o rollback for por vazamento de segredo:
#    - Rotacionar APP_SECRET, AISERVICE_TOKEN, MEMED_API_KEY, MEMED_SECRET_KEY
#    - git revert do commit que introduziu o vazamento
```

### Pós-rollback

1. Abrir issue no tracker com o motivo do rollback
2. Impedir novo go-live até a causa ser resolvida
3. Se houve emissão de prescrição antes do rollback, **reconciliar manualmente**
   com a Memed — as prescrições emitidas continuam válidas mesmo com o rollback

---

## Passo 8 — Pós-go-live (checklist)

- [ ] Smoke verde em produção
- [ ] Prescrição de teste emitida com sucesso
- [ ] PDF arquivado e recuperável
- [ ] Backup inicial rodou e produziu 3 streams
- [ ] `AGE_PUBKEY` validado (backup cifrado)
- [ ] Chave privada do age guardada **fora do servidor** (password manager)
- [ ] `DOCUMENT_ENCRYPTION_KEY` guardada **fora do servidor**
- [ ] Monitoramento configurado (healthcheck do backup)
- [ ] Pull de backup configurado (off-server sync, ver `docs/backup-restore.md`)
- [ ] Owner notificado que produção está ativa

---

## Apêndice A — Comandos úteis

### Verificar logs em tempo real

```bash
docker compose logs -f --tail=50
```

### Verificar apenas backend

```bash
docker compose logs backend --tail=100
```

### Verificar backup

```bash
docker compose logs backup --tail=30
ls -la /opt/openavisio-backups/
```

### Testar descriptografia de backup (requer chave privada)

```bash
age -d -i /path/to/age-key.txt clinical-$(date +%F).sql.age | head -c 200
```

### Verificar versão do código em produção

```bash
docker compose exec backend env | grep GIT_COMMIT
```

---

## Apêndice B — Referências

| Documento | Localização |
|---|---|
| Deploy script (produção) | `deploy/deploy.sh` |
| Deploy script (homolog) | `deploy/deploy-homolog.sh` |
| Smoke test | `deploy/smoke-homolog.sh` |
| Stack de produção | `deploy/docker-compose.prod.yml` |
| Backup/restore | `docs/backup-restore.md` |
| Plano de implementação | `.omo/plans/2026-10-06-fase2-memed-plan.md` |
| Doc da Memed (credenciais) | https://doc.memed.com.br/docs/obter-credenciais |
| API Memed (produção) | https://api.memed.com.br/ |
| Script Memed (produção) | https://partners.memed.com.br/integration.js |
| API Memed (homolog) | https://integrations.api.memed.com.br/v1 |