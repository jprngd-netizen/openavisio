# Pesquisa — Checagem de interação medicamentosa (OpenAvisio)

*Data: 2026-10-10 · insumo para DEC-2b / IX-DEC-1/2. Pesquisa só-leitura (repo não tocado).*

## Achado que muda o desenho

- **A DDI API clássica do RxNav/RxNorm (NLM) foi DESCONTINUADA em 02/01/2024**, sem substituto. O restante do RxNorm (normalização nome→RxCUI) segue vivo, grátis, ~20 req/s por IP (100 com chave UMLS), sem licença. → RxNorm serve para **normalizar**, não para checar interação.
- A **Memed já mostra alerta de interação no próprio módulo** (leve/moderado/grave), mas **client-side no iframe cross-origin** — a API de backend da Memed **não expõe endpoint de interação**. O app pai não lê esse alerta por JS.

## Comparativo de fontes

| Fonte | Licença/custo | Cobertura PT (nomes BR) | Disponibilidade |
|---|---|---|---|
| Memed (embed) | Grátis (parceiro) | ✅ total (módulo BR) | só no fluxo Memed; não legível por API |
| RxNav DDI | — | — | ❌ descontinuado 02/01/2024 |
| RxNorm (normalização) | Grátis, ODbL | ⚠️ US-centric (inglês/INN) | ✅ 20–100 req/s |
| DrugBank | Acadêmico grátis; comercial = licença paga | ❌ US | dataset que o NLM usava; não reutilizável sem contrato |
| **DDInter 2.0** | **CC BY-NC-SA 4.0** (não-comercial) | ⚠️ inglês + ATC | ✅ download CSV offline (~302k DDI) |
| **IMSES / CRF-MG "Detecta Interações"** | **Grátis, sem fins lucrativos** (chave API) | ✅ **100% PT**, ~330 interações graves | ✅ (401 sem chave) |
| ANVISA (dados abertos + bulas) | Grátis | ✅ princípio ativo PT | ✅ CSV |

## Recomendação

**Primário (dois níveis):**
1. **Camada humana, custo zero:** manter/reforçar o alerta **nativo da Memed** no embed (PT, no fluxo, advisory). Não reimplementar para receitas Memed.
2. **Camada API para medicação em texto livre:** **IMSES/CRF-MG** — PT nativo, grátis, só interações graves (menos fadiga de alerta). Tratar como *sem SLA*.

**Fallback obrigatório (offline/sem terceiros):** **DDInter 2.0** baixado e versionado no repo (CC BY-NC-SA, uso pessoal não-comercial). Elimina indisponibilidade e vazamento de PHI — nada sai da máquina.

**Descartados:** DrugBank comercial; RxNav apenas para normalização.

## Mapeamento texto-livre → código (parte mais frágil)

- Pipeline: `medication_display` (PT livre) → **princípio ativo/DCB** → código.
- Conversão marca→ativo: **dados abertos ANVISA** (`DADOS_ABERTOS_MEDICAMENTOS.csv`) e **CMED** (coluna SUBSTÂNCIA).
- Chave interna: **princípio ativo (DCI/INN)** normalizado; código padronizado = **ATC** (uso não-comercial) ou RxCUI (só INN inglês).
- Armadilhas: associações fixas (decompor em vários ativos); gírias/erros de grafia; **PT↔INN** (dipirona=metamizol, paracetamol=acetaminophen, AAS=aspirin) → dicionário de sinônimos curado; formas/sal; RxNorm não tem marca brasileira.

## Integração

- `InteractionService.check(list[ativo_normalizado]) -> Alert[]` — **só nomes/códigos de fármaco saem** (nunca PHI).
- **Cache por PAR ordenado** (tabela `drug_interaction_cache(a_code,b_code,severity,evidence,action,reference,checked_at)`), TTL 30–90 d.
- **Timeout curto (2–3 s) + circuito**: `IMSES → cache → DDInter local`. Se tudo falhar → `[]` com `status=unavailable`; UI mostra "checagem indisponível", nunca bloqueia.
- **Severidade advisory**: destaque só grave/major; moderado em cinza; leve/unknown oculto. Nunca bloqueia prescrição/Memed. Sempre "não substitui avaliação clínica".

## Riscos

- Falsos positivos → exigir match exato no princípio ativo; mostrar referência; começar só grave.
- Falsos negativos → "ausência de alerta ≠ ausência de interação"; cobrir com as duas bases.
- Disponibilidade (IMSES sem SLA; Memed fora 0–6 h/fins de semana) → DDInter local sempre-on + cache + degradar silencioso.
- Licença: DDInter é NC — ok uso pessoal/familiar, **não** serve como produto. Revisitar antes de distribuir.
- PHI: nenhuma fonte recebe dado do paciente.

## Fontes

- NLM RxNav DDI descontinuado: https://lhncbc.nlm.nih.gov/RxNav/information/FAQs.html
- RxNav ToS: https://lhncbc.nlm.nih.gov/RxNav/TermsofService.html
- DrugBank ToU: https://trust.drugbank.com/drugbank-trust-center/terms-of-service
- DDInter 2.0: https://ddinter2.scbdd.com/terms/ · https://ddinter2.scbdd.com/download/
- IMSES/CRF-MG: https://imses.crfmg.org.br/ · https://imses.crfmg.org.br/api/docs/
- Memed (interações, in-widget): https://suporte-medico.memed.com.br/hc/pt-br/articles/8564150172571
- Memed Backend API: https://doc.memed.com.br/docs/backend-api/
- ANVISA dados abertos: https://dados.anvisa.gov.br/dados/DADOS_ABERTOS_MEDICAMENTOS.csv
- ATC/WHO (não-comercial): https://confluence.hl7.org/spaces/TA/pages/104584082
