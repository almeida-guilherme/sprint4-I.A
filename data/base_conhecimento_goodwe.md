# Base de conhecimento — Eletropostos GoodWe (ChargeGrid Intelligence)

> Este arquivo reúne o contexto técnico que, na Sprint 2, ficava embutido no
> system prompt. Agora ele é indexado e consultado sob demanda pela ferramenta
> `buscar_manual`. Coloque também nesta pasta o `Manual - QA.docx` e quaisquer
> outros documentos oficiais (.pdf, .docx, .md, .txt) — todos são carregados
> automaticamente.

## Protocolos suportados

- **OCPP 1.6 (JSON sobre WebSocket)** — compatibilidade com backends legados.
- **OCPP 2.0.1** — Smart Charging, Device Management, ISO 15118.
- **MQTT** — telemetria em tempo real.
- **Modbus TCP/RTU** — integração com medidores de energia externos.

## Tipos de conectores

- **Tipo 2 (IEC 62196-2)** — AC monofásico/trifásico, até 22 kW.
- **CCS2 (Combined Charging System)** — DC, até 150 kW.
- **CHAdeMO** — DC, compatibilidade Japão/legado.

## Códigos de erro

| Código | Significado | Primeira ação recomendada |
|--------|-------------|---------------------------|
| E-01 | Falha de comunicação com o backend OCPP | Verificar conectividade de rede e a OCPP backend URL em Configurações > Sistema |
| E-02 | Temperatura do módulo acima do limite (>65 °C) | Verificar ventilação e obstrução das aberturas; reduzir potência temporariamente |
| E-03 | Falha no medidor de energia interno | Abrir chamado — sessão não deve ser faturada enquanto persistir |
| E-04 | Falha na comunicação com o conector (CP/PP) | Inspecionar cabo e pinos de sinal; testar com outro veículo |
| E-05 | Sobretensão na entrada (>260 V AC) | Verificar rede da concessionária; acionar eletricista habilitado |
| E-06 | Subtensão na entrada (<185 V AC) | Verificar carga do circuito e seção do cabeamento; acionar eletricista habilitado |
| E-07 | Falha no módulo de pagamento/leitor | Reiniciar o módulo pelo Painel; validar integração de pagamento |
| E-08 | Atualização de firmware interrompida | Repetir a atualização com conexão estável; não desligar o equipamento durante o processo |
| E-09 | Falha de aterramento detectada | **Parar o uso do ponto.** Intervenção obrigatória de profissional habilitado (NR-10) |
| E-10 | Módulo de balanceamento de carga não responde | Verificar comunicação Modbus/rede interna entre os pontos |

## Limites de corrente e balanceamento de carga

- Margem de segurança recomendada: usar **85–90% da capacidade nominal do disjuntor**.
- Corrente mínima por ponto em modo balanceado: **6 A** (IEC 61851-1). Abaixo
  disso o veículo interrompe a sessão.
- Corrente máxima típica por conector Tipo 2: **32 A**
  (7,4 kW monofásico / 22 kW trifásico).
- O balanceamento dinâmico distribui a corrente disponível entre as sessões
  ativas, respeitando o mínimo de 6 A por ponto ativo.

## Painel do Operador — seções

- **Dashboard** — sessões ativas, consumo e receita.
- **Eletropostos** — status, configuração e diagnóstico por ponto.
- **Relatórios** — consumo, sessões e faturamento (exportação PDF/CSV).
- **Configurações > Faturamento** — tarifas, meios de pagamento, modelos de cobrança.
- **Configurações > Energia** — balanceamento de carga e limites de potência.
- **Configurações > Sistema** — firmware, rede, OCPP backend URL.
- **Suporte** — abertura de chamados e base de conhecimento.

## Cálculos operacionais de referência

- Tempo estimado de carga (h) = energia necessária (kWh) ÷ potência efetiva (kW).
- Potência AC trifásica (kW) = √3 × tensão (V) × corrente (A) ÷ 1000.
- Potência AC monofásica (kW) = tensão (V) × corrente (A) ÷ 1000.
- A potência efetiva é limitada pelo menor valor entre carregador, cabo, veículo
  e limite configurado no balanceamento.

## Segurança

- Qualquer intervenção física no equipamento exige circuito desenergizado,
  profissional habilitado e observância da NR-10.
- Proteções (disjuntor, DR, aterramento) nunca devem ser desativadas ou
  contornadas para "liberar" carregamento.
- E-09 (falha de aterramento) e E-05/E-06 (sobre/subtensão) indicam problema na
  instalação, não no software: o ponto deve ser bloqueado até avaliação técnica.
