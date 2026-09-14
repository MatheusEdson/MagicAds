# -*- coding: utf-8 -*-
"""O banco: schema, carteira e leitura.

Duas implementacoes atras de uma costura so:
  - Supabase (PostgREST, HTTP puro, nao precisa instalar nada)
  - Postgres direto (DATABASE_URL, usa psycopg2, importado aqui dentro)

A carteira mora AQUI e nao num arquivo versionado, por dois motivos: arquivo
de carteira e dado de cliente dentro do git, e ainda apodrece (cliente que sai
continua aparecendo, cliente novo demora a entrar).
"""
import os
import sys
from pathlib import Path

from .comum import env, http


class Banco(object):
    def __init__(self, exigir=True):
        self.supa_url = env("MAGICADS_SUPABASE_URL", segredo=False).rstrip("/")
        self.supa_key = env("MAGICADS_SUPABASE_KEY")
        self.dsn = env("DATABASE_URL")
        if not self.supa_url and not self.dsn:
            if exigir:
                sys.exit("defina MAGICADS_SUPABASE_URL + MAGICADS_SUPABASE_KEY, "
                         "ou DATABASE_URL (veja o README)")
            self.modo = None
            return
        self.modo = "supabase" if self.supa_url else "postgres"

    # -- schema ---------------------------------------------------------
    def aplica_schema(self):
        """Cria as 4 tabelas. So funciona no modo postgres: o PostgREST nao
        executa DDL de proposito, e isso e uma protecao, nao uma limitacao.
        No Supabase, cole db/schema.sql no SQL Editor (uma vez, 10 segundos).
        """
        caminho = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
        if not caminho.exists():
            sys.exit("nao achei db/schema.sql")
        if self.modo != "postgres":
            print("No Supabase o schema se aplica pelo SQL Editor (PostgREST nao roda DDL).")
            print("Abra o painel -> SQL Editor -> cole o conteudo de db/schema.sql -> Run.")
            print("Arquivo: %s" % caminho)
            return False
        self._sql(caminho.read_text(encoding="utf-8"), escreve=True)
        return True

    def existe_schema(self):
        try:
            if self.modo == "supabase":
                self._rest("clientes?select=slug&limit=1")
            else:
                self._sql("select 1 from clientes limit 1")
            return True
        except Exception:
            return False

    # -- carteira -------------------------------------------------------
    def cliente_salva(self, slug, nome, nicho=None, cidade=None):
        linha = {"slug": slug, "nome": nome, "nicho": nicho, "cidade": cidade}
        if self.modo == "supabase":
            self._rest("clientes?on_conflict=slug", [linha], "POST",
                       "resolution=merge-duplicates,return=minimal")
        else:
            self._sql("insert into clientes (slug, nome, nicho, cidade) values (%s,%s,%s,%s) "
                      "on conflict (slug) do update set nome = excluded.nome, "
                      "nicho = excluded.nicho, cidade = excluded.cidade",
                      (slug, nome, nicho, cidade), escreve=True)

    def conta_salva(self, canal, account_id, cliente_slug, nome=None):
        linha = {"canal": canal, "account_id": account_id,
                 "cliente_slug": cliente_slug, "nome": nome}
        if self.modo == "supabase":
            self._rest("contas?on_conflict=canal,account_id", [linha], "POST",
                       "resolution=merge-duplicates,return=minimal")
        else:
            self._sql("insert into contas (canal, account_id, cliente_slug, nome) "
                      "values (%s,%s,%s,%s) on conflict (canal, account_id) do update set "
                      "cliente_slug = excluded.cliente_slug, nome = excluded.nome",
                      (canal, account_id, cliente_slug, nome), escreve=True)

    def conta_desativa(self, canal, account_id):
        if self.modo == "supabase":
            self._rest("contas?canal=eq.%s&account_id=eq.%s" % (canal, account_id),
                       {"ativo": False}, "PATCH", "return=minimal")
        else:
            self._sql("update contas set ativo = false where canal=%s and account_id=%s",
                      (canal, account_id), escreve=True)

    def clientes(self):
        if self.modo == "supabase":
            linhas = self._rest("clientes?select=slug,nome,nicho,cidade,ativo&order=slug")
            return [(l["slug"], l["nome"], l.get("nicho"), l.get("cidade"), l["ativo"])
                    for l in linhas]
        return self._sql("select slug, nome, nicho, cidade, ativo from clientes order by slug")

    def carteira(self):
        """(slug, nome, canal, account_id) das contas ATIVAS."""
        if self.modo == "supabase":
            linhas = self._rest("contas?select=canal,account_id,cliente_slug,nome"
                                "&ativo=is.true&order=cliente_slug")
            return [(l["cliente_slug"], l.get("nome") or l["cliente_slug"],
                     l["canal"], l["account_id"]) for l in linhas]
        return self._sql("select cliente_slug, coalesce(nome, cliente_slug), canal, account_id "
                         "from contas where ativo order by cliente_slug")

    # -- metricas -------------------------------------------------------
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
        marca = "(" + ",".join(["%s"] * len(colunas)) + ")"
        sql = ("insert into metricas (%s) values %s "
               "on conflict (canal, account_id, data, campanha, criativo_id) do update set "
               "investimento = excluded.investimento, impressoes = excluded.impressoes, "
               "cliques = excluded.cliques, conversas = excluded.conversas, "
               "conversoes = excluded.conversoes, atualizado_em = now()"
               % (",".join(colunas), ",".join([marca] * len(valores))))
        self._sql(sql, [v for linha in valores for v in linha], escreve=True)
        return len(linhas)

    def linhas_no_periodo(self, desde, ate, slug=None):
        """Linhas cruas da janela. O relatorio agrega em Python: agregacao em
        SQL aqui viraria uma view, e view vira divida cedo demais."""
        if self.modo == "supabase":
            q = ("metricas?select=cliente_slug,canal,account_id,data,campanha,"
                 "investimento,impressoes,cliques,conversas,conversoes"
                 "&data=gte.%s&data=lte.%s&order=data&limit=50000" % (desde, ate))
            if slug:
                q += "&cliente_slug=eq.%s" % slug
            return [(l["cliente_slug"], l["canal"], l["account_id"], str(l["data"]),
                     l["campanha"], float(l["investimento"] or 0), int(l["impressoes"] or 0),
                     int(l["cliques"] or 0), int(l["conversas"] or 0), int(l["conversoes"] or 0))
                    for l in self._rest(q)]
        sql = ("select cliente_slug, canal, account_id, data::text, campanha, investimento, "
               "impressoes, cliques, conversas, conversoes from metricas "
               "where data between %s and %s")
        args = [desde, ate]
        if slug:
            sql += " and cliente_slug = %s"
            args.append(slug)
        return [(a, b, c, d, e, float(f), int(g), int(h), int(i), int(j))
                for a, b, c, d, e, f, g, h, i, j in self._sql(sql + " order by data", args)]

    def ultimo_dia_por_conta(self):
        if self.modo == "supabase":
            visto = {}
            for l in self._rest("metricas?select=canal,account_id,data"
                                "&order=data.desc&limit=50000"):
                chave = (l["canal"], l["account_id"])
                if chave not in visto or str(l["data"]) > visto[chave]:
                    visto[chave] = str(l["data"])
            return visto
        return {(c, a): str(d) for c, a, d in self._sql(
            "select canal, account_id, max(data) from metricas group by canal, account_id")}

    # -- motores --------------------------------------------------------
    def _rest(self, caminho, data=None, method="GET", prefer=None):
        h = {"apikey": self.supa_key, "Authorization": "Bearer %s" % self.supa_key}
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
        con = psycopg2.connect(self.dsn)
        try:
            with con:
                with con.cursor() as cur:
                    cur.execute(sql, args)
                    if escreve:
                        return []
                    return cur.fetchall()
        finally:
            con.close()


def onde_escrevo():
    """Texto curto pro usuario saber em que banco ele esta mexendo."""
    if os.environ.get("MAGICADS_SUPABASE_URL"):
        return "supabase %s" % os.environ["MAGICADS_SUPABASE_URL"]
    if os.environ.get("DATABASE_URL"):
        bruto = os.environ["DATABASE_URL"]
        return "postgres %s" % (bruto.split("@")[-1] if "@" in bruto else "local")
    return "nenhum banco configurado"
