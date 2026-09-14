# -*- coding: utf-8 -*-
"""ETL: Meta Ads e Google Ads -> seu Postgres. Idempotente.

POR QUE EXISTE
Metrica lida no chat e metrica que voce nao compara com ontem. Decisao precisa
de serie, e serie precisa de banco. Este ETL enche a tabela `metricas` do
db/schema.sql e pode rodar quantas vezes quiser no mesmo dia: a chave primaria
(canal, conta, data, campanha, criativo) E a chave de idempotencia, entao nao
existe controle de "ja rodei hoje" pra dar errado.

SEGURANCA (o que o codigo garante sozinho)
1. Segredo so vem de variavel de ambiente ou do cofre. Nada de credencial no
   repo, nada de valor embutido.
2. Nenhum segredo e impresso: tudo passa pelo `limpa()` de comum.py, que e o
   UNICO filtro do projeto. Dois filtros parecem redundancia e sao a chance de
   um deles ficar pra tras quando a regra mudar.
3. A carteira mora no BANCO, nao num arquivo versionado. Arquivo de carteira
   vira dado de cliente dentro do git, e alem disso apodrece: cliente que
   churna continua aparecendo e cliente novo demora a entrar.
4. Falha nao vira zero. Se a chamada de uma conta falhar, a conta entra em
   FALHAS e NADA e escrito pra ela. Escrever zero por causa de erro de rede e
   pior que nao escrever: vira "a campanha parou" no relatorio.

USO
  export MAGICADS_META_TOKEN=EAA...
  export MAGICADS_SUPABASE_URL=https://xxxx.supabase.co
  export MAGICADS_SUPABASE_KEY=...            # service key, so no servidor
  python -m magicads etl --dias 7
  python -m magicads etl --so-meta
  python -m magicads etl --seco               # nao escreve, so mostra

  # Postgres seu, sem Supabase:
  export DATABASE_URL=postgresql://usuario:xxxxxxxx@host:5432/base
  python -m magicads etl                      # usa psycopg2 se estiver instalado
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta

from .banco import Banco
from .comum import META_VER, diz, env, guarda_segredo, http, limpa

GADS_VER = os.environ.get("MAGICADS_GADS_VERSION", "v25")

# Meta: primeiro toma esses tres action_types como "conversa".
MSG_INICIADA = "onsite_conversion.total_messaging_connection"
MSG_RESPONDIDA = "onsite_conversion.messaging_first_reply"
MSG_DEPTH_3 = "onsite_conversion.messaging_user_depth_3_message_send"

# A Meta reporta o MESMO resultado em mais de um `action_type`: `lead` e o total
# de Leads, e ele JA INCLUI o lead do pixel e o do formulario. Somar os tres
# conta a mesma pessoa duas ou tres vezes -- e resultado inflado divide o custo,
# entao um lead de R$ 100 aparece como dois de R$ 50 e voce escala o que nao
# estava funcionando.
#
# Visto ao vivo em 21/08/2026: a mesma linha trazia `lead=1` e
# `offsite_conversion.fb_pixel_lead=1`, que sao o mesmo lead.
#
# Regra: dentro de cada familia, o AGREGADO manda; os especificos so entram
# quando o agregado nao veio. Entre familias, soma normal -- lead e compra sao
# coisas diferentes.
FAMILIAS = (
    ("lead", ("onsite_conversion.lead_grouped", "offsite_conversion.fb_pixel_lead")),
    ("purchase", ("offsite_conversion.fb_pixel_purchase",)),
)

# Achatado, so pra quem quiser saber "isto conta como resultado?".
CONVERSAO = tuple(
    [agregado for agregado, _ in FAMILIAS]
    + [e for _, especificos in FAMILIAS for e in especificos]
)

DIAS_ATE_ESQUECER = 35

FALHAS = []
MUDAS = []


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------
def conta_resultados(actions):
    """(conversas, conversoes).

    conversas = INICIADAS. E o denominador de tudo, e teto de intencao: nenhuma
    delas e conversa qualificada, muito menos venda.

    `depth_5` fica de fora de proposito: ele conta MENSAGEM ENVIADA, nao pessoa,
    e por isso consegue ser maior que o numero de conversas iniciadas. Serve de
    sinal de que ha conversa longa, nunca de contagem de gente.

    conversoes respeita as FAMILIAS: dentro de cada uma, o agregado manda e os
    especificos so entram se ele nao veio. Somar os dois contaria a mesma pessoa
    duas vezes, e inflar resultado e pior que nao ter resultado -- ele divide o
    custo pela metade e faz voce escalar o que nao estava funcionando.
    """
    valores, conversas = {}, 0
    for a in actions or []:
        t = a.get("action_type", "")
        try:
            v = int(float(a.get("value", 0)))
        except (TypeError, ValueError):
            continue
        if t == MSG_INICIADA:
            conversas += v
        else:
            valores[t] = valores.get(t, 0) + v

    conversoes = 0
    for agregado, especificos in FAMILIAS:
        if agregado in valores:
            conversoes += valores[agregado]
        else:
            conversoes += sum(valores.get(e, 0) for e in especificos)
    return conversas, conversoes


def token_do_cliente(slug):
    """Fallback por conta: o token de System User DO CLIENTE, se estiver no cofre.

    Nao e fallback de rede, e fallback de IDENTIDADE. Existe pro dia em que voce
    perde acesso a UMA conta (o cliente desfez a parceria, ou o seu token caiu)
    e o resto da frota continua funcionando. Sem isto, perder uma conta e um
    cliente sem numero no relatorio ate alguem reparar.
    """
    try:
        from .cli import token as token_do_cofre
        _, tok = token_do_cofre(slug)
        if tok:
            guarda_segredo(tok)
        return tok
    except SystemExit:
        return None
    except Exception:
        return None


def coleta_meta(banco, carteira, desde, ate, seco):
    principal = env("MAGICADS_META_TOKEN")
    total = 0
    for slug, nome, canal, act in carteira:
        if canal != "meta":
            continue
        conta = act if act.startswith("act_") else "act_%s" % act
        janela = json.dumps({"since": desde.isoformat(), "until": ate.isoformat()})

        def monta(tok):
            return ("https://graph.facebook.com/%s/%s/insights"
                    "?level=campaign&fields=campaign_name,spend,impressions,clicks,actions"
                    "&time_increment=1&time_range=%s&limit=500&access_token=%s"
                    % (META_VER, conta, urllib.parse.quote(janela), tok))

        resp = None
        if principal:
            try:
                resp = http(monta(principal))
            except RuntimeError as e:
                diz("  meta %-22s token principal recusou: %s" % (nome, limpa(str(e))[:70]))
        if resp is None:
            alt = token_do_cliente(slug)
            if not alt:
                diz("  meta %-22s FALHOU: sem token que abra esta conta" % nome)
                FALHAS.append("meta %s" % nome)
                continue
            try:
                resp = http(monta(alt))
                diz("  meta %-22s LIDA COM O TOKEN DO CLIENTE" % nome)
            except RuntimeError as e:
                diz("  meta %-22s FALHOU nos dois tokens: %s" % (nome, limpa(str(e))[:70]))
                FALHAS.append("meta %s" % nome)
                continue

        linhas = []
        for r in resp.get("data", []):
            conversas, conversoes = conta_resultados(r.get("actions"))
            linhas.append({
                "cliente_slug": slug, "canal": "meta", "account_id": conta,
                "data": r.get("date_start"),
                "campanha": r.get("campaign_name") or "(sem nome)", "criativo_id": "",
                "investimento": float(r.get("spend", 0)),
                "impressoes": int(r.get("impressions", 0)),
                "cliques": int(r.get("clicks", 0)),
                "conversas": conversas, "conversoes": conversoes,
            })
        gasto = sum(l["investimento"] for l in linhas)
        if linhas and not seco:
            banco.grava_metricas(linhas)
        diz("  meta %-22s %4d linhas  R$ %10.2f%s"
            % (nome, len(linhas), gasto, "  [seco]" if seco else ""))
        if not linhas:
            MUDAS.append(("meta", nome, conta))
        total += len(linhas)
    return total


# ---------------------------------------------------------------------------
# Google Ads
# ---------------------------------------------------------------------------
def token_google():
    corpo = urllib.parse.urlencode({
        "client_id": env("MAGICADS_GOOGLE_CLIENT_ID", segredo=False),
        "client_secret": env("MAGICADS_GOOGLE_CLIENT_SECRET"),
        "refresh_token": env("MAGICADS_GADS_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=corpo,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=60) as r:
        at = json.loads(r.read())["access_token"]
    guarda_segredo(at)
    return at


def coleta_google(banco, carteira, desde, ate, seco):
    dev = env("MAGICADS_GADS_DEVELOPER_TOKEN")
    mcc = env("MAGICADS_GADS_LOGIN_CUSTOMER_ID", segredo=False)
    if not dev:
        diz("  google: sem MAGICADS_GADS_DEVELOPER_TOKEN, pulando o canal")
        return 0
    # O refresh do Google roda ANTES do laco, entao um token revogado derrubava
    # a rodada inteira com traceback -- depois do Meta ja ter coletado e
    # gravado. O dado nao se perdia, mas o resumo e o codigo de saida sim, e
    # quem le cron por e-mail so via o stack trace. Falha de canal se comporta
    # como falha de conta: entra em FALHAS e a rodada segue.
    try:
        at = token_google()
    except Exception as e:
        diz("  google: nao consegui renovar o token: %s" % limpa(str(e))[:120])
        diz("         (refresh_token revogado ou client_id/secret trocado)")
        FALHAS.append("google (token)")
        return 0
    total = 0

    # O Google exige intervalo FECHADO em segments.date. Um ">=" sozinho devolve
    # EXPECTED_FILTERS_ON_DATE_RANGE, que se disfarca de "invalid argument" e
    # faz voce procurar erro de sintaxe onde nao tem.
    consulta = (
        "SELECT segments.date, campaign.name, metrics.cost_micros, "
        "metrics.impressions, metrics.clicks, metrics.conversions "
        "FROM campaign "
        "WHERE segments.date BETWEEN '%s' AND '%s'" % (desde.isoformat(), ate.isoformat())
    )

    for slug, nome, canal, cid in carteira:
        if canal != "google":
            continue
        cid_limpo = cid.replace("-", "")
        cabecalhos = {"Authorization": "Bearer %s" % at, "developer-token": dev,
                      "Content-Type": "application/json"}
        if mcc:
            cabecalhos["login-customer-id"] = mcc.replace("-", "")
        try:
            resp = http("https://googleads.googleapis.com/%s/customers/%s/googleAds:search"
                        % (GADS_VER, cid_limpo),
                        data={"query": consulta}, method="POST", headers=cabecalhos)
        except RuntimeError as e:
            diz("  ads  %-22s FALHOU: %s" % (nome, limpa(str(e))[:90]))
            FALHAS.append("google %s" % nome)
            continue

        linhas = []
        for r in resp.get("results", []):
            m = r.get("metrics", {})
            linhas.append({
                "cliente_slug": slug, "canal": "google", "account_id": cid,
                "data": r["segments"]["date"],
                "campanha": r.get("campaign", {}).get("name") or "(sem nome)",
                "criativo_id": "",
                "investimento": int(m.get("costMicros", 0)) / 1000000.0,
                "impressoes": int(m.get("impressions", 0)),
                "cliques": int(m.get("clicks", 0)),
                "conversas": 0,
                "conversoes": int(float(m.get("conversions", 0))),
            })
        gasto = sum(l["investimento"] for l in linhas)
        if linhas and not seco:
            banco.grava_metricas(linhas)
        diz("  ads  %-22s %4d linhas  R$ %10.2f%s"
            % (nome, len(linhas), gasto, "  [seco]" if seco else ""))
        if not linhas:
            MUDAS.append(("google", nome, cid))
        total += len(linhas)
    return total


# ---------------------------------------------------------------------------
# resumo
# ---------------------------------------------------------------------------
def resumo(banco, total):
    """Conta muda nao e conta quebrada. A distincao e a parte importante.

    Quem nunca teve uma linha na vida nao vira alerta: alertar nela duas vezes
    por dia treina voce a ignorar o alerta, e ai o alerta de verdade passa
    junto. So vira alerta quem TINHA dado recente e parou.
    """
    diz("")
    diz("=" * 64)
    diz("gravadas %d linhas" % total)

    if FALHAS:
        diz("")
        diz("FALHAS (%d) -- nada foi escrito pra essas contas:" % len(FALHAS))
        for f in FALHAS:
            diz("   %s" % f)

    if MUDAS:
        try:
            ultimo = banco.ultimo_dia_por_conta()
        except Exception:
            ultimo = {}
        limite = (date.today() - timedelta(days=DIAS_ATE_ESQUECER)).isoformat()
        emudeceram, nunca_tiveram = [], []
        for canal, nome, conta in MUDAS:
            visto = ultimo.get((canal, conta))
            (emudeceram if visto and visto >= limite else nunca_tiveram).append(
                (canal, nome, visto))
        if emudeceram:
            diz("")
            diz("EMUDECERAM (%d) -- tinham dado recente e pararam. OLHE ISTO:" % len(emudeceram))
            for canal, nome, visto in emudeceram:
                diz("   %-8s %-22s ultimo dia: %s" % (canal, nome, visto))
        if nunca_tiveram:
            diz("")
            diz("sem dado, e nunca tiveram (%d): %s"
                % (len(nunca_tiveram), ", ".join(n for _, n, _ in nunca_tiveram)))
    diz("=" * 64)
    return 1 if FALHAS else 0


def main(argv):
    dias = 30
    for i, a in enumerate(argv):
        if a == "--dias" and i + 1 < len(argv):
            dias = int(argv[i + 1])
    seco = "--seco" in argv
    so_meta = "--so-meta" in argv
    so_google = "--so-google" in argv

    ate = date.today()
    desde = ate - timedelta(days=dias)

    banco = Banco()
    carteira = banco.carteira()
    if not carteira:
        sys.exit("carteira vazia. Cadastre em `clientes` e `contas` (ver db/schema.sql).")

    diz("janela %s a %s  ·  %d conta(s)  ·  banco: %s%s"
        % (desde, ate, len(carteira), banco.modo, "  [MODO SECO]" if seco else ""))
    diz("-" * 64)

    total = 0
    if not so_google:
        total += coleta_meta(banco, carteira, desde, ate, seco)
    if not so_meta:
        total += coleta_google(banco, carteira, desde, ate, seco)

    return resumo(banco, total)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
