import json, os, pty, shutil, socket, subprocess, sys, threading, time, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
import analisar_ia as ia

DIR = os.path.dirname(os.path.abspath(__file__))

def rows(temp, umi, pres, n=24):
    return [(temp(i), umi(i), pres(i)) for i in range(n)]

def test_parse_ignora_ruido_serial():
    assert ia.parse("temp,umi,pres\n25.5,60,1013\nlixo\n1,2\n26,61,1012.5\n") == [(25.5, 60, 1013), (26, 61, 1012.5)]

def test_setor_saudavel_tem_risco_zero():
    s = ia.setor("A", rows(lambda i: 25 + i % 2, lambda i: 60 + i % 2, lambda i: 1013 + i % 2))
    assert s["risco"] == 0 and s["regras"] == []

def test_setor_critico_aciona_regras():
    s = ia.setor("A", rows(lambda i: 35 + i % 2, lambda i: 90 + i % 2, lambda i: 1013 + i % 2))
    assert s["risco"] == 80
    assert {"Sombrear / resfriar", "Reduzir umidade do ar (risco de fungos)"} <= set(s["regras"])

def test_previsao_de_cruzamento_do_limite():
    c = ia.canal([float(30 + 0.5 * i) for i in range(24)], ia.CANAIS["temp"])
    assert c["tendencia"] == pytest.approx(15) and "ja alem" in c["previsao"]
    c = ia.canal([float(20 + 0.1 * i) for i in range(24)], ia.CANAIS["temp"])
    assert "cruza 32 °C em" in c["previsao"]
    assert ia.canal([1013.0 + i for i in range(24)], ia.CANAIS["pres"])["previsao"] == "sem limite definido"

def test_sensor_travado_e_salto_sao_suspeitos():
    salto = ia.canal([25.0] * 12 + [45.0] + [25.0] * 11, ia.CANAIS["temp"])
    assert any("saltos" in s for s in salto["suspeito"])
    fora = ia.canal([25.0] * 23 + [90.0], ia.CANAIS["temp"])
    assert any("fora da faixa" in s for s in fora["suspeito"])

def test_sensor_travado_so_vale_quando_habilitado_e_bme280_estavel_nao_alerta():
    c = {**ia.CANAIS["umi"], "travado": 12}
    assert any("identicas" in s for s in ia.canal([60.0] * 24, c)["suspeito"])
    assert ia.canal([60.0] * 6 + [60.0 + 0.1 * i for i in range(18)], c)["suspeito"] == []
    for k, v in {"temp": 25.0, "umi": 60.0, "pres": 1013.0}.items():
        assert ia.canal([v] * 24, ia.CANAIS[k])["suspeito"] == []

def test_limite_exato_conta_como_alerta():
    s = ia.setor("A", rows(lambda i: 31.5 + i % 2, lambda i: 60 + i % 2, lambda i: 1013 + i % 2))
    assert s["risco"] == 40 and "Sombrear / resfriar" in s["regras"]

def test_parse_rejeita_nan_e_inf():
    assert ia.parse("nan,60,1013\n25,inf,1013\n25,60,1013\n") == [(25, 60, 1013)]

def test_historico_ignora_testes_do_formato_antigo():
    antigo = {"id": 0, "fonte": "demo", "ts": "x", "resultado": {"setores": [{"canais": {"co2": {}, "solo": {}, "temp": {}}, "risco": 10}]}}
    novos = [entrada(i, 50 + 20 * i) for i in range(1, 4)]
    assert ia.atuais([antigo] + novos) == novos
    h = ia.historico_local([antigo] + novos)
    assert h["n"] == 3 and len(h["risco"]["serie"]) == 3
    assert "#1" in ia.resumo_historico([antigo] + novos) and "#4" not in ia.resumo_historico([antigo] + novos)

def test_queda_de_pressao_no_historico_e_notada():
    def e(i, p):
        s = ia.setor("A", rows(lambda j: 25 + j % 2, lambda j: 60 + j % 2, lambda j: p + j % 2))
        return {"id": i, "fonte": "demo", "ts": "x", "resultado": {"setores": [s]}}
    assert any("Pressao" in i for i in ia.historico_local([e(i, 1013 - 4 * i) for i in range(4)])["insights"])

def test_correlacao_de_serie_constante_e_omitida():
    s = ia.setor("A", rows(lambda i: 25, lambda i: 50, lambda i: 1013))
    assert s["correlacoes"] == {}

def test_processar_rejeita_poucas_leituras():
    with pytest.raises(ValueError):
        ia.processar([(25, 60, 1013)] * 2)

def entrada(id, umi, ts="01/01 00:00:00"):
    s = ia.setor("A", rows(lambda i: 25 + i % 2, lambda i: umi + i % 3, lambda i: 1013 - i % 2))
    return {"id": id, "fonte": "demo", "ts": ts, "resultado": {"setores": [s]}}

def test_historico_detecta_alta_de_umidade():
    h = ia.historico_local([entrada(i, 40 + 15 * i) for i in range(4)])
    assert h["n"] == 4 and h["canais"]["umi"]["tendencia"] > 0
    assert h["canais"]["umi"]["suspeito_em"] == 0
    assert any("Umidade do ar" in i for i in h["insights"])
    assert "#4" in ia.resumo_historico([entrada(i, 60) for i in range(4)])

def test_historico_vazio():
    assert ia.historico_local([])["n"] == 0

class OpenAIFalsa:
    def __init__(self):
        self.status, self.conteudo, self.pedidos = 200, "", []
        outer = self
        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                outer.pedidos.append(json.loads(self.rfile.read(int(self.headers["content-length"]))))
                corpo = json.dumps({"choices": [{"message": {"content": outer.conteudo}}]} if outer.status == 200 else "negado")
                self.send_response(outer.status); self.end_headers(); self.wfile.write(corpo.encode())
            def log_message(self, *a): pass
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/v1/chat/completions"

@pytest.fixture
def openai():
    f = OpenAIFalsa()
    yield f
    f.httpd.shutdown(); f.httpd.server_close()

@pytest.fixture
def historico(tmp_path):
    arq = tmp_path / "historico.json"
    arq.write_text(json.dumps([entrada(1, 50), entrada(2, 90)]))
    return arq

@pytest.fixture
def server(historico, openai):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); porta = s.getsockname()[1]
    url = f"http://127.0.0.1:{porta}"
    env = {**os.environ, "DADOS": str(historico.parent), "PORT": str(porta), "OPENAI_URL": openai.url, "OPENAI_API_KEY": "teste"}
    p = subprocess.Popen([sys.executable, "server.py"], cwd=DIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/", timeout=1)
            break
        except OSError:
            if p.poll() is not None: pytest.fail(p.stderr.read().decode())
            time.sleep(.1)
    yield url
    p.kill(); p.stderr.close()

def get(url):
    try:
        with urllib.request.urlopen(url) as r: return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def post(url, obj):
    req = urllib.request.Request(url, json.dumps(obj).encode(), {"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def itens(server): return json.loads(get(server + "/api/historico")[1])["itens"]

def test_pagina_inicial(server):
    st, body = get(server + "/")
    assert st == 200 and b"<html" in body.lower()

def test_lista_historico(server):
    assert [i["id"] for i in itens(server)] == [1, 2]
    assert itens(server)[1]["risco"] > itens(server)[0]["risco"]

def test_detalhe_historico_e_404(server):
    st, body = get(server + "/api/historico/2")
    assert st == 200 and json.loads(body)["setores"][0]["nome"] == "A"
    assert get(server + "/api/historico/999")[0] == 404
    assert get(server + "/nada")[0] == 404

def test_post_invalido_devolve_400(server):
    req = urllib.request.Request(server + "/api/chat", b"{nao e json", {"content-type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as e: urllib.request.urlopen(req)
    assert e.value.code == 400
    assert post(server + "/api/chat", {})[0] == 400

def test_run_so_aceita_post(server):
    assert get(server + "/api/run?fonte=demo")[0] == 404

def test_run_demo_usa_laudo_da_ia_e_grava_historico(server, openai):
    openai.conteudo = '{"resumo_geral": "tudo ok"}'
    st, r = post(server + "/api/run?fonte=demo", {})
    assert st == 200 and r["setores"][0]["canais"]["umi"]["valores"]
    assert r["laudo"] == {"resumo_geral": "tudo ok"} and r["erro_laudo"] is None
    assert openai.pedidos[0]["response_format"] == {"type": "json_object"}
    assert [i["id"] for i in itens(server)][:2] == [1, 2] and len(itens(server)) == 3

def test_run_com_json_invalido_ou_erro_http_da_ia(server, openai):
    openai.conteudo = "nao json"
    assert post(server + "/api/run?fonte=demo", {})[1]["erro_laudo"] == "IA devolveu JSON invalido"
    openai.status = 401
    assert post(server + "/api/run?fonte=demo", {})[1]["erro_laudo"].startswith("Erro 401")

def test_historico_mantem_so_os_ultimos_10(server):
    for _ in range(12): post(server + "/api/run?fonte=demo", {})
    assert len(itens(server)) == 10

def test_historico_corrompido_vira_vazio(server, historico):
    historico.write_text("{quebrado")
    assert itens(server) == []

def test_run_serial_le_leituras_da_porta(server):
    mestre, escravo = pty.openpty()
    os.write(mestre, b"temp,umi,pres\nlixo\n" + b"".join(f"{20 + i},60,1013\n".encode() for i in range(30)))
    st, r = post(server + "/api/run?fonte=serial&porta=" + os.ttyname(escravo), {})
    os.close(mestre); os.close(escravo)
    assert st == 200 and r["setores"][0]["canais"]["temp"]["valores"][0] == 20

def test_run_serial_descarta_primeira_linha_cortada(server):
    mestre, escravo = pty.openpty()
    os.write(mestre, b"9.9,60,1013\n" + b"".join(f"{20 + i},60,1013\n".encode() for i in range(30)))
    st, r = post(server + "/api/run?fonte=serial&porta=" + os.ttyname(escravo), {})
    os.close(mestre); os.close(escravo)
    assert st == 200 and 9.9 not in r["setores"][0]["canais"]["temp"]["valores"]

def test_run_serial_mostra_erro_do_arduino(server):
    mestre, escravo = pty.openpty()
    os.write(mestre, b"lixo\nERRO: BME280 nao encontrado\n")
    st, r = post(server + "/api/run?fonte=serial&porta=" + os.ttyname(escravo), {})
    os.close(mestre); os.close(escravo)
    assert st == 500 and "BME280 nao encontrado" in r["erro"]

def test_historico_antigo_e_descartado_ao_salvar(server, historico):
    antigo = {"id": 0, "fonte": "demo", "ts": "x", "resultado": {"setores": [{"canais": {"co2": {}}, "risco": 1}]}}
    historico.write_text(json.dumps([antigo]))
    assert itens(server) == []
    post(server + "/api/run?fonte=demo", {})
    assert [i["id"] for i in itens(server)] != [0] and len(json.loads(historico.read_text())) == 1

def test_run_serial_inexistente_devolve_500(server):
    st, r = post(server + "/api/run?fonte=serial&porta=/dev/inexistente", {})
    assert st == 500 and r["erro"]

def test_chat_envia_pergunta_e_historico_para_a_ia(server, openai):
    openai.conteudo = "regue"
    assert post(server + "/api/chat", {"pergunta": "e agora?", "resumo": "R"}) == (200, {"resposta": "regue", "erro": None})
    sistema, usuario = openai.pedidos[0]["messages"]
    assert "#2" in sistema["content"] and usuario["content"] == "e agora?"

def test_chat_propaga_erro_da_ia(server, openai):
    openai.status = 401
    st, r = post(server + "/api/chat", {"pergunta": "oi"})
    assert st == 500 and r["erro"].startswith("Erro 401")

def test_analise_historico(server, openai):
    openai.conteudo = '{"resumo": "ok"}'
    assert post(server + "/api/historico/analise", {}) == (200, {"analise": {"resumo": "ok"}, "erro": None})

def test_analise_exige_dois_testes(server, historico):
    historico.write_text(json.dumps([entrada(1, 50)]))
    assert post(server + "/api/historico/analise", {})[0] == 400
