# OpenAvisio e emissão de prescrições eletrônicas — enquadramento regulatório (BR e UE)

**Data:** 2026-10-08 · **Escopo:** uso pessoal/familiar, um único médico, software auto-hospedado (AGPL-3.0) com integração Memed, certificado ICP-Brasil próprio
**Método:** fontes primárias (gov.br/ANVISA, Planalto, CFM, EUR-Lex/MDCG, Memed). Toda afirmação factual traz URL e artigo. Itens não verificáveis estão marcados como **não confirmado**.

---

## English executive summary

**Go/no-go: conditional GO** for one physician using the software for himself and his family in Brazil, **provided** that (i) prescription issuance runs through Memed in **production** as the RDC Anvisa 1.000/2025-compliant *electronic prescription service* integrated to the SNCR; (ii) Memed requests the SNCR numbering (OpenAvisio does not re-implement SNCR); (iii) documents are signed with a **qualified ICP-Brasil signature**; (iv) OpenAvisio contains **no clinical decision-support** (no diagnosis/treatment/dose suggestion); (v) signed documents are retained; and (vi) the software is **not distributed** or used to serve third parties.

Under Brazilian law the **physician remains the issuer** (RDC 1.000/2025, art. 6), and the platform is *not* the issuer — but the platform that numbers/transmits is a **regulated intermediary** ("serviço de prescrição eletrônica", arts. 4–5, 17). Memed occupies that role, not OpenAvisio. Issuing prescriptions does **not** turn a personal/family record into a **SaMD**: ANVISA's RDC 657/2022 Q&A expressly excludes record/communication software; ANVISA/MDR only bite when the software itself suggests diagnosis, triage or treatment. Under **EU MDR 2017/745 + MDCG 2019-11**, storage/communication software is likewise not medical device software; "placing on the market" (distribution) is the trigger — personal/family use is not. **NO-GO** on any production deployment that adds clinical decision-support, or that distributes the software, without a full SaMD/CE-marking pathway.

---

## Resposta curta (go/no-go)

- **Quem emite e numera:** o **prescritor** (médico com CRM) é o emissor. A numeração é concedida pelo SNCR ao prescritor; o *serviço de prescrição eletrônica* apenas **requisita** essa numeração em nome dele. RDC Anvisa 1.000/2025, art. 6: *"A emissão dos receituários eletrônicos … é de responsabilidade exclusiva do prescritor, sendo vedada sua emissão por instituições ou por terceiros em seu nome."*
- **Memed como mera ferramenta:** usar a Memed **mantém o médico como emissor** e **não** transfere a autoria. Porém a Memed **é parte regulada**: ela é o *"serviço de prescrição eletrônica"* que, sob a RDC 1.000/2025 (arts. 4–5, 17), precisa estar integrada ao SNCR por API, requisitar a numeração, vinculá-la ao prescritor autorizado, entregar o receituário ao paciente e garantir rastreabilidade. Ou seja: a plataforma **não vira o emitente**, mas **entra no perímetro regulatório** como prestador.
- **SaMD no Brasil:** um prontuário pessoal/familiar que apenas registra, exibe, comunica e imprime a prescrição **não é** software como dispositivo médico (RDC 657/2022 + Q&A da Anvisa). Ele **vira** SaMD se passar a fazer triagem automática, sugerir diagnóstico/tratamento ou calcular dose. Como é de uso exclusivo e não distribuído, ainda cabe a exclusão de *in-house* da RDC 657/2022, art. 5º.
- **UE:** o mesmo raciocínio. Sob MDR 2017/745 + MDCG 2019-11, software de armazenamento/comunicação não é MDSW; o gatilho é a *colocação no mercado* (distribuição). Uso pessoal/familiar não coloca produto no mercado. Prescrição na UE é matéria **nacional**, não de MDR.
- **Veredito:** **GO condicionado** para uso pessoal/familiar no Brasil, cumpridas as condições da seção "Caminho mínimo conforme". **NO-GO** para distribuição ou atendimento a terceiros sem trilha completa de SaMD/CE.

---

## Base legal BR

### 1. Prescrição eletrônica de controlados — RDC Anvisa 1.000/2025

**Instrumento:** Resolução da Diretoria Colegiada Anvisa nº 1.000, de **11/12/2025** (DOU 15/12/2025, Seção 1, p. 174), em vigor **60 dias após a publicação** (≈13/02/2026), conforme art. 27. Dispõe sobre requisitos de controle para Notificações de Receita, Receitas de Controle Especial e Receitas sujeitas à retenção emitidas em meio eletrônico.
Fonte: https://anvisalegis.datalegis.net/action/ActionDatalegis.php?acao=abrirTextoAto&cod_menu=8499&cod_modulo=293&link=S&numeroAto=00001000&orgao=RDC/DC/ANVISA/MS&seqAto=000&tipo=RDC&valorAno=2025 · DOU: https://in.gov.br/web/dou/-/resolucao-da-diretoria-colegiada-anvisa-n-1.000-de-11-de-dezembro-de-2025-675167858

Pontos decisivos:
- **Art. 4º** — os receituários eletrônicos devem ser gerados **exclusivamente em serviços de prescrição eletrônica integrados ao SNCR por API**; § 2º **veda** a emissão por serviços não integrados.
- **Art. 5º** — obrigações do *serviço de prescrição eletrônica*: requisitar a numeração ao SNCR (requisito de assinatura qualificada foi alterado — ver RDC 1.028/2026), vincular a numeração ao prescritor autorizado, disponibilizar o receituário ao paciente e assegurar rastreabilidade.
- **Art. 6º** — **emissão é responsabilidade exclusiva do prescritor**; vedada emissão por instituições ou terceiros em seu nome.
- **Art. 8º** — Notificações de Receita e Receitas de Controle Especial eletrônicas devem ser **subscritas com assinatura eletrônica qualificada**.
- **Art. 11** — Receitas sujeitas à retenção (antimicrobianos/GLP-1) exigem assinatura **avançada ou qualificada**.
- **Art. 17** — descumprimento dos requisitos do SNCR acarreta **suspensão imediata do acesso** do serviço de prescrição eletrônica ao Sistema.
- **Art. 26** — descumprimento configura infração sanitária (Lei 6.437/1977).

**Alteração:** RDC Anvisa nº **1.028, de 01/06/2026**, alterou o art. 5º, I (removeu a exigência de assinatura qualificada na *requisição* da numeração) e o art. 16 (prazo do SNCR). Fonte: https://anvisalegis.datalegis.net/action/ActionDatalegis.php?acao=abrirTextoAto&cod_menu=9431&cod_modulo=310&link=S&numeroAto=00001028&orgao=RDC/DC/ANVISA/MS&seqAto=000&tipo=RDC&valorAno=2026

**SNCR:** instituído pela RDC nº **873, de 27/05/2024** (arts. 3º, VIII, e 20 da RDC 1.000/2025). Em operação para Vigilâncias Sanitárias desde 2024; uso obrigatório a partir de 01/01/2025. Fonte: https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa/2024/sistema-nacional-de-controle-de-receituarios-ja-esta-em-vigor

**Prazo crítico:** a RDC 1.028/2026 fixou **30/09/2026** como data-limite para a Anvisa disponibilizar o SNCR para requisição de numeração e registro de utilização dos receituários eletrônicos (art. 16, redação vigente). A documentação técnica da API e o ambiente de treinamento foram publicados; a fase de integração com plataformas iniciou em junho de 2026. **Não confirmado:** se, em 08/10/2026, a funcionalidade eletrônica do SNCR para *todas* as 7 categorias já está plenamente operacional e homologada para integradores privados — o cronograma depende de atos e comunicados subsequentes da Anvisa. Fonte: https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa/anvisa-publica-documentacao-tecnica-para-integracao-de-sistemas-de-prescricao-eletronica-ao-sncr · https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/sncr/receituario-eletronico

### 2. Assinatura eletrônica em saúde — Lei 14.063/2020

**Lei nº 14.063, de 23/09/2020** (DOU 24/09/2020):
- **Art. 13** — receituários de medicamentos sujeitos a controle especial e atestados médicos em meio eletrônico só são válidos quando subscritos com **assinatura eletrônica qualificada** (ICP-Brasil) do profissional de saúde.
- **Art. 14** — os demais documentos de saúde são válidos com assinatura **avançada ou qualificada**.
- **Art. 15** — altera o **art. 35 da Lei 5.991/1973**: § 2º (receitas eletrônicas válidas com assinatura avançada ou qualificada, ressalvados atos internos hospitalares) e § 3º (**obrigatória** a qualificada para receituários de controlados e atestados).
Fontes: https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2020/lei/l14063.htm · https://www.planalto.gov.br/ccivil_03/leis/l5991.htm

Definições: "assinatura qualificada" usa certificado ICP-Brasil (RDC 1.000/2025, art. 3º, II); "avançada" usa certificado não ICP-Brasil (art. 3º, I). O BirdID do médico, sendo ICP-Brasil, atende ao requisito qualificado.

### 3. Emissão de documentos médicos — Resoluções CFM

- **Resolução CFM nº 2.299/2021**, de 30/09/2021 (DOU 26/10/2021): *"Regulamenta, disciplina e normatiza a emissão de documentos médicos eletrônicos."* Exige assinatura digital certificada pela **ICP-Brasil** (nível de segurança 2) e conteúdo mínimo (nome, CRM, endereço, nome/identificação do paciente, data/hora, assinatura digital). Fontes: https://sistemas.cfm.org.br/normas/arquivos/resolucoes/BR/2021/2299_2021.pdf · https://portal.cfm.org.br/noticias/cfm-atualiza-plataforma-que-permite-aos-medicos-prescreverem-receitas-digitalmente/
- **Resolução CFM nº 2.381/2024**, de 20/06/2024: normatiza a emissão de documentos médicos (atestado, laudo, relatório, solicitação de exames etc.); documentos eletrônicos exigem **assinatura qualificada** do médico. Fonte: https://sistemas.cfm.org.br/normas/visualizar/resolucoes/BR/2024/2381
- A plataforma de prescrição eletrônica do próprio CFM (`prescricao.cfm.org.br`) é gratuita e segue a RDC 1.000/25 — alternativa ao Memed caso se queira evitar dependência comercial. Fonte: https://prescricao.cfm.org.br/

### 4. Software como dispositivo médico (SaMD) — RDC 657/2022

**RDC nº 657, de 24/03/2022** (DOU 30/03/2022; retificação 08/06/2022), em vigor desde **01/07/2022**. Dispõe sobre a regularização de SaMD.
Fontes: https://www.in.gov.br/web/dou/-/resolucao-de-diretoria-colegiada-rdc-n-657-de-24-de-marco-de-2022-389603457 · https://anvisalegis.datalegis.net/action/ActionDatalegis.php?acao=abrirTextoAto&tipo=RDC&numeroAto=00000657&seqAto=000&valorAno=2022&orgao=RDC/DC/ANVISA/MS

- **Art. 1º, § 2º** — a resolução **não se aplica** a software: (I) de bem-estar; (II) de lista de produtos não regulados; (III) **usado exclusivamente para gerenciamento administrativo/financeiro**; (IV) que processa dados demográficos/epidemiológicos sem finalidade clínica; (V) embarcado em dispositivo médico.
- **Art. 3º, VII** — define SaMD como software destinado a uma ou mais **indicações médicas** (inclui SaaS).
- **Art. 5º** — SaMD **desenvolvido internamente (*in-house*) e de uso exclusivo** do serviço de saúde, classes de risco I e II, **não é passível de regularização** na Anvisa, desde que não interfira em dispositivo médico regularizável.
- Classificação de risco pela **RDC nº 751/2022** (Regra 11, análoga à europeia).

**Interpretação oficial (Perguntas & Respostas da Anvisa sobre a RDC 657/2022):** plataformas de **prontuário eletrônico, agenda, telemedicina e comunicação** que apenas registram, exibem e transmitem dados **não são SaMD**. O software passa a ser SaMD quando faz **triagem automática, sugestão de diagnóstico ou sugestão de tratamento**. Fontes: https://www.gov.br/anvisa/pt-br/centraisdeconteudo/publicacoes/produtos-para-a-saude/manuais/software-como-dispositivo-medico-perguntas-e-respostas · https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa/2022/software-como-dispositivo-medico-perguntas-e-respostas

**Revisão pendente:** em fevereiro de 2025 a Anvisa publicou **minuta** de revisão da RDC 657/2022 (IA, PCCP) — **não finalizada**; vale o texto de 2022. **Não confirmado:** número/data do ato final de revisão.

---

## Base legal UE

**Regulamento (UE) 2017/745 — MDR.** Artigo 2(1): "dispositivo médico" abrange *software* destinado pelo fabricante a finalidades médicas (diagnóstico, prevenção, monitorização, predição, prognóstico, tratamento ou alívio de doença etc.); art. 2(12) define "finalidade prevista" a partir do que o **fabricante** declara. Fonte: https://www.medical-device-regulation.eu/2019/07/10/mdr-article-2-definitions/

**MDCG 2019-11** (Guia de Qualificação e Classificação de Software sob MDR/IVDR; original out/2019, **Rev.1 de junho/2025**): software só é MDSW se tiver **finalidade médica própria**. Ficam **fora** (etapa de qualificação) o software que não realiza ação sobre os dados além de **armazenamento, arquivamento, comunicação, simples busca ou compressão sem perda**. A classificação usa a **Regra 11 do Anexo VIII**: informação para decisão diagnóstica/terapêutica = **classe IIa** (IIb/III conforme gravidade); monitorização de processo fisiológico = IIa/IIb; todo o resto = classe I.
Fontes: https://health.ec.europa.eu/document/download/b45335c5-1679-4c71-a91c-fc7a4d37f12b_en?filename=mdcg_2019_11_en.pdf · https://health.ec.europa.eu/system/files/2020-09/md_mdcg_2019_11_guidance_en_0.pdf

**Aplicação a este caso:** um prontuário familiar que armazena dados e formata/transmite a prescrição **do médico** não tem finalidade médica própria → **não é MDSW**. Se ganhasse cálculo de dose, triagem ou sugestão terapêutica, seria MDSW (Regra 11, tipicamente IIa). O MDR só obriga quem **"coloca no mercado"** / "põe em serviço" como fabricante — **uso pessoal/familiar não é colocação no mercado**. Nota: o MDR **não** regula prescrição; **prescrição é matéria nacional** de cada Estado-Membro (inclusive assinatura eletrônica), fora do âmbito do MDR. **Não confirmado:** requisitos específicos de assinatura eletrônica de receitas por país da UE (não pesquisados em detalhe nesta análise).

---

## Caminho mínimo conforme

### (a) O que já está satisfeito
- Médico devidamente inscrito (CRM) — requisito de "prescritor" da Portaria SVS/MS nº 344/1998 e das resoluções CFM.
- Certificado **ICP-Brasil** próprio (BirdID) — atende à assinatura **qualificada** exigida pela Lei 14.063/2020 (arts. 13/15) e pela RDC 1.000/2025 (art. 8º) para controlados.
- Software que apenas registra/exibe/imprime a prescrição — fora do SaMD pela RDC 657/2022 (art. 1º, § 2º, III) e pelo Q&A da Anvisa.

### (b) O que ele PRECISA fazer
1. **Sair da homologação e usar a Memed em produção** — a integração exige formulário em `memed.com.br/parceiro-software`, termo de aceite assinado e credenciais de produção. A Memed é quem ocupa o papel de *"serviço de prescrição eletrônica"* integrado ao SNCR (RDC 1.000/2025, arts. 4–5), **retirando do OpenAvisio** a obrigação de implementar a API do SNCR. Fontes: https://suporte-medico.memed.com.br/hc/pt-br/articles/53501207014427 · https://doc.memed.com.br/
2. **Garantir assinatura eletrônica qualificada (ICP-Brasil)** em toda prescrição de controlado, com validação pelo serviço do ITI (RDC 1.000/2025, art. 13, I; Lei 14.063/2020, arts. 13/15).
3. **Emitir nos modelos oficiais da Anvisa** — os modelos eletrônicos são padronizados e não customizáveis; exigem numeração individualizada do SNCR (RDC 1.000/2025, arts. 7º; modelos em https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/sncr/receituario-eletronico).
4. **Reter o documento assinado** — guarda do prontuário/prescrição pelo médico; a responsabilidade pela guarda do **registro de utilização** é do **estabelecimento dispensador** (RDC 1.000/2025, art. 14). Recomenda-se reter o PDF assinado conforme regras de prontuário (Lei 13.787/2018 e CFM 1.821/2007 — 20 anos). **Não confirmado:** prazo específico de guarda do receituário eletrônico pelo prescritor na RDC 1.000/2025.
5. **Cadastro prévio para Notificação de Receita "A"/Talidomida** junto à Vigilância Sanitária local, se prescrever esses grupos (Portaria SVS/MS nº 344/1998, art. 40, §§ 1º–4º, com redação da RDC 1.000/2025).
6. **LGPD:** dados de saúde são sensíveis (Lei 13.709/2018, art. 11). Para uso estritamente pessoal/familiar, aplica-se a hipótese de **uso exclusivamente particular/não econômico** (art. 4º, I) — ainda assim, recomenda-se manter o auto-hospedado sem exposição pública e sem compartilhamento com terceiros. **Não confirmado:** extensão exata da excludente do art. 4º da LGPD a um prontuário familiar mantido por médico.

### (c) O que só seria exigido se distribuísse ou atendesse terceiros
- **Distribuir o software (Brasil):** transforma-o em produto colocado no mercado. Se mantiver finalidade apenas de registro/comunicação → segue fora do SaMD; se agregar apoio clínico → **regularização de SaMD** (RDC 657/2022 + RDC 751/2022; classes I/II via notificação, III/IV via registro) e conformidade com RDC 848/2024 (requisitos essenciais), IEC 62304, IEC 62366-1, ISO 14971.
- **Auto-hospedar o serviço de numeração/prescrição (Brasil):** passaria a **ser ele próprio** o *"serviço de prescrição eletrônica"* da RDC 1.000/2025 (arts. 4–5, 17) → integração obrigatória ao SNCR por API, sob pena de vedação/suspensão.
- **Servir pacientes de terceiros:** exige cumprimento pleno de LGPD como controlador, eventual licenciamento sanitário, e cobertura de responsabilidade civil.
- **Distribuir à UE:** o uso pessoal/familiar não é colocação no mercado; distribuir **é** → o desenvolvedor vira **fabricante** sob o MDR (conformidade, avalição de conformidade, marcação CE quando aplicável; se MDSW, classificação pela Regra 11). A exceção *in-house* do MDR (art. 5(5), derrogação por Estado-Membro) só vale para uso **dentro de uma única instituição de saúde** e **não** cobre distribuição.

---

## Riscos e o que NÃO fazer

- **NÃO** embutir no OpenAvisio triagem automática, sugestão de diagnóstico, sugestão de tratamento ou cálculo de dose — isso o converte em **SaMD** (RDC 657/2022) e, na UE, em MDSW (Regra 11), disparando a trilha completa de regularização/marcação CE.
- **NÃO** confundir "não é dispositivo médico" com "não é regulado": a **emissão de prescrição** é regulada (RDC 1.000/2025, Lei 14.063/2020, resoluções CFM). O `docs/regulatory-positioning.md` deve ser **atualizado** para cobrir expressamente a função de prescrição e declarar a **dependência da Memed** como serviço de prescrição integrado ao SNCR (a nota ADR-036 continua válida: implantar em produção exige essa revisão formal — agora ela existe neste relatório).
- **NÃO** manter-se em ambiente de homologação da Memed para emitir prescrição a paciente real: a homologação não gera documento válido em produção; a emissão de controlado em produção depende de numeração real do SNCR.
- **NÃO** reimplementar o SNCR no OpenAvisio: isso faria do próprio software um *serviço de prescrição eletrônica* sujeito à RDC 1.000/2025 — deixe essa camada com a Memed.
- **NÃO** distribuir o software nem usá-lo para pacientes de terceiros sem resolver o item (c) acima.
- **Risco de assinatura:** prescrição de controlado **sem** assinatura qualificada ICP-Brasil é **inválida** (Lei 14.063/2020, art. 15, § 3º; RDC 1.000/2025, art. 8º). Não usar assinatura avançada onde se exige qualificada.
- **Ponto temporal/ambíguo:** o prazo do SNCR (30/09/2026) e eventual operacionalização plena para integradores privados são **recentes e em evolução** — vale conferir comunicados atuais da Anvisa antes de depender do fluxo eletrônico de controlados.

---

## Fontes

1. RDC Anvisa 1.000/2025 (texto consolidado) — https://anvisalegis.datalegis.net/action/ActionDatalegis.php?acao=abrirTextoAto&cod_menu=8499&cod_modulo=293&link=S&numeroAto=00001000&orgao=RDC/DC/ANVISA/MS&seqAto=000&tipo=RDC&valorAno=2025
2. RDC Anvisa 1.000/2025 — DOU — https://in.gov.br/web/dou/-/resolucao-da-diretoria-colegiada-anvisa-n-1.000-de-11-de-dezembro-de-2025-675167858
3. RDC Anvisa 1.028/2026 (altera RDC 1.000/2025) — https://anvisalegis.datalegis.net/action/ActionDatalegis.php?acao=abrirTextoAto&cod_menu=9431&cod_modulo=310&link=S&numeroAto=00001028&orgao=RDC/DC/ANVISA/MS&seqAto=000&tipo=RDC&valorAno=2026
4. Anvisa — SNCR em vigor / RDC 873/2024 — https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa/2024/sistema-nacional-de-controle-de-receituarios-ja-esta-em-vigor
5. Anvisa — Receituário Eletrônico / SNCR — https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/sncr/receituario-eletronico
6. Anvisa — Perguntas & Respostas RDC 1.000/2025 (2ª ed.) — https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/sncr/farmacias/perguntas-e-respostas-rdc-1000-2025-2a-edicao.pdf
7. Anvisa — documentação técnica de integração ao SNCR — https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa/anvisa-publica-documentacao-tecnica-para-integracao-de-sistemas-de-prescricao-eletronica-ao-sncr
8. Lei 14.063/2020 (Planalto) — https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2020/lei/l14063.htm
9. Lei 5.991/1973 (Planalto, art. 35 consolidado) — https://www.planalto.gov.br/ccivil_03/leis/l5991.htm
10. Resolução CFM 2.299/2021 (PDF) — https://sistemas.cfm.org.br/normas/arquivos/resolucoes/BR/2021/2299_2021.pdf
11. CFM — plataforma de prescrição eletrônica / 2.299/21 — https://portal.cfm.org.br/noticias/cfm-atualiza-plataforma-que-permite-aos-medicos-prescreverem-receitas-digitalmente/
12. Resolução CFM 2.381/2024 — https://sistemas.cfm.org.br/normas/visualizar/resolucoes/BR/2024/2381
13. RDC 657/2022 (DOU) — https://www.in.gov.br/web/dou/-/resolucao-de-diretoria-colegiada-rdc-n-657-de-24-de-marco-de-2022-389603457
14. Anvisa — Perguntas & Respostas RDC 657/2022 (SaMD) — https://www.gov.br/anvisa/pt-br/centraisdeconteudo/publicacoes/produtos-para-a-saude/manuais/software-como-dispositivo-medico-perguntas-e-respostas
15. MDR (UE) 2017/745 — Art. 2 (definições) — https://www.medical-device-regulation.eu/2019/07/10/mdr-article-2-definitions/
16. MDCG 2019-11 Rev.1 — https://health.ec.europa.eu/document/download/b45335c5-1679-4c71-a91c-fc7a4d37f12b_en?filename=mdcg_2019_11_en.pdf
17. MDCG 2019-11 (versão original) — https://health.ec.europa.eu/system/files/2020-09/md_mdcg_2019_11_guidance_en_0.pdf
18. Memed — Termos de uso (Médicos) — https://suporte-medico.memed.com.br/hc/pt-br/articles/11822598155419-Termos-de-uso-M%C3%A9dicos
19. Memed — Condições gerais de licenciamento (SaaS) — https://suporte-medico.memed.com.br/hc/pt-br/articles/9419131744155-Condi%C3%A7%C3%B5es-gerais-de-licenciamento-de-uso-da-plataforma-na-modalidade-Software-as-a-Service-SAAS
20. Memed — RDC 1.000/2025 (receitas controladas) — https://suporte-medico.memed.com.br/hc/pt-br/articles/56357536042651-Receitas-controladas-o-que-muda-com-a-RDC-1-000-2025
21. Memed — documentação para desenvolvedores — https://doc.memed.com.br/
22. Memed — integração de prescrição (passo a passo) — https://suporte-medico.memed.com.br/hc/pt-br/articles/53501207014427-Integra%C3%A7%C3%A3o-de-Prescri%C3%A7%C3%A3o-Memed
23. CFM — Prescrição Eletrônica (plataforma gratuita) — https://prescricao.cfm.org.br/
