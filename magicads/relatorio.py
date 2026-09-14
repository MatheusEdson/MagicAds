# -*- coding: utf-8 -*-
"""Leitura: o que o ETL gravou, em formato de decisão.

ETL sem leitura e banco que enche e ninguem olha. Este modulo responde as tres
perguntas que se faz de manha, e nenhuma delas e "qual foi o CTR":

  1. quanto cada cliente gastou e o que voltou            -> relatorio
  2. o que mudou de ontem pra media, por campanha          -> relatorio <cliente>
  3. que conta parou de reportar                           -> relatorio --mudas

USO
  python -m magicads relatorio                 ultimos 30 dias, todos
  python -m magicads relatorio --dias 7
  python -m magicads relatorio acme            por campanha do cliente
  python -m magicads relatorio --mudas
"""
import sys
from datetime import date, timedelta

from .banco import Banco, onde_escrevo
from .comum import diz

DIAS_ATE_ESQUECER = 35


def brl(v):
    return ("R$ %s" % ("%0.2f" % v)).replace(".", ",")


def agrega(linhas, chave):
    """chave(linha) -> (investimento, impressoes, cliques, conversas, conversoes)"""
    fora = {}
    for l in linhas:
        k = chave(l)
        a = fora.setdefault(k, [0.0, 0, 0, 0, 0])
        a[0] += l[5]
        a[1] += l[6]
        a[2] += l[7]
        a[3] += l[8]
        a[4] += l[9]
    return fora


def resultado(a):
    """Conversao quando existe; senao conversa. Conta que so tem clique mostra 0,
    e isso e informacao: ela nao esta medindo resultado nenhum."""
    return a[4] if a[4] else a[3]


def custo(a):
    r = resultado(a)
    return a[0] / r if r else None


def linha_custo(a):
    c = custo(a)
    return brl(c) if c is not None else "sem resultado"


def portfolio(banco, dias):
    ate = date.today()
    desde = ate - timedelta(days=dias)
    anterior_desde = desde - timedelta(days=dias)

    atual = banco.linhas_no_periodo(desde.isoformat(), ate.isoformat())
    antes = banco.linhas_no_periodo(anterior_desde.isoformat(),
                                    (desde - timedelta(days=1)).isoformat())
    if not atual:
        diz("nenhuma linha entre %s e %s. Rode o ETL: python -m magicads etl --dias %d"
            % (desde, ate, dias))
        return 0

    por_cliente = agrega(atual, lambda l: l[0])
    por_cliente_antes = agrega(antes, lambda l: l[0])

    diz("")
    diz("PORTFOLIO  ·  %s a %s  ·  %s" % (desde, ate, onde_escrevo()))
    diz("=" * 88)
    diz("%-20s %13s %9s %14s %10s" % ("cliente", "investido", "result.", "custo/result.", "vs ant."))
    diz("-" * 88)

    total = [0.0, 0, 0, 0, 0]
    for slug in sorted(por_cliente, key=lambda s: -por_cliente[s][0]):
        a = por_cliente[slug]
        b = por_cliente_antes.get(slug)
        if b and b[0]:
            delta = "%+d%%" % round((a[0] - b[0]) / b[0] * 100)
        else:
            delta = "novo"
        diz("%-20s %13s %9d %14s %10s"
            % (slug[:20], brl(a[0]), resultado(a), linha_custo(a), delta))
        for i in range(5):
            total[i] += a[i]

    diz("-" * 88)
    diz("%-20s %13s %9d %14s" % ("TOTAL", brl(total[0]), resultado(total), linha_custo(total)))

    # Conta sem resultado nenhum na janela nao e detalhe: ou nao esta medindo,
    # ou esta gastando a toa. Os dois pedem acao, e nenhum aparece na media.
    zeradas = [s for s, a in por_cliente.items() if a[0] > 0 and not resultado(a)]
    if zeradas:
        diz("")
        diz("gastaram e nao registraram resultado: %s" % ", ".join(sorted(zeradas)))
        diz("  ou o evento nao esta chegando, ou a verba esta indo pro lixo. Os dois pedem acao.")
    return 0


def por_campanha(banco, slug, dias):
    ate = date.today()
    desde = ate - timedelta(days=dias)
    linhas = banco.linhas_no_periodo(desde.isoformat(), ate.isoformat(), slug)
    if not linhas:
        diz("nenhuma linha de %s entre %s e %s" % (slug, desde, ate))
        return 1

    ontem = (ate - timedelta(days=1)).isoformat()
    por_camp = agrega(linhas, lambda l: (l[1], l[4]))
    de_ontem = agrega([l for l in linhas if l[3] == ontem], lambda l: (l[1], l[4]))
    dias_ativos = {}
    for l in linhas:
        dias_ativos.setdefault((l[1], l[4]), set()).add(l[3])

    diz("")
    diz("%s  ·  %s a %s" % (slug.upper(), desde, ate))
    diz("=" * 96)
    diz("%-8s %-34s %12s %8s %13s %11s" %
        ("canal", "campanha", "investido", "result.", "custo/result.", "ontem"))
    diz("-" * 96)
    for chave in sorted(por_camp, key=lambda k: -por_camp[k][0]):
        canal, campanha = chave
        a = por_camp[chave]
        o = de_ontem.get(chave)
        media = a[0] / max(1, len(dias_ativos[chave]))
        if o:
            marca = "%s%s" % (brl(o[0]), "  alto" if o[0] > media * 1.5 else "")
        else:
            marca = "nada"
        diz("%-8s %-34s %12s %8d %13s %11s"
            % (canal, (campanha or "")[:34], brl(a[0]), resultado(a), linha_custo(a), marca))
    diz("-" * 96)
    diz("\"ontem\" comparado com a media diaria da propria campanha na janela.")
    diz("Campanha que gastou ontem e nao aparece na lista de resultado e a primeira a olhar.")
    return 0


def mudas(banco):
    """Conta muda nao e conta quebrada, e essa distincao e o que salva o alerta.

    Quem nunca teve uma linha na vida nao vira alarme: alertar nela todo dia
    treina voce a ignorar o alerta, e ai o alerta de verdade passa junto.
    """
    ultimo = banco.ultimo_dia_por_conta()
    carteira = banco.carteira()
    limite = (date.today() - timedelta(days=2)).isoformat()
    esquecimento = (date.today() - timedelta(days=DIAS_ATE_ESQUECER)).isoformat()

    emudeceram, nunca, ok = [], [], 0
    for slug, nome, canal, conta in carteira:
        visto = ultimo.get((canal, conta))
        if visto and visto >= limite:
            ok += 1
        elif visto and visto >= esquecimento:
            emudeceram.append((canal, nome, visto))
        elif visto:
            nunca.append((canal, nome, "parou em %s" % visto))
        else:
            nunca.append((canal, nome, "nunca teve linha"))

    diz("")
    diz("SAUDE DA COLETA  ·  %d conta(s)" % len(carteira))
    diz("=" * 72)
    diz("reportando normalmente: %d" % ok)
    if emudeceram:
        diz("")
        diz("EMUDECERAM (%d) -- tinham dado recente e pararam. OLHE ISTO:" % len(emudeceram))
        for canal, nome, visto in emudeceram:
            diz("   %-8s %-28s ultimo dia: %s" % (canal, nome[:28], visto))
    if nunca:
        diz("")
        diz("sem dado recente, e ja estavam assim (%d):" % len(nunca))
        for canal, nome, obs in nunca:
            diz("   %-8s %-28s %s" % (canal, nome[:28], obs))
    diz("=" * 72)
    return 1 if emudeceram else 0


def main(argv):
    dias = 30
    for i, a in enumerate(argv):
        if a == "--dias" and i + 1 < len(argv):
            dias = int(argv[i + 1])
    banco = Banco()
    if "--mudas" in argv:
        return mudas(banco)
    alvo = [a for a in argv if not a.startswith("--") and not a.isdigit()]
    if alvo:
        return por_campanha(banco, alvo[0], dias)
    return portfolio(banco, dias)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
