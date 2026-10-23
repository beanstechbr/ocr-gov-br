# OCR Gov BR — OCR e anonimização abertos para órgãos públicos brasileiros

Repositório público da **Beans Tech** com o stack de tratamento documental que oferecemos,
gratuitamente, a órgãos públicos: OCR de alta fidelidade para documentos judiciais e
administrativos + engine de anonimização LGPD em cascata, tudo executável **on-premise**,
sem que nenhum dado sensível saia da rede do órgão.

## Por que existe

Órgãos públicos brasileiros operam sobre milhões de páginas escaneadas — autos processuais,
prontuários, formulários — frequentemente com fontes corrompidas, carimbos e manuscritos.
Ao mesmo tempo, a LGPD exige anonimização robusta antes de qualquer publicação ou análise.
Este repositório documenta e distribui a solução aberta para os dois problemas.

## Componentes

### 1. OCR documental (OCR Beans)
- Detecção automática de PDFs com fontes corrompidas (comum em sistemas judiciais) e
  aplicação de OCR apenas onde necessário (páginas com camada de texto usam extração nativa).
- Pipeline em lote para grandes volumes (petições, laudos, autos).
- Motores de peso aberto avaliados para português: `dots.ocr` (MIT), `PaddleOCR-VL`
  (Apache-2.0, 109 idiomas), com fallback determinístico (PyMuPDF/Tesseract).
- Preservação de layout: tabelas, campos, bounding boxes, ordem de leitura.

### 2. Engine de anonimização (cascata L0–L5, fail-closed)
```
L0 Normalização (NFKC, reconstituição de tokens quebrados pelo OCR)
L1 Determinístico (regex + validação de dígito: CPF/CNPJ/OAB — zero falso positivo)
L2 Gazetteers locais (PEPs, magistrados/OAB, hospitais, escolas)
L3 NER local em CPU (spaCy pt / BERTimbau ONNX)
L4 Ensemble contextual (regras cruzadas L1×L2×L3)
L5 Verificação pré-publicação com detector independente + auditoria amostral
```
- **Fail-closed**: na dúvida, anonimiza. Pseudônimos consistentes preservam a análise.
- Dois modos: **pseudonimização reversível** (chave no KMS do órgão — art. 13, LGPD) ou
  **anonimização irreversível** (publicação — art. 12, LGPD).
- Meta de qualidade: recall ≥99% em identificadores diretos, ≥95% em nomes, medido em
  corpus dourado interno (nunca publicado).
- **Nenhum dado bruto toca API de LLM** — modelos externos só veem texto já anonimizado.

### 3. IA soberana on-premise
- Tudo roda em hardware do próprio órgão (CPU para a anonimização; GPU local para OCR/LLM).
- Modelos abertos recomendados: GLM (texto/OCR), Qwen-VL (visão documental), MedGemma
  (saúde), Whisper PT-BR (transcrição de audiências/consultas).
- Compatível com a Resolução CNJ 332/2020 (governança, transparência e auditabilidade de IA
  no Judiciário).

## Arquitetura — uma engine, três verticais

```
beanstech.io          → infra/gateway (MCP, Keycloak, KMS)
OCR Beans             → engine de OCR
jogolimpo.ai          → O ANONIMIZADOR (engine única, marca LGPD)
   ├─ rulepack JUS    → gazetteers: magistrados, OAB, CNJ, varas
   ├─ rulepack MED    → gazetteers: hospitais, CRM, CID-10
   └─ rulepack FIN    → gazetteers: PEPs, contas, CVM/Bacen

medpubbr / juspubbr / finpubbr → portais que PUBLICAM dados já anonimizados
ragjur / ragmed / ragfin       → retrieval sobre o resultado
```

**Decisão de desenho: um anonimizador só.** As verticais são rulepacks (listas e regras
carregadas por perfil), nunca código duplicado: homologação única pelo órgão, correção de
bug em um lugar só, métricas de qualidade num corpus dourado único e política fail-closed
uniforme. A engine é o pedágio obrigatório entre qualquer documento público e qualquer
API de IA por assinatura.

## Como um órgão público adota

1. **Piloto gratuito** sobre um lote real de documentos do órgão (nós executamos, o órgão mede).
2. Formalização por **Termo/Acordo de Cooperação Técnica** (modelo AGU — EN 200/2017), sem
   transferência de recursos.
3. Implantação on-premise com documentação, treinamento e código aberto.

## Licença

Apache-2.0. O código é aberto: qualquer órgão pode usar, auditar e adaptar.

## Contato

Beans Tech — contato@beanstech.com.br
