# Agrosense

Monitoramento de temperatura, umidade do ar e pressão de uma estufa, com um sensor BME280 num Arduino Uno, com painel web, regras de risco e laudo gerado pela OpenAI.

## Como funciona

```
Arduino Uno (BME280) --serial--> server.py
                                    +--> analisar_ia.py --> regras, tendência, previsão
                                    |                   \--> openai_client.py --> laudo
                                    +--> dados/historico.json (últimos 10 testes)
                                    +--> index.html (interface)
```

Cada teste coleta 24 leituras (uma a cada 2 s) da porta serial, ou gera leituras simuladas no modo demonstração. O Python calcula tendência, previsão de cruzamento do limite, sensores suspeitos, correlações e risco de 0 a 100. A OpenAI devolve o laudo e responde perguntas no chat.

## Requisitos

- Python 3.10+
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
| BME280 (I2C) VIN / GND / SDA / SCL | 5V / GND / A4 / A5 |

Calibre `TEMP_OFFSET` no início do firmware. O BME280 mede temperatura, umidade do ar e pressão (endereço `0x76` ou `0x77`; precisa da biblioteca *Adafruit BME280*). Se o módulo for na verdade um BMP280, não há umidade: o firmware repete `ERRO: leitura invalida...` a cada 2 s e o servidor mostra essa mensagem. Cada linha serial é `temp,umidade_ar,pressao`; valores `nan`/`inf` e a primeira linha lida (pode vir cortada) são descartados.

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
| Temperatura | > 32 °C |
| Umidade do ar | > 85 % |
| Pressão | sem alerta, só informativa (o histórico avisa queda ou alta de mais de 5 hPa) |
| Sensor travado | 12 leituras idênticas seguidas (24 s) |

Os limites usam `>=`. Testes gravados antes do BME280 (com CO₂ e solo) não aparecem no histórico e são apagados do arquivo no próximo teste salvo.

## Testes

```
pytest
```

Os testes sobem o servidor de verdade e usam um servidor HTTP local no lugar da OpenAI. Nenhuma chamada sai para a internet.

## Arquivos

| Arquivo | Função |
|---|---|
| `server.py` | Servidor HTTP, coleta serial, demo e histórico |
| `analisar_ia.py` | Análise estatística, regras e prompts |
| `openai_client.py` | Cliente da OpenAI e leitura do `.env` |
| `index.html` | Interface |
| `test_projeto.py` | Testes |
