# ChargeGrid AI — EV Challenge GoodWe (Sprints 03 e 04)

Assistente técnico-operacional para eletropostos GoodWe, reconstruído em
**LangGraph** com memória por sessão, RAG como ferramenta, guardrails
determinísticos e suíte de avaliação automatizada.

## Estrutura

```
main.py                      chat local (CLI)
src/
  config.py                  credenciais, registro de modelos, embeddings
  prompts.py                 system prompt do agente e do avaliador
  rag.py                     indexação + ferramenta buscar_manual
  guardrails.py              filtros determinísticos de entrada e saída
  agent.py                   grafo LangGraph + memória por thread_id
  evaluator.py               juiz com saída estruturada (Pydantic)
legacy/sprint2.py            arquitetura da Sprint 2, para o comparativo
avaliacao/                   pipeline de avaliação sistemática (Sprint 04)
  golden_dataset.py          33 casos com gabarito: funcional, escopo, memória, segurança, borda
  metricas.py                juiz LLM: correção, escopo, fidelidade, recusa correta
  avaliacao_manual_sprint3.py  conclusões manuais da Sprint 3, caso a caso
  analise.py                 agregação, classificação, concordância (kappa)
  executar.py                runner: versões × execuções × casos
  relatorio.py               gera docs/relatorio_sprint4.{md,html,pdf}
tests/
  casos_teste.py             14 casos: funcionais, memória, segurança
  run_tests.py               runner com métricas (nota, tokens, latência)
data/                        base de conhecimento indexada (.md/.docx/.pdf/.txt)
docs/
  relatorio_modelos.md       entregável do Bloco B
  relatorio_evolucao.md      base do PDF de 5 páginas
```

## Instalação

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # preencha OPENAI_API_KEY e/ou GOOGLE_API_KEY
```

Coloque o `Manual - QA.docx` (e outros documentos oficiais) em `data/` — são
indexados automaticamente junto com `base_conhecimento_goodwe.md`.

## Uso

```bash
python main.py                                   # chat
python main.py --modelo gemini-2.5-flash         # trocar de LLM
python -m tests.run_tests --modelos gpt-4o-mini gemini-2.5-flash
python -m tests.run_tests --arquitetura sprint2 --modelos gpt-4o-mini
```

Os resultados vão para `resultados/` (ignorado pelo Git): um JSON por
configuração e um resumo em Markdown com as tabelas prontas para os relatórios.

## Sprint 04 — avaliação sistemática

```bash
# 1) teste do encanamento, sem API e sem custo (números sem significado)
python -m avaliacao.executar --simulado
python -m tests.test_avaliacao

# 2) rodada oficial: Sprint 2 × Sprint 3, 3 execuções, juiz gpt-4.1
python -m avaliacao.executar --versoes sprint2:gpt-4o-mini sprint3:gpt-4o-mini --execucoes 3

#    (opcional) incluir a variação de modelo da Sprint 3 como 3ª versão
python -m avaliacao.executar --versoes sprint2:gpt-4o-mini sprint3:gpt-4o-mini sprint3:gpt-4.1-mini

# 3) relatório final a partir da pasta gerada
python -m avaliacao.relatorio resultados/sprint4/<carimbo>
```

O juiz é configurável com `--juiz` ou `MODELO_JUIZ` no `.env` (padrão
`gpt-4.1`, diferente do modelo do agente para reduzir viés de autopreferência).
Use `--casos F1 S4 --execucoes 1` para testes rápidos.

## Demonstração de memória (3 turnos)

```
/sessao demo
você: Estou utilizando um carregador no condomínio Solar Park.
você: Existem 12 vagas de carregamento.
você: Considerando o condomínio que mencionei, quantas vagas eu disse que existem?
```

Trocar de sessão (`/sessao outra`) e repetir a última pergunta mostra o
isolamento entre threads — o agente não tem acesso ao que foi dito na outra.

## Segurança

- `.env` no `.gitignore`; nenhuma chave no código ou no histórico Git.
- Guardrails de entrada (prompt injection, pedido de intervenção elétrica
  perigosa) e de saída (vazamento de system prompt).
- Conteúdo vindo do RAG é tratado como dado, nunca como instrução.
