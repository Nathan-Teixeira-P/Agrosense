#!/usr/bin/env python3
import json, math, statistics, sys
from openai_client import openai

INTERVALO_S = 2
TRAVADO = 12
NOMES = ["Carinho na Roça"]
CANAIS = {
    "temp": dict(rot="Temperatura", un="°C", limite=32, sentido=1, salto=5, faixa=(-10, 60), travado=0),
    "umi":  dict(rot="Umidade do ar", un="%", limite=85, sentido=1, salto=20, faixa=(0, 100), travado=0),
    "pres": dict(rot="Pressao", un="hPa", limite=None, sentido=1, salto=10, faixa=(300, 1100), ref=100, travado=0),
}

def canal(v, c):
    n = len(v)
    mx, my = (n - 1) / 2, sum(v) / n
    a = slope(v)
    b = my - a * mx
    lim, s = c["limite"], c["sentido"]
    if lim is None:
        prev = "sem limite definido"
    elif v[-1] * s >= lim * s:
        prev = f"ja alem do limite ({lim} {c['un']})"
    elif a * s > 0:
        prev = f"cruza {lim} {c['un']} em ~{(lim - (a * (n - 1) + b)) / a * INTERVALO_S / 60:.1f} min"
    else:
        prev = "nao deve cruzar o limite"
    saltos = sum(abs(v[i] - v[i - 1]) > c["salto"] for i in range(1, n))
    run = mx_run = 1
    for i in range(1, n):
        run = run + 1 if v[i] == v[i - 1] else 1
        mx_run = max(mx_run, run)
    susp = []
    if saltos: susp.append(f"{saltos} saltos > {c['salto']} {c['un']}")
    lim_travado = c.get("travado", TRAVADO)
    if lim_travado and mx_run >= lim_travado: susp.append(f"{mx_run} leituras identicas seguidas")
    if not all(c["faixa"][0] <= x <= c["faixa"][1] for x in v): susp.append("fora da faixa fisica")
    return {"valores": v, "media": my, "min": min(v), "max": max(v), "tendencia": a * 60 / INTERVALO_S,
            "reta": [b, a], "previsao": prev, "suspeito": susp}

def corr(x, y):
    try: return statistics.correlation(x, y)
    except statistics.StatisticsError: return None

def setor(nome, rows):
    ch = {k: canal([r[i] for r in rows], c) for i, (k, c) in enumerate(CANAIS.items())}
    temp, umi = ch["temp"], ch["umi"]
    t_alta = temp["media"] >= CANAIS["temp"]["limite"]
    u_alta = umi["media"] >= CANAIS["umi"]["limite"]
    risco = (40 if t_alta else 0) \
          + (40 if u_alta else 0) \
          + 10 * sum(bool(c["suspeito"]) for c in ch.values())
    regras = []
    if t_alta: regras.append("Sombrear / resfriar")
    if u_alta: regras.append("Reduzir umidade do ar (risco de fungos)")
    for k, c in ch.items():
        if c["suspeito"]: regras.append(f"Verificar sensor de {CANAIS[k]['rot']}")
    cor = {p: corr(ch[a]["valores"], ch[b]["valores"]) for p, (a, b) in
           {"temperatura x umidade do ar": ("temp", "umi"), "temperatura x pressao": ("temp", "pres"), "umidade do ar x pressao": ("umi", "pres")}.items()}
    return {"nome": nome, "canais": ch, "risco": min(risco, 100), "regras": regras,
            "correlacoes": {k: round(v, 2) for k, v in cor.items() if v is not None}}

def resumo_texto(setores):
    linhas = []
    for s in setores:
        linhas.append(f"{s['nome']} (risco {s['risco']}/100):")
        for k, c in s["canais"].items():
            u = CANAIS[k]
            sens = "SUSPEITO (" + ", ".join(c["suspeito"]) + ")" if c["suspeito"] else "ok"
            linhas.append(f"  - {u['rot']}: media {c['media']:.1f} {u['un']} (min {c['min']:.1f}, max {c['max']:.1f}), "
                          f"tendencia {c['tendencia']:+.2f} {u['un']}/min, {c['previsao']}; sensor {sens}")
        linhas.append("  - correlacoes: " + (", ".join(f"{k} {v:+.2f}" for k, v in s["correlacoes"].items()) or "n/d"))
        linhas.append("  - acoes por regra: " + ("; ".join(s["regras"]) or "nenhuma"))
    return "\n".join(linhas)

SISTEMA = ("Voce e um agronomo assistente de uma estufa. Os dados vem de um unico sensor barato, o BME280: "
           "temperatura, umidade do ar e pressao. Nao ha sensor de CO2 nem de umidade do solo: nao opine sobre irrigacao ou CO2. "
           "Limites: temperatura > 32 C estresse termico; "
           "umidade do ar > 85% risco de fungos; pressao sem limite (so contexto: queda rapida indica mau tempo). "
           "Considere a previsao e a saude dos sensores: leitura de sensor SUSPEITO nao e confiavel. Portugues, direto.")

def laudo(resumo):
    txt, erro = openai([
        {"role": "system", "content": SISTEMA + ' Responda SOMENTE JSON: {"resumo_geral": str, "setores": '
         '[{"nome": str, "urgencia": "baixa|media|alta", "diagnostico": str, "acoes": [str]}], '
         '"insights": [str]}. "insights" = relacoes entre temperatura, umidade do ar e pressao ou riscos que as regras nao pegam.'},
        {"role": "user", "content": "ANALISE:\n" + resumo}], json_mode=True)
    if erro: return None, erro
    try: return json.loads(txt), None
    except ValueError: return None, "IA devolveu JSON invalido"

def chat(pergunta, resumo, historico=""):
    return openai([{"role": "system", "content": SISTEMA + " Responda a pergunta usando so estes dados.\nTESTE ATUAL:\n" + resumo
                    + ("\n\nHISTORICO DOS ULTIMOS TESTES:\n" + historico if historico else "")},
                   {"role": "user", "content": pergunta}])

def processar(rows):
    n = len(rows) // len(NOMES)
    if n < 3: raise ValueError(f"Poucas leituras ({len(rows)}); preciso de ao menos {3 * len(NOMES)}.")
    setores = [setor(nome, rows[i * n:(i + 1) * n]) for i, nome in enumerate(NOMES)]
    resumo = resumo_texto(setores)
    ia, erro = laudo(resumo)
    return {"setores": setores, "canais": CANAIS, "resumo": resumo,
            "laudo": ia, "erro_laudo": erro, "intervalo_s": INTERVALO_S}

def slope(ys):
    n = len(ys)
    if n < 2: return 0.0
    mx, my = (n - 1) / 2, sum(ys) / n
    return sum((i - mx) * (y - my) for i, y in enumerate(ys)) / sum((i - mx) ** 2 for i in range(n))


def atuais(hist):
    return [e for e in hist if all(k in e["resultado"]["setores"][0]["canais"] for k in CANAIS)]


def historico_local(hist):
    hist = atuais(hist)
    n = len(hist)
    if n == 0: return {"n": 0, "canais": {}, "risco": {"serie": []}, "insights": []}
    ss = [e["resultado"]["setores"] for e in hist]
    canais, insights = {}, []
    for k, c in CANAIS.items():
        medias = [sum(x["canais"][k]["media"] for x in s) / len(s) for s in ss]
        alem = 0 if c["limite"] is None else sum(c["sentido"] * (m - c["limite"]) >= 0 for m in medias)
        susp = sum(any(x["canais"][k]["suspeito"] for x in s) for s in ss)
        t = slope(medias)
        canais[k] = {"medias": medias, "tendencia": t, "suspeito_em": susp}
        if n > 1 and abs(t) * (n - 1) > 0.05 * (c["limite"] or c["ref"]):
            insights.append(f"{c['rot']}: media {'subindo' if t > 0 else 'caindo'} {abs(t):.1f} {c['un']} por teste "
                            f"(de {medias[0]:.1f} para {medias[-1]:.1f}).")
        if alem: insights.append(f"{c['rot']}: media alem do limite em {alem} de {n} testes.")
        if susp: insights.append(f"Sensor de {c['rot']} suspeito em {susp} de {n} testes"
                                 + (" (problema recorrente: vale checar o hardware)." if susp >= 3 else "."))
    risco = [max(x["risco"] for x in s) for s in ss]
    if n > 1 and slope(risco) > 3: insights.append(f"Risco geral em alta ({risco[0]} -> {risco[-1]}).")
    return {"n": n, "canais": canais, "risco": {"serie": risco}, "insights": insights}

def resumo_historico(hist):
    h = historico_local(hist)
    linhas = []
    for i, e in enumerate(atuais(hist), 1):
        s = e["resultado"]["setores"][0]
        med = ", ".join(f"{CANAIS[k]['rot']} {c['media']:.1f} {CANAIS[k]['un']}" for k, c in s["canais"].items())
        susp = [CANAIS[k]["rot"] for k, c in s["canais"].items() if c["suspeito"]]
        linhas.append(f"#{i} {e['ts']} ({e['fonte']}): risco {s['risco']}/100; {med}; sensores suspeitos: {', '.join(susp) or 'nenhum'}")
    return "\n".join(linhas) + "\nPadroes calculados: " + (" ".join(h["insights"]) or "nenhum")

def laudo_historico(hist):
    txt, erro = openai([
        {"role": "system", "content": SISTEMA + " Voce analisa o HISTORICO de testes (do mais antigo ao mais novo). "
         "Testes com fonte 'demo' sao simulados: se o historico for de demonstracao, diga isso. "
         'Responda SOMENTE JSON: {"resumo": str, "padroes": [str], "recomendacoes": [str]}. '
         "Foque em evolucao no tempo, recorrencia de falhas de sensor e o que muda a decisao de manejo."},
        {"role": "user", "content": resumo_historico(hist)}], json_mode=True)
    if erro: return None, erro
    try: return json.loads(txt), None
    except ValueError: return None, "IA devolveu JSON invalido"

def parse(texto):
    rows = []
    for l in texto.splitlines():
        p = l.strip().split(",")
        try:
            r = tuple(float(x) for x in p)
            if len(r) == len(CANAIS) and all(map(math.isfinite, r)): rows.append(r)
        except ValueError:
            pass
    return rows

if __name__ == "__main__":
    r = processar(parse(sys.stdin.read()))
    print(r["resumo"], "\n\n", json.dumps(r["laudo"] or r["erro_laudo"], ensure_ascii=False, indent=2))
