# -*- coding: utf-8 -*-
"""MagicAds: opera Meta Ads com o SEU app e o SEU token de System User.

POR QUE ISSO EXISTE
O MCP oficial de ads fala com a identidade de quem conectou. Quando a conta nao
esta atribuida ao portfolio dessa identidade, a API le pela metade e as vezes
devolve lista VAZIA no lugar de erro. Lista vazia com HTTP 200 nao e "nao tem",
e "nao vejo". Este CLI fala com o token do System User que voce escolher, e por
isso enxerga o que a outra identidade nao enxerga.

REGRAS QUE O CODIGO APLICA SOZINHO
1. O token NUNCA e impresso. Se aparecer em qualquer saida, vira <SEGREDO> --
   inclusive dentro de mensagem de erro (a Meta ecoa parametro, e e assim que
   token vaza em log). O filtro e UM so, em comum.py.
2. `post` e `subir` rodam em modo VALIDACAO/ENSAIO por padrao. Pra valer de
   verdade exige `--executar` explicito.
3. `pausar` executa direto, sem cerimonia. Freio que exige confirmacao e freio
   que nao se usa na hora do aperto.
4. Cofre em ~/.magicads/tokens, um arquivo por cliente, chmod 600.

O CICLO COMPLETO
  init                       prepara cofre e banco, e diz o que falta
  cliente / conta            a carteira (mora no banco, nao em arquivo)
  diag <cliente>             os 6 portoes, antes de perder a tarde
  subir <receita.json>       campanha + conjunto + criativo + anuncio
  etl --dias 7               enche a serie
  relatorio                  le a serie em formato de decisao
  pausar / ativar            o freio e o acelerador

USO
  python -m magicads init
  python -m magicads clientes
  python -m magicads cliente acme "Acme Pneus" --nicho auto --cidade Uberlandia
  python -m magicads conta acme meta act_000000000000000 "Acme - Meta"
  python -m magicads diag acme
  python -m magicads get  acme me/adaccounts fields=name,account_status
  python -m magicads post acme act_123/campaigns name=[C01] objective=OUTCOME_LEADS
  python -m magicads imagem acme act_123 criativo.jpg
  python -m magicads subir receitas/local-whatsapp.json
  python -m magicads subir receitas/local-whatsapp.json --executar
  python -m magicads etl --dias 7
  python -m magicads relatorio
  python -m magicads relatorio acme --dias 14
  python -m magicads relatorio --mudas
  python -m magicads pausar acme 120xxxxxxxx
  python -m magicads ativar acme 120xxxxxxxx --executar
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .comum import GRAPH as API
from .comum import guarda_segredo, limpa

COFRE = Path(os.environ.get("MAGICADS_COFRE", os.path.expanduser("~/.magicads/tokens")))
Q1 = chr(39)


# ---------------------------------------------------------------------------
# cofre
# ---------------------------------------------------------------------------
def cofre_arquivos():
    if not COFRE.exists():
        sys.exit(
            "cofre nao existe: %s\n"
            "crie com:\n"
            "  mkdir -p ~/.magicads/tokens\n"
            "  printf 'CLIENTE_META_TOKEN=EAA...\\n' > ~/.magicads/tokens/cliente.env\n"
            "  chmod 600 ~/.magicads/tokens/cliente.env\n"
            "(ver exemplos/acme.example.env)" % COFRE
        )
    return sorted(COFRE.glob("*.env"))


def token(cliente):
    """Resolve cliente -> (nome, token). Aceita apelido por prefixo.

    O token sai daqui JA registrado no filtro de segredo: quem chama nao
    precisa lembrar de proteger, e por isso nao tem como esquecer.
    """
    arqs = cofre_arquivos()
    alvo = [p for p in arqs if p.stem == cliente]
    if not alvo:
        alvo = [p for p in arqs if p.stem.startswith(cliente)]
    if not alvo:
        sys.exit("cliente %r nao esta no cofre. Rode: python -m magicads clientes" % cliente)
    if len(alvo) > 1:
        sys.exit("%r casa com %s. Seja especifico." % (cliente, [p.stem for p in alvo]))
    p = alvo[0]
    if os.name != "nt" and oct(p.stat().st_mode)[-3:] not in ("600", "400"):
        print("AVISO: %s nao esta 600. Corrija com chmod 600." % p.name, file=sys.stderr)
    for linha in p.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            k, v = linha.split("=", 1)
            if k.strip().upper().endswith("_META_TOKEN"):
                return p.stem, guarda_segredo(v.strip().strip('"').strip(Q1))
    sys.exit("%s nao tem chave terminando em _META_TOKEN" % p.name)


TOK_ATUAL = [""]


def usa(tok):
    """Escolhe com qual token as proximas chamadas falam."""
    TOK_ATUAL[0] = guarda_segredo(tok) or ""


# ---------------------------------------------------------------------------
# http
# ---------------------------------------------------------------------------
def chamada(metodo, caminho, campos):
    campos = dict(campos)
    campos["access_token"] = TOK_ATUAL[0]
    dados = urllib.parse.urlencode(campos).encode("utf-8")
    if metodo == "GET":
        req = urllib.request.Request("%s/%s?%s" % (API, caminho, dados.decode("utf-8")))
    else:
        req = urllib.request.Request("%s/%s" % (API, caminho), data=dados, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        try:
            er = json.loads(e.read().decode("utf-8")).get("error", {})
        except Exception:
            er = {"message": "HTTP %s" % e.code}
        return None, er
    except Exception as e:
        return None, {"message": str(e)[:200]}


def erro_legivel(er):
    """`error_user_title` costuma ser o unico campo que diz a causa de verdade."""
    partes = ["code=%s" % er.get("code"), "subcode=%s" % er.get("error_subcode")]
    if er.get("error_user_title"):
        partes.append("titulo=%s" % er["error_user_title"])
    if er.get("error_user_msg"):
        partes.append("msg_usuario=%s" % er["error_user_msg"])
    if er.get("message"):
        partes.append("message=%s" % er["message"])
    return limpa(" | ".join(str(x) for x in partes))


# ---------------------------------------------------------------------------
# comandos
# ---------------------------------------------------------------------------
def cmd_clientes():
    arqs = cofre_arquivos()
    print("cofre: %s" % COFRE)
    print("-" * 84)
    for p in arqs:
        nome = p.stem
        _, tok = token(nome)
        usa(tok)
        d, e = chamada("GET", "me", {"fields": "id,name"})
        if e:
            print("  XX %-22s TOKEN MORTO  %s" % (nome, erro_legivel(e)[:70]))
            continue
        ca, _ = chamada("GET", "me/adaccounts", {"fields": "name", "limit": "25"})
        it = ((ca or {}).get("data") or [])
        print("  OK %-22s %s %s  |  %d conta(s): %s" % (
            nome, d.get("name"), d.get("id"), len(it),
            ", ".join((x.get("name") or "")[:20] for x in it) or "nenhuma"))
    print("-" * 84)
    print("proximo passo: python -m magicads diag <cliente>")


def cmd_diag(cliente):
    """Os 6 portoes. Cinco deles nao aparecem antes de voce tentar subir."""
    nome, tok = token(cliente)
    usa(tok)
    print("=" * 92)
    print("DIAGNOSTICO  ·  %s  ·  identidade = token do cofre  ·  so leitura" % nome)
    print("=" * 92)

    # portao 1: o token abre?
    d, e = chamada("GET", "me", {"fields": "id,name"})
    if e:
        print("\nO TOKEN NAO ABRE: %s" % erro_legivel(e))
        print("\n190 sozinho = senha trocada do lado do cliente.")
        print("190 com subcode 465 = o app saiu do portfolio;")
        print("  precisa readicionar E gerar token novo. Readicionar sem gerar nao resolve.")
        return
    print("\nfalando como: %s (%s)" % (d.get("name"), d.get("id")))

    # portoes 2, 3, 4: conta, escrita, pagamento
    ca, e = chamada("GET", "me/adaccounts",
                    {"fields": "name,account_status,user_tasks,funding_source_details,business",
                     "limit": "25"})
    contas = ((ca or {}).get("data") or [])
    print("\n" + "-" * 92)
    print("CONTAS DE ANUNCIO (%d)" % len(contas))
    print("-" * 92)
    negocios, pode_escrever, tem_pagamento = set(), False, False
    for c in contas:
        tarefas = c.get("user_tasks") or []
        fs = c.get("funding_source_details") or {}
        b = c.get("business") or {}
        if b.get("id"):
            negocios.add((b.get("id"), b.get("name")))
        escreve = any(t in tarefas for t in ("MANAGE", "ADVERTISE"))
        pode_escrever = pode_escrever or escreve
        tem_pagamento = tem_pagamento or bool(fs.get("display_string"))
        print("  %-26s %s" % ((c.get("name") or "")[:26], c.get("id")))
        print("     status=%s  tasks=%s" % (c.get("account_status"), ",".join(tarefas) or "VAZIO"))
        print("     portfolio=%s" % (b.get("name") or "NENHUM"))
        print("     pagamento=%s" % (fs.get("display_string") or "SEM FORMA DE PAGAMENTO"))
        if not escreve:
            print("     ATENCAO: sem MANAGE/ADVERTISE. Le a conta e NAO cria nada nela.")

    # portao 5: pagina.
    # A verdade sobre pagina mora no lado do NEGOCIO. `promote_pages` filtra em
    # silencio o que o token nao consegue ler e devolve vazio mesmo quando a
    # pagina existe.
    print("\n" + "-" * 92)
    print("PAGINAS (lidas pelo portfolio, nao por promote_pages)")
    print("-" * 92)
    paginas = []
    for bid, bnome in sorted(negocios):
        for borda in ("owned_pages", "client_pages"):
            r, er = chamada("GET", "%s/%s" % (bid, borda), {"fields": "id,name", "limit": "50"})
            if er:
                print("  [%s %s] %s: ERRO %s" % (bnome, bid, borda, erro_legivel(er)[:60]))
                continue
            it = (r or {}).get("data") or []
            print("  [%s] %s: %d" % (bnome, borda, len(it)))
            for x in it:
                paginas.append(x)
                print("      %-32s %s" % ((x.get("name") or "")[:32], x.get("id")))

    ap, er = chamada("GET", "me/assigned_pages", {"fields": "id,name,tasks", "limit": "50"})
    com_messaging = False
    if er:
        print("  me/assigned_pages: ERRO %s" % erro_legivel(er)[:60])
    else:
        it = (ap or {}).get("data") or []
        print("\n  na mao deste token (me/assigned_pages): %d" % len(it))
        for x in it:
            tarefas = x.get("tasks") or []
            com_messaging = com_messaging or ("MESSAGING" in tarefas)
            print("      %-32s %-18s tasks=%s" % ((x.get("name") or "")[:32], x.get("id"),
                                                  ",".join(tarefas)))

    print("\n" + "-" * 92)
    print("VEREDITO")
    print("-" * 92)
    print("  %-30s %s" % ("token abre", "OK"))
    print("  %-30s %s" % ("conta de anuncio", "OK" if contas else "FALTA"))
    print("  %-30s %s" % ("escrita na conta",
                          "OK" if pode_escrever else "FALTA (papel Anunciante ou superior)"))
    print("  %-30s %s" % ("forma de pagamento",
                          "OK" if tem_pagamento else "FALTA (conta nova nasce sem, e status=1 nao avisa)"))
    print("  %-30s %s" % ("pagina", "OK" if paginas else "FALTA"))

    # portao 6, o mais traicoeiro: a pagina pode ter a task MESSAGING e NAO ter
    # uma conta de WhatsApp conectada. Nenhuma LEITURA mostra isso; quem responde
    # e o POST de conjunto com destino WHATSAPP, que devolve subcode 2446886.
    # Rodamos em validate_only, que a Meta confere e nao cria.
    # Exige uma campanha existente pra pendurar o teste -- e e de proposito:
    # validate_only NAO protege em /campaigns, so em adset e anuncio.
    zap = None
    if contas and paginas:
        conta1 = contas[0].get("id")
        cp, _ = chamada("GET", "%s/campaigns" % conta1, {"fields": "id", "limit": "1"})
        camps = ((cp or {}).get("data") or [])
        if camps:
            sonda = {
                "name": "[SONDA] gate de WhatsApp", "campaign_id": camps[0]["id"],
                "optimization_goal": "CONVERSATIONS", "billing_event": "IMPRESSIONS",
                "bid_strategy": "LOWEST_COST_WITHOUT_CAP", "destination_type": "WHATSAPP",
                "daily_budget": "2000", "status": "PAUSED",
                "promoted_object": json.dumps({"page_id": paginas[0].get("id")}),
                "targeting": json.dumps({"geo_locations": {"countries": ["BR"]},
                                         "age_min": 18,
                                         "targeting_automation": {"advantage_audience": 1}}),
                "execution_options": json.dumps(["validate_only"]),
            }
            _, er = chamada("POST", "%s/adsets" % conta1, sonda)
            if not er:
                zap = True
            elif er.get("error_subcode") == 2446886:
                zap = False
            else:
                print("  %-30s sonda inconclusiva: %s" % ("WhatsApp na pagina",
                                                          erro_legivel(er)[:60]))

    if zap is True:
        print("  %-30s OK (conjunto CTWA validou)" % "WhatsApp na pagina")
    elif zap is False:
        print("  %-30s FALTA  -> subcode 2446886" % "WhatsApp na pagina")
        print("     A pagina NAO tem conta de WhatsApp conectada. A task MESSAGING nao supre")
        print("     isso. Conserto do CLIENTE, no Business Suite: Configuracoes da Pagina ->")
        print("     WhatsApp -> conectar o numero e confirmar com o codigo que chega nele.")
    elif com_messaging:
        print("  %-30s NAO TESTADO (sem campanha na conta)" % "WhatsApp na pagina")
        print("     A pagina tem MESSAGING, mas isso NAO prova WhatsApp conectado. Crie uma")
        print("     campanha primeiro e rode o diag de novo, que ai a sonda roda.")

    if contas and pode_escrever and tem_pagamento and paginas and zap is True:
        print("\n  PODE SUBIR. Monte com `post`, que valida antes de criar.")
    else:
        print("\n  NAO SUBA AINDA: resolva o que esta FALTA acima.")
        print("  Metade dos itens acima e acao do CLIENTE, nao sua. Mande a lista pra ele.")


def cmd_chamada(metodo, argv):
    if len(argv) < 2:
        sys.exit("uso: python -m magicads %s <cliente> <caminho> [chave=valor ...]"
                 % metodo.lower())
    cliente, caminho = argv[0], argv[1]
    executar = "--executar" in argv
    campos = {}
    for a in argv[2:]:
        if a == "--executar":
            continue
        if "=" not in a:
            sys.exit("parametro sem `=`: %r" % a)
        k, v = a.split("=", 1)
        campos[k] = v
    nome, tok = token(cliente)
    usa(tok)

    if metodo == "POST" and not executar:
        campos["execution_options"] = json.dumps(["validate_only"])
        print("MODO VALIDACAO: a Meta vai conferir e NAO criar. Use --executar pra valer.")
        if caminho.endswith("/campaigns"):
            print("AVISO: validate_only NAO protege em /campaigns. A Meta cria de verdade.")
            print("       Se e campanha, confira o payload agora: com --executar ou sem ele,")
            print("       este endpoint cria. Suba sempre com status=PAUSED.")
    elif metodo == "POST":
        print("MODO REAL: isso CRIA de verdade em %s." % nome)

    d, e = chamada(metodo, caminho, campos)
    if e:
        print("\nERRO: %s" % erro_legivel(e))
        sys.exit(1)
    print(limpa(json.dumps(d, ensure_ascii=False, indent=2)))


def cmd_status(argv, novo):
    """pausar/ativar qualquer entidade (campanha, conjunto, anuncio) pelo id.

    `pausar` executa direto: freio que exige confirmacao e freio que nao se usa
    na hora do aperto. `ativar` exige --executar, porque religar queima dinheiro.
    """
    if len(argv) < 2:
        sys.exit("uso: python -m magicads %s <cliente> <id>"
                 % ("pausar" if novo == "PAUSED" else "ativar"))
    cliente, alvo = argv[0], argv[1]
    nome, tok = token(cliente)
    usa(tok)

    if novo == "ACTIVE" and "--executar" not in argv:
        print("ativar %s religa o gasto. Repita com --executar." % alvo)
        return

    d, e = chamada("POST", alvo, {"status": novo})
    if e:
        print("ERRO: %s" % erro_legivel(e))
        sys.exit(1)
    print("%s -> %s em %s  %s" % (alvo, novo, nome, limpa(json.dumps(d, ensure_ascii=False))))

    # Confirma por GET direto: sob rate limit a Meta responde 200 com corpo
    # incompleto, e listagem mente mais ainda. Ler o proprio id e a unica prova.
    v, e2 = chamada("GET", alvo, {"fields": "id,name,status,effective_status"})
    if not e2:
        print("conferido: %s" % limpa(json.dumps(v, ensure_ascii=False)))


def cmd_init():
    """Prepara o terreno e, principalmente, DIZ O QUE FALTA.

    Setup que falha calado e a razao de metade das tardes perdidas: voce
    descobre que o banco nao tinha tabela quando o ETL ja rodou 20 contas.
    """
    from .banco import Banco, onde_escrevo

    print("=" * 72)
    print("INIT")
    print("=" * 72)

    print("\n1. cofre de tokens")
    if COFRE.exists():
        arqs = sorted(COFRE.glob("*.env"))
        print("   ok  %s  |  %d cliente(s): %s"
              % (COFRE, len(arqs), ", ".join(p.stem for p in arqs) or "nenhum ainda"))
        if not arqs:
            print("   crie um: printf 'ACME_META_TOKEN=EAA...' > %s/acme.env" % COFRE)
    else:
        COFRE.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(str(COFRE), 0o700)
        print("   criei %s (700). Ponha um arquivo .env por cliente, cada um 600." % COFRE)

    print("\n2. banco")
    banco = Banco(exigir=False)
    if not banco.modo:
        print("   FALTA. Defina MAGICADS_SUPABASE_URL + MAGICADS_SUPABASE_KEY,")
        print("   ou DATABASE_URL. Sem banco nao ha serie, e sem serie nao ha decisao.")
        return 1
    print("   %s" % onde_escrevo())

    if banco.existe_schema():
        print("   ok  as tabelas existem")
    else:
        print("   as 4 tabelas nao existem ainda. Aplicando db/schema.sql...")
        if banco.aplica_schema():
            print("   ok  schema aplicado")
        else:
            return 1

    print("\n3. carteira")
    try:
        contas = banco.carteira()
    except Exception as e:
        print("   nao consegui ler: %s" % limpa(e))
        return 1
    if contas:
        print("   ok  %d conta(s) ativa(s)" % len(contas))
        for slug, nome, canal, cid in contas[:10]:
            print("       %-8s %-22s %s" % (canal, nome[:22], slug))
    else:
        print("   vazia. Cadastre:")
        print("       python -m magicads cliente acme \"Acme Pneus\"")
        print("       python -m magicads conta acme meta act_000000000000000")

    print("\n" + "=" * 72)
    print("proximo passo: python -m magicads diag <cliente>")
    return 0


def cmd_cliente(argv):
    """Sem argumento, lista. Com argumento, cria ou atualiza."""
    from .banco import Banco
    banco = Banco()
    if not argv:
        linhas = banco.clientes()
        if not linhas:
            print("nenhum cliente. Cadastre: python -m magicads cliente acme \"Acme Pneus\"")
            return 0
        print("%-16s %-28s %-14s %-14s %s" % ("slug", "nome", "nicho", "cidade", "ativo"))
        print("-" * 80)
        for slug, nome, nicho, cidade, ativo in linhas:
            print("%-16s %-28s %-14s %-14s %s"
                  % (slug, (nome or "")[:28], nicho or "", cidade or "",
                     "sim" if ativo else "NAO"))
        return 0

    slug = argv[0]
    nome = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else slug
    nicho = cidade = None
    for i, a in enumerate(argv):
        if a == "--nicho" and i + 1 < len(argv):
            nicho = argv[i + 1]
        if a == "--cidade" and i + 1 < len(argv):
            cidade = argv[i + 1]
    banco.cliente_salva(slug, nome, nicho, cidade)
    print("cliente %s (%s) salvo." % (slug, nome))
    print("agora a conta: python -m magicads conta %s meta act_..." % slug)
    return 0


def cmd_conta(argv):
    """Liga uma conta de anuncio a um cliente. `--remover` desativa sem apagar.

    Desativar em vez de deletar e de proposito: a metrica historica dela
    continua valendo, e sumir com a conta apagaria a comparacao com o periodo
    anterior no relatorio.
    """
    from .banco import Banco
    banco = Banco()
    if not argv:
        for slug, nome, canal, cid in banco.carteira():
            print("%-8s %-20s %-24s %s" % (canal, slug, cid, nome))
        return 0
    if len(argv) < 3:
        sys.exit("uso: python -m magicads conta <cliente> <meta|google> <id> [nome] [--remover]")
    slug, canal, cid = argv[0], argv[1], argv[2]
    if canal not in ("meta", "google"):
        sys.exit("canal tem que ser `meta` ou `google` (veio %r)" % canal)
    if canal == "meta" and not cid.startswith("act_"):
        cid = "act_%s" % cid
    if "--remover" in argv:
        banco.conta_desativa(canal, cid)
        print("%s %s desativada. O historico dela continua no banco." % (canal, cid))
        return 0
    nome = argv[3] if len(argv) > 3 and not argv[3].startswith("--") else None
    banco.conta_salva(canal, cid, slug, nome)
    print("%s %s -> %s" % (canal, cid, slug))
    print("confira o acesso: python -m magicads diag %s" % slug)
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    c, resto = sys.argv[1], sys.argv[2:]
    if c in ("-h", "--help", "help"):
        print(__doc__)
        return
    if c == "init":
        sys.exit(cmd_init())
    elif c == "clientes":
        cmd_clientes()
    elif c == "cliente":
        sys.exit(cmd_cliente(resto))
    elif c == "conta":
        sys.exit(cmd_conta(resto))
    elif c == "diag":
        if not resto:
            sys.exit("uso: python -m magicads diag <cliente>")
        cmd_diag(resto[0])
    elif c == "get":
        cmd_chamada("GET", resto)
    elif c == "post":
        cmd_chamada("POST", resto)
    elif c == "pausar":
        cmd_status(resto, "PAUSED")
    elif c == "ativar":
        cmd_status(resto, "ACTIVE")
    elif c == "subir":
        from . import subir
        sys.exit(subir.main(resto))
    elif c == "imagem":
        from . import subir
        sys.exit(subir.sobe_imagem(resto))
    elif c == "etl":
        from . import etl
        sys.exit(etl.main(resto))
    elif c == "relatorio":
        from . import relatorio
        sys.exit(relatorio.main(resto))
    else:
        print(__doc__)
        sys.exit("comando desconhecido: %r" % c)


if __name__ == "__main__":
    main()
