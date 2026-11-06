# Agrosense

Monitoramento de CO₂, umidade do solo e temperatura de uma estufa, com painel web, regras de risco e laudo gerado pela OpenAI.

## Como funciona

```
Arduino (MH-Z19B + sensor de solo) --serial--> server.py --> ecotech_sensor (C) --> painel de CO₂
                                                   |
                                                   +--> analisar_ia.py --> regras, tendência, previsão
                                                   |                   \--> openai_client.py --> laudo
                                                   +--> dados/historico.json (últimos 10 testes)
                                                   +--> index.html (interface)
```

Cada teste coleta 24 leituras (uma a cada 2 s) da porta serial, ou gera leituras simuladas no modo demonstração. O programa em C monta o painel de CO₂, e o Python calcula tendência, previsão de cruzamento do limite, sensores suspeitos, correlações e risco de 0 a 100. A OpenAI devolve o laudo e responde perguntas no chat.

## Requisitos

- Python 3.10+
- gcc
- Chave da OpenAI

## Configuração

Crie um `.env` na raiz:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

`OPENAI_MODEL` é opcional.

## Executar

```
./run.sh
```

Abre `http://localhost:3000`. Sem Arduino conectado, use a fonte Demonstração.

Com Docker:

```
docker compose up --build
docker compose -f docker-compose.yml -f docker-compose.serial.yml up --build
```

O segundo comando repassa a porta serial ao container. Defina `PORTA=/dev/ttyUSB0` se não for `/dev/ttyACM0`.

Variáveis do servidor: `HOST` (padrão `127.0.0.1`), `PORT` (padrão `3000`) e `DADOS` (pasta do histórico).

## Hardware

Firmware em `arduino/ecotech_multi/ecotech_multi.ino`.

| Componente | Pino |
|---|---|
| MH-Z19B RX / TX | 10 / 11 |
| Sensor capacitivo de solo | A0 |

Calibre `SOLO_SECO`, `SOLO_MOLHADO` e `TEMP_OFFSET` no início do firmware. A temperatura vem do próprio MH-Z19B e pode errar alguns graus.

## API

| Rota | Descrição |
|---|---|
| `GET /` | Interface |
| `POST /api/run?fonte=demo\|serial&porta=...` | Roda um teste e grava no histórico |
| `GET /api/historico` | Lista os testes e os padrões do histórico |
| `GET /api/historico/<id>` | Detalhe de um teste |
| `POST /api/historico/analise` | Laudo da IA sobre o histórico (mínimo 2 testes) |
| `POST /api/chat` | Pergunta à IA com o teste atual e o histórico |

## Limites usados

| Canal | Alerta |
|---|---|
| CO₂ | média ≥ 1000 ppm (crítica ≥ 1300) |
| Solo | < 30 % (seco), < 20 % (muito seco) |
| Temperatura | > 32 °C |

## Testes

```
pytest
```

Os testes sobem o servidor de verdade e usam um servidor HTTP local no lugar da OpenAI. Nenhuma chamada sai para a internet, e o gcc é necessário.

## Arquivos

| Arquivo | Função |
|---|---|
| `server.py` | Servidor HTTP, coleta serial, demo e histórico |
| `analisar_ia.py` | Análise estatística, regras e prompts |
| `openai_client.py` | Cliente da OpenAI e leitura do `.env` |
| `ecotech_co2_sensor.c` | Painel de CO₂ lido do Arduino |
| `ecotech_co2.c` | Versão da atividade, com leituras simuladas |
| `index.html` | Interface |
| `test_projeto.py` | Testes |
