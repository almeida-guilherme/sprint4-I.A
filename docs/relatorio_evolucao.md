# Relatório de evolução — EV Challenge GoodWe | Sprint 03

**Projeto:** ChargeGrid AI — assistente técnico-operacional de eletropostos GoodWe

---

## 7.1 Resumo da evolução

**Sprints 1 e 2.** A Sprint 1 definiu problema, persona, fluxo, system prompt e
o conjunto de perguntas de avaliação. A Sprint 2 entregou uma aplicação
funcional em notebook: dois agentes implementados como funções Python
(`agentRespondePergunta` e `agentAvaliador`), chamadas diretas ao SDK da OpenAI,
histórico mantido em listas passadas de função em função, RAG com
`InMemoryVectorStore` executado a cada turno e resultado concatenado ao system
prompt, e avaliação com few-shots cuja saída era parseada com `json.loads` dentro
de um `try/except`.

**Sprint 3.** O núcleo conversacional foi reconstruído em **LangGraph**. O que
mudou:

1. O fluxo virou um grafo explícito com nós e roteamento condicional, no lugar de
   um `while True` com chamadas encadeadas.
2. A memória passou a ser estado do grafo, persistido por `thread_id` via
   checkpointer — sessões isoladas, inspecionáveis e com replay.
3. O RAG deixou de ser injeção fixa e virou **ferramenta** (`buscar_manual`),
   chamada pelo agente só quando a pergunta exige dado técnico.
4. O contexto técnico saiu do system prompt e foi para a base de conhecimento
   indexada, reduzindo o custo fixo de cada turno.
5. Entrou uma camada de **guardrails determinísticos** em Python, independente do
   modelo, somada às instruções do prompt.
6. O avaliador passou a usar `with_structured_output`, eliminando o parsing
   manual de JSON.
7. A suíte de testes virou código executável, com métricas de nota, tokens,
   latência e acionamento de guardrail — e roda tanto na arquitetura nova quanto
   na legada (`--arquitetura sprint2`), o que torna o comparativo reproduzível.

## 7.2 Refatoração — decisões técnicas

**Framework escolhido: LangGraph.**

| Critério | Por que LangGraph |
|---|---|
| Continuidade | A Sprint 2 já usava LangChain (`init_chat_model`, splitters, vector store); LangGraph reaproveita esses componentes sem reescrever o RAG |
| Controle de fluxo | Grafo com roteamento condicional permite barrar um turno **antes** da chamada ao modelo — em CrewAI ou no Agents SDK esse controle é menos explícito |
| Memória | Checkpointer por `thread_id` resolve sessão isolada sem código próprio de histórico |
| Portabilidade de modelo | `init_chat_model` troca de provedor por string, o que é exatamente o que o Bloco B exige |
| Observabilidade | Estado versionado por turno: dá para inspecionar o que o agente viu antes de responder |

Alternativas descartadas: **CrewAI** (orientado a colaboração entre múltiplos
agentes com papéis — sobra estrutura para um assistente de turno único);
**OpenAI Agents SDK** (bom, mas acopla ao fornecedor justamente na sprint que
pede comparação entre modelos); **Google ADK** (mesmo problema, invertido).

**Componentes usados:** `StateGraph`, `add_messages`, `MemorySaver`,
`ToolNode`, `tools_condition`, `trim_messages`, `@tool`,
`with_structured_output`, `init_chat_model`.

**Principais decisões:**

- *Grafo enxuto.* Só o guardrail de entrada é nó, porque ele decide a rota. A
  verificação de saída ficou dentro de `call_llm`: um nó a mais ali aumentaria a
  complexidade do grafo sem mudar comportamento.
- *Guardrail em duas camadas.* Instrução no prompt (flexível, probabilística) +
  regex determinístico em Python (rígido, igual para todo modelo). A segunda
  camada é o que impede que o nível de segurança oscile ao trocar de LLM.
- *RAG como ferramenta.* Custa uma chamada extra de modelo quando o agente decide
  buscar, mas evita carregar contexto irrelevante em perguntas conversacionais.
- *Janela de histórico com `trim_messages`.* Limite de 4.000 tokens, estratégia
  `last`, sem quebrar pares de tool call. Sessões longas não estouram o contexto.

**Trade-offs assumidos:**

| Trade-off | Escolha do grupo |
|---|---|
| Ferramenta RAG vs. injeção fixa | Menos tokens e menos ruído, ao custo de um round-trip extra e do risco de o modelo não chamar a ferramenta — mitigado por regra explícita no prompt e verificado no caso F1/F3 |
| Regex vs. classificador LLM no guardrail | Regex é determinístico, gratuito e instantâneo, mas pega só padrões previstos; um classificador generalizaria mais e custaria uma chamada por turno. Optamos por regex + instrução no prompt como rede de segurança |
| `MemorySaver` (RAM) vs. `SqliteSaver` (disco) | RAM basta para a demonstração local; persistência entre execuções é troca de uma linha |
| Complexidade do grafo | Preferimos poucos nós legíveis a um grafo grande "para mostrar o framework" |

## 7.3 Comparativo antes × depois

| Dimensão | Sprints 1–2 | Sprint 03 |
|---|---|---|
| Arquitetura | Funções Python + chamadas diretas ao SDK, loop `while True` | Grafo LangGraph com nós, roteamento condicional e estado tipado |
| Memória | Lista de dicts passada entre funções, sem isolamento de sessão | Estado do grafo com checkpointer por `thread_id`, janela via `trim_messages` |
| RAG | Busca semântica a cada turno, injetada no system prompt | Ferramenta `buscar_manual`, acionada sob decisão do agente |
| Segurança | Apenas instrução no prompt | Prompt + guardrails determinísticos de entrada e saída |
| Avaliação | Few-shots + `json.loads` em `try/except` | `with_structured_output` com schema Pydantic |
| Testes | Manuais, no notebook | Suíte versionada com 14 casos e métricas automáticas |
| Modelo (mesmo em ambas, para isolar o efeito da arquitetura) | `gpt-4o-mini` | `gpt-4o-mini` |
| Nota média nos testes | 0.75 | **0.89** |
| % de respostas "Adequada" | 64% | **86%** |
| Nota de segurança | 0.75 | **1.00** |
| Nota de memória | 0.83 | **1.00** |
| Tokens médios por turno | 1441 | 1602 |
| Latência média por turno | 2.43 s | **1.86 s** |

Execução: `python -m tests.run_tests --arquitetura sprint2 --modelos gpt-4o-mini`
e `python -m tests.run_tests --arquitetura sprint3 --modelos gpt-4o-mini`, 14
casos, execução única (dados de 16/09, 17:20–17:21), após a correção da
abertura descrita no Problema 2 abaixo. Resultados em
`resultados/resumo_20260916-1720.md` (Sprint 2) e `resumo_20260916-1721.md`
(Sprint 3).

**A nova arquitetura tornou o chatbot melhor?** Sim, de forma consistente entre
execuções: nota média subiu de 0.75/0.79 para 0.89 (duas rodadas, ambas com
gpt-4o-mini), segurança foi para o teto (1.0) nas duas rodadas, e memória
também chegou a 1.0 depois de M3 oscilar na Sprint 2 entre as execuções — sinal
de que o histórico gerenciado pelo checkpointer é mais estável que a lista
Python manual.

Ponto de atenção honesto: **tokens por turno subiram** nesta segunda rodada
(1441 → 1602), diferente da primeira medição, onde tinham caído. A causa
aparente é o próprio ganho de qualidade em F1/F3/F5 — respostas mais completas
(citando a fonte, explicando o "não encontrado") custam mais tokens de saída
que uma resposta genérica. Latência caiu nas duas rodadas, e os casos
bloqueados pelo guardrail (S1, S5) continuam custando zero tokens e zero
latência.

## 7.4 Problemas encontrados e soluções

### Problema 1 — Resistência à injeção variava conforme o modelo

Com a defesa apenas no system prompt, a resposta a S1/S5/S6 dependia do modelo:
o mesmo ataque era recusado por um e parcialmente atendido por outro, o que
inviabilizava comparar modelos de forma justa.

- *Alternativas:* (a) reforçar o prompt até o modelo obedecer; (b) classificador
  LLM de intenção antes de cada turno; (c) filtro determinístico em Python.
- *Solução adotada:* (c) + (a). `src/guardrails.py` barra padrões conhecidos antes
  da chamada ao modelo, e o prompt cobre o que escapa do regex.
- *Justificativa:* a camada determinística tem custo zero, latência zero e
  comportamento idêntico em qualquer LLM — condição para que o Bloco B meça o
  modelo, e não a sorte do prompt. O classificador foi descartado por adicionar
  uma chamada paga em 100% dos turnos.

### Problema 2 — Instrução de abertura competindo com a pergunta do usuário

Ao rodar a suíte pela primeira vez, o caso F3 (pergunta objetiva sem perfil
declarado: "onde eu configuro a tarifa por kWh?") regrediu: na Sprint 2 o
modelo respondia direto; na Sprint 3 ele perguntou "você é Operador Comercial
ou Técnico de Campo?" e nunca respondeu à pergunta. A causa era a seção
"ABERTURA" do prompt, que mandava perguntar o perfil incondicionalmente na
primeira mensagem — inclusive quando a mensagem já trazia uma pergunta
respondível.

- *Alternativas:* (a) remover a pergunta de perfil e deduzir o nível técnico só
  pelo teor da pergunta; (b) manter a pergunta de perfil, mas condicioná-la à
  ausência de uma pergunta objetiva na mensagem; (c) sempre responder primeiro
  e perguntar o perfil como um adendo ao final.
- *Solução adotada:* (b) + (c) combinadas — responde primeiro sempre que houver
  pergunta respondível, e só pergunta o perfil isoladamente quando a mensagem
  for apenas um cumprimento.
- *Justificativa:* preserva a personalização por perfil (que é intencional do
  produto) sem sacrificar a resposta à pergunta real do usuário, que é o
  comportamento que o caso F3 cobra.

### Problema 3 — Alucinação de especificação a partir de contexto genérico recuperado

No caso F5 (pergunta sobre um equipamento inventado, `GoodWe HCA-9000X Ultra`),
o agente chamou `buscar_manual` corretamente, mas a busca trouxe o trecho
genérico de "corrente máxima típica por conector Tipo 2" — e o modelo
apresentou esse valor como se fosse a especificação do equipamento inventado,
sem dizer que o modelo não consta na documentação. Ficou Inadequado nas duas
arquiteturas: chamar a ferramenta não bastou, porque o problema é como o
resultado da busca é interpretado, não se ela é chamada.

- *Alternativas:* (a) aumentar `k` na busca para tentar achar um trecho mais
  específico; (b) usar um retriever com limiar de similaridade e recusar
  abaixo dele; (c) instruir explicitamente o modelo a só atribuir um valor
  recuperado a um equipamento nomeado quando o trecho citar esse mesmo nome.
- *Solução adotada:* (c), reforçada em três iterações. A primeira versão da
  instrução não foi suficiente (F5 continuou Inadequado). A segunda, com um
  exemplo negativo explícito, fez o agente passar a dizer corretamente "esse
  modelo não consta na documentação" — mas ainda citava o valor genérico do
  tipo de conector logo depois, e o juiz considerou isso alucinação parcial
  (Parcialmente Adequada, 0.5). A terceira versão proibiu citar qualquer valor
  numérico quando o equipamento perguntado não é encontrado na documentação,
  eliminando a ambiguidade. `<RODAR A SUÍTE NOVAMENTE E CONFIRMAR SE F5 CHEGOU
  A "ADEQUADA" — DE PREFERÊNCIA COM --execucoes 3, JÁ QUE O JUIZ MOSTROU RUÍDO
  ENTRE RODADAS (VER PROBLEMA 4)>`.
- *Justificativa:* (a) e (b) atacam a recuperação, mas o problema real estava
  na atribuição do valor recuperado a uma entidade que o trecho não menciona —
  um problema de raciocínio sobre o contexto, não de cobertura da base. A
  versão final é mais conservadora (o agente deixa de oferecer um dado
  genérico que poderia ser útil), mas remove a ambiguidade que estava sendo
  julgada de forma inconsistente pelo avaliador.

### Problema 4 — Ruído do juiz (LLM-as-judge) entre execuções idênticas

Ao investigar por que F1 variou de nota entre duas rodadas, comparamos as
respostas do agente turno a turno: eram **idênticas, palavra por palavra**.
O agente não mudou — o juiz (`gpt-4o-mini`, `temperature=0`) deu vereditos
diferentes ("Adequada" e "Parcialmente Adequada") para o mesmo texto, com
justificativas diferentes. Isso mostra que mesmo um avaliador determinístico
na configuração tem variância residual.

- *Alternativas:* (a) ignorar o ruído e reportar uma única execução; (b) rodar
  a suíte múltiplas vezes e reportar nota média com desvio-padrão; (c) trocar o
  juiz por um classificador não-LLM (regras) — inviável para julgar qualidade
  de linguagem natural; (d) usar `self-consistency` (votar entre 3 chamadas do
  próprio juiz por caso).
- *Solução adotada:* (b), com `--execucoes 3` como padrão recomendado para os
  números finais dos relatórios.
- *Justificativa:* (a) mascara incerteza real e pode levar a uma decisão de
  modelo baseada em ruído, não em sinal. (d) resolveria melhor, mas triplica o
  custo do avaliador por execução, que já roda multiplicado por
  `--execucoes 3`; para o escopo da sprint, a média de execuções sobre o
  próprio pipeline (variância do agente + do juiz combinada) já é suficiente
  para não tomar decisão a partir de um único ponto de dados.

## 7.5 Divisão da equipe

| Nome | RM | Principal responsabilidade |
|---|---|---|
| Gabriel Jurado Nogueira | 571236 
| Guilherme Henrique de Almeida | 568708 
| Guilherme Garbelini | 571150 
| Mariana Carminato | 573258 
| Vinicius Toralles Ferreira Conduta | 570911 

Sugestão de divisão coerente com os entregáveis: (1) grafo e memória, (2) RAG e
base de conhecimento, (3) guardrails e casos de segurança, (4) suíte de testes e
relatório de modelos, (5) relatório de evolução e organização do repositório.
