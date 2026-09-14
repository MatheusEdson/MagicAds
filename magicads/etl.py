# -*- coding: utf-8 -*-
"""ETL: Meta Ads e Google Ads -> seu Postgres. Idempotente.

POR QUE EXISTE
Metrica lida no chat e metrica que voce nao compara com ontem. Decisao precisa
de serie, e serie precisa de banco. Este ETL enche a tabela `metricas` do
db/schema.sql e pode rodar quantas vezes quiser no mesmo dia: a chave primaria
(canal, conta, data, campanha, criativo) E a chave de idempotencia, entao nao
existe controle de "ja rodei hoje" pra dar errado.

SEGURANCA (o que o codigo garante sozinho)
1. Segredo so vem de variavel de ambiente. Nada de arquivo de credencial no
   repo, nada de valor embutido.
2. Nenhum segredo e impresso. Todo print passa por `limpa()`, que troca
   qualquer valor secreto conhecido por <SEGREDO>. Erro de API ecoa parametro,
   e e assim que token vaza em log.
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
  export DATABASE_URL=postgresql://user:senha@host:5432/base
  python -m magicads etl                      # usa psycopg2 se estiver instalado
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

META_VER = os.environ.get("MAGICADS_API_VERSION", "v25.0")
GADS_VER = os.environ.get("MAGICADS_GADS_VERSION", "v25")

# Meta: primeiro toma esses tres action_types como "conversa".
MSG_INICIADA = "onsite_conversion.total_messaging_connection"
MSG_RESPONDIDA = "onsite_conversion.messaging_first_reply"
MSG_DEPTH_3 = "onsite_conversion.messaging_user_depth_3_message_send"

CONVERSAO = (
    "lead",
    "onsite_conversion.lead_grouped",
    "purchase",
    "offsite_conversion.fb_pixel_lead",
    "offsite_conversion.fb_pixel_purchase",
)

DIAS_ATE_ESQUECER = 35

FALHAS = []
MUDAS = []


# ---------------------------------------------------------------------------
# segredo: entra por env, nunca sai por print
# ---------------------------------------------------------------------------
SEGREDOS = []


def env(nome, obrigatorio=False, segredo=True):
    v = os.environ.get(nome, "")
    if obrigatorio and not v:
        sys.exit("falta a variavel de ambiente %s (veja o docstring de etl.py)" % nome)
    if v and segredo and len(v) > 8:
        SEGREDOS.append(v)
    return v


def limpa(s):
    """Ultima linha de defesa. Nenhum segredo sai daqui, nem dentro de erro."""
    s = str(s)
    for v in SEGREDOS:
        if v and v in s:
            s = s.replace(v, "<SEGREDO>")
    return s


def diz(*partes):
    print(limpa(" ".join(str(p) for p in partes)))


# ---------------------------------------------------------------------------
# http com retry: API de anuncio cai sozinha o tempo todo
# ---------------------------------------------------------------------------
def http(url, data=None, headers=None, method=None, tentativas=3):
    for n in range(tentativas):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode() if data is not None else None,
                headers=headers or {},
                method=method,
            )
            with urllib.request.urlopen(req, timeout=90) as r:
                corpo = r.read()
                return json.loads(corpo) if corpo else {}
        except urllib.error.HTTPError as e:
            corpo = e.read().decode()[:300]
            if e.code in (429, 500, 503) and n < tentativas - 1:
                time.sleep(3 * (n + 1))
                continue
            raise RuntimeError(limpa("HTTP %s: %s" % (e.code, corpo)))
        except Exception as e:
            if n < tentativas - 1:
                time.sleep(3 * (n + 1))
                continue
            raise RuntimeError(limpa(str(e)[:200]))


# ---------------------------------------------------------------------------
# armazenamento: PostgREST (Supabase) ou Postgres direto
# ---------------------------------------------------------------------------
class Banco(object):
    """Duas implementacoes, uma costura so.

    O caminho Supabase nao precisa de nada instalado (PostgREST e HTTP).
    O caminho Postgres direto usa psycopg2, importado aqui dentro justamente
    pra quem usa Supabase nao precisar instalar.
    """

    def __init__(self):
        self.supa_url = env("MAGICADS_SUPABASE_URL", segredo=False).rstrip("/")
        self.supa_key = env("MAGICADS_SUPABASE_KEY")
        self.dsn = env("DATABASE_URL")
        if not self.supa_url and not self.dsn:
            sys.exit("defina MAGICADS_SUPABASE_URL + MAGICADS_SUPABASE_KEY, ou DATABASE_URL")
        self.modo = "supabase" if self.supa_url else "postgres"

    # -- leitura --------------------------------------------------------
    def carteira(self):
        """(slug, nome, canal, account_id). Fonte de verdade = banco."""
        if self.modo == "supabase":
            linhas = self._rest("contas?select=canal,account_id,cliente_slug,nome,ativo"
                                "&ativo=is.true&order=cliente_slug")
            return [(l["cliente_slug"], l.get("nome") or l["cliente_slug"],
                     l["canal"], l["account_id"]) for l in linhas]
        return self._sql(
            "select cliente_slug, coalesce(nome, cliente_slug), canal, account_id "
            "from contas where ativo order by cliente_slug")

    def ultimo_dia_por_conta(self):
        """Pra separar conta que EMUDECEU de conta que nunca teve dado."""
        if self.modo == "supabase":
            linhas = self._rest("metricas?select=canal,account_id,data&order=data.desc&limit=20000")
            visto = {}
            for l in linhas:
                chave = (l["canal"], l["account_id"])
                if chave not in visto or l["data"] > visto[chave]:
                    visto[chave] = l["data"]
            return visto
        return {(c, a): str(d) for c, a, d in self._sql(
            "select canal, account_id, max(data) from metricas group by canal, account_id")}

    # -- escrita --------------------------------------------------------
    def grava_metricas(self, linhas):
        if not linhas:
            return 0
        if self.modo == "supabase":
            self._rest("metricas?on_conflict=canal,account_id,data,campanha,criativo_id",
                       linhas, "POST", "resolution=merge-duplicates,return=minimal")
            return len(linhas)
        colunas = ("canal", "account_id", "data", "campanha", "criativo_id", "cliente_slug",
                   "investimento", "impressoes", "cliques", "conversas", "conversoes")
        valores = [tuple(l[c] for c in colunas) for l in linhas]
        marcas = "(" + ",".join(["%s"] * len(colunas)) + ")"
        sql = ("insert into metricas (%s) values %s "
               "on conflict (canal, account_id, data, campanha, criativo_id) do update set "
               "investimento = excluded.investimento, impressoes = excluded.impressoes, "
               "cliques = excluded.cliques, conversas = excluded.conversas, "
               "conversoes = excluded.conversoes, atualizado_em = now()"
               % (",".join(colunas), ",".join([marcas] * len(valores))))
        chatos = [v for linha in valores for v in linha]
        self._sql(sql, chatos, escreve=True)
        return len(linhas)

    # -- motores --------------------------------------------------------
    def _rest(self, caminho, data=None, method="GET", prefer=None):
        h = {"apikey": self.supa_key, "Authorization": "Bearer %s" % self.supa_key,
             "Content-Type": "application/json"}
        if prefer:
            h["Prefer"] = prefer
        return http("%s/rest/v1/%s" % (self.supa_url, caminho), data=data,
                    headers=h, method=method)

    def _sql(self, sql, args=None, escreve=False):
        try:
            import psycopg2
        except ImportError:
            sys.exit("DATABASE_URL exige psycopg2: pip install psycopg2-binary\n"
                     "(ou use MAGICADS_SUPABASE_URL, que nao precisa de nada instalado)")
        with psycopg2.connect(self.dsn) as con:
            with con.cursor() as cur:
                cur.execute(sql, args)
                if escreve:
                    return []
                return cur.fetchall()


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
    """
    conversas = conversoes = 0
    for a in actions or []:
        t = a.get("action_type", "")
        try:
            v = int(float(a.get("value", 0)))
        except (TypeError, ValueError):
            continue
        if t == MSG_INICIADA:
            conversas += v
        elif t in CONVERSAO:
            conversoes += v
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
            SEGREDOS.append(tok)
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
                diz("  meta %-22s token principal recusou: %s" % (nome, str(e)[:70]))
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
                diz("  meta %-22s FALHOU nos dois tokens: %s" % (nome, str(e)[:70]))
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
    SEGREDOS.append(at)
    return at


def coleta_google(banco, carteira, desde, ate, seco):
    dev = env("MAGICADS_GADS_DEVELOPER_TOKEN")
    mcc = env("MAGICADS_GADS_LOGIN_CUSTOMER_ID", segredo=False)
    if not dev:
        diz("  google: sem MAGICADS_GADS_DEVELOPER_TOKEN, pulando o canal")
        return 0
    at = token_google()
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
            diz("  ads  %-22s FALHOU: %s" % (nome, str(e)[:90]))
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
