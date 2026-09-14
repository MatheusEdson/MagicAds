# -*- coding: utf-8 -*-
"""Sobe campanha inteira a partir de uma receita JSON.

POR QUE EXISTE
Subir uma campanha na Graph API sao quatro chamadas encadeadas (campanha ->
conjunto -> criativo -> anuncio), cada uma com campos obrigatorios que a Meta
so reclama depois, com mensagem que nao diz o que faltou. Montar isso na mao,
toda vez, e onde o dia inteiro vai embora.

A receita e um JSON com o que muda. O resto (os campos que a Meta exige, a
ordem das chamadas, o status PAUSED, a conferencia por GET) e trabalho do
codigo.

SEGURANCA
1. Modo ENSAIO por padrao: monta, valida, imprime os quatro payloads e NAO
   chama a Meta. Criar de verdade exige --executar.
2. Tudo nasce PAUSED. Nao existe opcao de subir ligado, e isso e de proposito:
   revisar antes de gastar e a diferenca entre erro barato e erro caro.
3. Se falhar no meio, imprime o que JA foi criado e o comando pra remover.
   Orfao silencioso e como se descobre, tres semanas depois, que tem campanha
   sua rodando em conta de cliente.

USO
  python -m magicads subir receitas/local-whatsapp.json
  python -m magicads subir receitas/local-whatsapp.json --executar
"""
import copy
import json
import os
import re
import sys

from .comum import (GRAPH, diz, erro_da_meta, guarda_segredo, http, http_arquivo,
                    limpa)

# tipo de conta -> o que a Meta espera. Vem dos agentes Gandalf (aios/agents/).
PADROES = {
    "b2b": {
        "objetivo": "OUTCOME_LEADS", "otimizacao": "LEAD_GENERATION",
        "destino": "formulario", "cobranca": "IMPRESSIONS",
    },
    "local": {
        "objetivo": "OUTCOME_LEADS", "otimizacao": "LEAD_GENERATION",
        "destino": "formulario", "cobranca": "IMPRESSIONS",
    },
    "local-whatsapp": {
        "objetivo": "OUTCOME_ENGAGEMENT", "otimizacao": "CONVERSATIONS",
        "destino": "whatsapp", "cobranca": "IMPRESSIONS",
    },
    "loja": {
        "objetivo": "OUTCOME_SALES", "otimizacao": "OFFSITE_CONVERSIONS",
        "destino": "site", "cobranca": "IMPRESSIONS",
    },
    "balcao": {
        "objetivo": "OUTCOME_TRAFFIC", "otimizacao": "LINK_CLICKS",
        "destino": "site", "cobranca": "IMPRESSIONS",
    },
}

VERBA_MINIMA_CENTAVOS = 600   # a Meta recusa conjunto abaixo de ~R$6/dia no BR


class Recusa(Exception):
    """Erro de receita: o problema esta no arquivo, nao na Meta."""


# ---------------------------------------------------------------------------
# validacao: falhar aqui e de graca, falhar na Meta custa uma hora
# ---------------------------------------------------------------------------
def valida(r):
    tipo = r.get("tipo")
    if tipo not in PADROES:
        raise Recusa("tipo %r desconhecido. Use um de: %s"
                     % (tipo, ", ".join(sorted(PADROES))))
    p = PADROES[tipo]

    for campo in ("cliente", "conta", "campanha", "conjunto", "anuncios"):
        if not r.get(campo):
            raise Recusa("falta `%s` na receita" % campo)

    conta = r["conta"]
    if not conta.startswith("act_"):
        raise Recusa("`conta` tem que comecar com act_ (veio %r)" % conta)

    camp, conj = r["campanha"], r["conjunto"]
    objetivo = camp.get("objetivo") or p["objetivo"]
    otimizacao = conj.get("otimizacao") or p["otimizacao"]
    destino = conj.get("destino") or p["destino"]

    if not camp.get("nome"):
        raise Recusa("falta `campanha.nome`")

    verba = int(conj.get("verba_diaria") or 0)
    if verba < VERBA_MINIMA_CENTAVOS:
        raise Recusa("verba_diaria em CENTAVOS e minimo %d (R$%0.2f). Veio %d."
                     % (VERBA_MINIMA_CENTAVOS, VERBA_MINIMA_CENTAVOS / 100.0, verba))

    if not conj.get("geo"):
        raise Recusa("falta `conjunto.geo`. Campanha sem geografia compra o pais inteiro.")

    # promoted_object: o campo que a Meta exige e nao explica
    if destino == "formulario":
        if not r.get("pagina"):
            raise Recusa("destino formulario exige `pagina` (o promoted_object e a pagina)")
        if not any(a.get("formulario_id") for a in r["anuncios"]):
            raise Recusa("destino formulario exige `formulario_id` em cada anuncio "
                         "(o id do formulario instantaneo ja criado na pagina)")
    elif destino == "whatsapp":
        if not r.get("pagina"):
            raise Recusa("destino whatsapp exige `pagina`. E o numero NAO vai no criativo: "
                         "ele mora no promoted_object, junto da pagina.")
    elif destino == "site":
        if objetivo == "OUTCOME_SALES" and not r.get("pixel"):
            raise Recusa("OUTCOME_SALES exige `pixel` (promoted_object = pixel + evento)")
        if not any(a.get("link") for a in r["anuncios"]):
            raise Recusa("destino site exige `link` em cada anuncio")

    for i, a in enumerate(r["anuncios"], 1):
        for campo in ("nome", "texto"):
            if not a.get(campo):
                raise Recusa("anuncio %d: falta `%s`" % (i, campo))
        if not a.get("imagem_hash") and not a.get("video_id"):
            raise Recusa("anuncio %d: precisa de `imagem_hash` ou `video_id`.\n"
                         "  imagem: python -m magicads imagem <cliente> <conta> <arquivo>\n"
                         "  video:  python -m magicads video  <cliente> <conta> <arquivo>" % i)
        if a.get("video_id") and not a.get("capa_hash"):
            raise Recusa("anuncio %d: video exige `capa_hash`. Escolha um frame, suba com "
                         "`magicads imagem` e ponha o hash ali.\n"
                         "  Sem capa a Meta pega um frame sozinha, e frame sorteado de video "
                         "vertical costuma ser a pessoa de olho fechado." % i)
        if a.get("video_id") and a.get("imagem_hash"):
            raise Recusa("anuncio %d: escolha UM criativo. Com `video_id` e `imagem_hash` "
                         "juntos, a Meta usa o video e ignora a imagem em silencio -- e voce "
                         "passa a tarde achando que testou as duas." % i)

    avisos = []
    if conj.get("advantage_audience") == 1 and tipo == "b2b":
        avisos.append("advantage_audience=1 em conta B2B torna sua demografia decorativa: "
                      "a Meta entrega fora da faixa que voce travou. Em publico pequeno e "
                      "especifico isso costuma doer.")
    if camp.get("verba_diaria"):
        avisos.append("verba na CAMPANHA (CBO) cobra o minimo por CONJUNTO ATIVO. "
                      "Com varios conjuntos ligados e verba pequena, o piso estoura o planejado.")
    posic = conj.get("posicionamentos")
    if posic and "instagram" in posic and not r.get("instagram_id"):
        avisos.append("posicionamento no Instagram sem `instagram_id`: o anuncio roda no IG "
                      "com o nome e a foto da PAGINA do Facebook. Funciona, e parece de outra "
                      "marca pra quem ve.")
    if not posic:
        avisos.append("sem `conjunto.posicionamentos`, a Meta escolhe onde entregar -- e "
                      "costuma achar volume barato em Audience Network. Se voce so quer feed e "
                      "stories, diga.")
    return objetivo, otimizacao, destino, avisos


# ---------------------------------------------------------------------------
# montagem dos quatro payloads
# ---------------------------------------------------------------------------
def monta(r, objetivo, otimizacao, destino):
    camp, conj = r["campanha"], r["conjunto"]

    p_campanha = {
        "name": camp["nome"],
        "objective": objetivo,
        "status": "PAUSED",
        # Obrigatorio mesmo vazio. Faltando, a Meta recusa com mensagem que
        # nao cita o campo.
        "special_ad_categories": json.dumps(camp.get("categorias_especiais") or []),
    }
    if camp.get("verba_diaria"):
        # CBO: a verba mora na campanha e ela reparte entre os conjuntos.
        p_campanha["daily_budget"] = str(int(camp["verba_diaria"]))
        p_campanha["bid_strategy"] = camp.get("estrategia") or "LOWEST_COST_WITHOUT_CAP"
    else:
        # ABO: a verba mora no conjunto. Desde 2026 a Meta RECUSA a campanha sem
        # este campo, e recusa mal: `message` diz so "Invalid parameter", e o
        # motivo real so aparece em `error_user_title`. Visto ao vivo em
        # 14/09/2026, na primeira vez que o `subir --executar` rodou de verdade:
        #
        #   100 / 4834011  "E necessario especificar True ou False no campo
        #                   is_adset_budget_sharing_enabled"
        #
        # `false` de proposito: com `true` a Meta reparte ate 20% do orcamento
        # entre os conjuntos, e ai acaba a separacao por loja, praca ou unidade
        # -- que costuma ser a unica razao de ter mais de um conjunto.
        p_campanha["is_adset_budget_sharing_enabled"] = "false"

    alvo = copy.deepcopy(conj["geo"])
    if conj.get("idade"):
        alvo["age_min"], alvo["age_max"] = conj["idade"][0], conj["idade"][1]
    if conj.get("generos"):
        alvo["genders"] = conj["generos"]
    if conj.get("interesses"):
        alvo.setdefault("flexible_spec", []).append({"interests": conj["interesses"]})
    if conj.get("publicos_incluir"):
        alvo["custom_audiences"] = [{"id": i} for i in conj["publicos_incluir"]]
    if conj.get("publicos_excluir"):
        alvo["excluded_custom_audiences"] = [{"id": i} for i in conj["publicos_excluir"]]
    alvo["targeting_automation"] = {"advantage_audience": int(conj.get("advantage_audience", 0))}

    # Instagram nao e canal separado: e posicionamento da mesma API. Declarar as
    # plataformas evita que a Meta va buscar volume barato em Audience Network,
    # que enche o relatorio de impressao e nao enche nada mais.
    posic = conj.get("posicionamentos")
    if posic:
        alvo["publisher_platforms"] = list(posic)
        if conj.get("posicoes_facebook"):
            alvo["facebook_positions"] = conj["posicoes_facebook"]
        if conj.get("posicoes_instagram"):
            alvo["instagram_positions"] = conj["posicoes_instagram"]

    p_conjunto = {
        "name": conj.get("nome") or "[A01] conjunto 1",
        "status": "PAUSED",
        "optimization_goal": otimizacao,
        "billing_event": conj.get("cobranca") or "IMPRESSIONS",
        "bid_strategy": conj.get("estrategia") or "LOWEST_COST_WITHOUT_CAP",
        "targeting": json.dumps(alvo),
    }
    if not camp.get("verba_diaria"):
        p_conjunto["daily_budget"] = str(int(conj["verba_diaria"]))
    if conj.get("inicio"):
        p_conjunto["start_time"] = conj["inicio"]

    if destino == "formulario":
        p_conjunto["promoted_object"] = json.dumps({"page_id": str(r["pagina"])})
        p_conjunto["destination_type"] = "ON_AD"
    elif destino == "whatsapp":
        p_conjunto["promoted_object"] = json.dumps({"page_id": str(r["pagina"])})
        p_conjunto["destination_type"] = "WHATSAPP"
    elif r.get("pixel"):
        p_conjunto["promoted_object"] = json.dumps({
            "pixel_id": str(r["pixel"]),
            "custom_event_type": r.get("evento") or "PURCHASE",
        })

    criativos, anuncios = [], []
    for a in r["anuncios"]:
        # O destino decide o link e o botao, e isso vale igual pra imagem e video.
        if destino == "formulario":
            link = "http://fb.me/"      # exigido pela API, ignorado no formulario
            botao = {"type": a.get("cta") or "SIGN_UP",
                     "value": {"lead_gen_form_id": str(a["formulario_id"])}}
        elif destino == "whatsapp":
            link = a.get("link") or "https://api.whatsapp.com/send"
            botao = {"type": a.get("cta") or "WHATSAPP_MESSAGE"}
        else:
            link = a["link"]
            botao = {"type": a.get("cta") or "LEARN_MORE", "value": {"link": a["link"]}}

        if a.get("video_id"):
            # video_data e link_data tem nomes DIFERENTES pros mesmos campos.
            # `name` vira `title`, `description` vira `link_description`. Copiar o
            # bloco de imagem e trocar so a midia gera anuncio sem titulo.
            midia = {
                "video_id": str(a["video_id"]),
                "image_hash": a["capa_hash"],
                "message": a["texto"],
                "title": a.get("titulo") or "",
                "link_description": a.get("descricao") or "",
                "call_to_action": botao,
            }
            historia = {"video_data": midia}
        else:
            midia = {
                "message": a["texto"],
                "name": a.get("titulo") or "",
                "description": a.get("descricao") or "",
                "image_hash": a["imagem_hash"],
                "link": link,
                "call_to_action": botao,
            }
            historia = {"link_data": midia}

        historia["page_id"] = str(r.get("pagina") or "")
        criativo = {"name": "%s (criativo)" % a["nome"],
                    "object_story_spec": json.dumps(historia)}
        if r.get("instagram_id"):
            # Sem isto o anuncio roda no Instagram com a identidade da Pagina do
            # Facebook: nome e foto de outra marca, pra quem ve.
            criativo["instagram_actor_id"] = str(r["instagram_id"])
        criativos.append(criativo)
        anuncios.append({"name": a["nome"], "status": "PAUSED"})

    return p_campanha, p_conjunto, criativos, anuncios


# ---------------------------------------------------------------------------
# execucao
# ---------------------------------------------------------------------------
def chama(caminho, campos, token):
    campos = dict(campos)
    campos["access_token"] = token
    return http("%s/%s" % (GRAPH, caminho), form=campos, method="POST")


def confere(ident, token, campos="id,name,status"):
    """Sempre por GET no proprio id. Listagem sob rate limit devolve vazio com
    HTTP 200, que parece 'nao criou' e e 'nao vejo'."""
    try:
        return http("%s/%s?fields=%s&access_token=%s" % (GRAPH, ident, campos, token))
    except RuntimeError as e:
        return {"erro": limpa(str(e))[:120]}


def executa(r, token, p_campanha, p_conjunto, criativos, anuncios):
    conta = r["conta"]
    criados = []

    diz("")
    diz("CRIANDO DE VERDADE em %s. Tudo nasce PAUSED." % conta)
    diz("-" * 72)

    # 1. campanha. Sem ensaio possivel: validate_only NAO protege em /campaigns,
    # a Meta cria de verdade nesse endpoint com ou sem a flag.
    try:
        resp = chama("%s/campaigns" % conta, p_campanha, token)
    except RuntimeError as e:
        diz("campanha FALHOU: %s" % limpa(e))
        return 1
    id_campanha = resp["id"]
    criados.append(("campanha", id_campanha))
    diz("campanha  %s  %s" % (id_campanha, p_campanha["name"]))

    # 2. conjunto: aqui validate_only funciona, entao ensaiamos antes de valer.
    p_conjunto = dict(p_conjunto, campaign_id=id_campanha)
    ensaio = dict(p_conjunto, execution_options=json.dumps(["validate_only"]))
    try:
        chama("%s/adsets" % conta, ensaio, token)
    except RuntimeError as e:
        codigo, subcodigo, msg = erro_da_meta(str(e))
        diz("conjunto REPROVOU na validacao: %s" % limpa(msg))
        if subcodigo == 2446886:
            diz("")
            diz("subcode 2446886: a Pagina NAO tem conta de WhatsApp conectada.")
            diz("A tarefa MESSAGING nao supre isso. Conserto e do CLIENTE, no Business")
            diz("Suite: Configuracoes da Pagina -> WhatsApp -> conectar o numero.")
        limpeza(criados)
        return 1

    try:
        resp = chama("%s/adsets" % conta, p_conjunto, token)
    except RuntimeError as e:
        diz("conjunto FALHOU depois de validar: %s" % limpa(e))
        limpeza(criados)
        return 1
    id_conjunto = resp["id"]
    criados.append(("conjunto", id_conjunto))
    diz("conjunto  %s  %s" % (id_conjunto, p_conjunto["name"]))

    # 3 e 4. criativo e anuncio, um par por anuncio da receita
    for criativo, anuncio in zip(criativos, anuncios):
        try:
            resp = chama("%s/adcreatives" % conta, criativo, token)
            id_criativo = resp["id"]
            corpo = dict(anuncio, adset_id=id_conjunto,
                         creative=json.dumps({"creative_id": id_criativo}))
            resp = chama("%s/ads" % conta, corpo, token)
        except RuntimeError as e:
            diz("anuncio %r FALHOU: %s" % (anuncio["name"], limpa(e)))
            diz("a campanha e o conjunto ficaram de pe (PAUSED). Veja abaixo.")
            resumo(criados, token)
            return 1
        criados.append(("anuncio", resp["id"]))
        diz("anuncio   %s  %s" % (resp["id"], anuncio["name"]))

    resumo(criados, token)
    diz("")
    diz("Tudo PAUSED. Revise no gerenciador e ligue com:")
    diz("  python -m magicads ativar %s %s --executar" % (r["cliente"], id_campanha))
    return 0


def limpeza(criados):
    """Nao apaga sozinho: apagar por conta propria e como o script decidir que a
    sua campanha nao serve. Mostra o que ficou de pe e o comando exato.

    O que nao se faz e ficar calado: orfao silencioso e como se descobre, tres
    semanas depois, que tem campanha sua parada na conta de um cliente.
    """
    if not criados:
        return
    diz("")
    diz("O QUE JA TINHA SIDO CRIADO (esta PAUSED, nao gasta nada):")
    for tipo, ident in criados:
        diz("   %-9s %s" % (tipo, ident))
    diz("")
    diz("Pra remover, do mais novo pro mais velho:")
    for tipo, ident in reversed(criados):
        diz("   python -m magicads remover <cliente> %s --executar" % ident)


def resumo(criados, token):
    diz("")
    diz("CONFERINDO POR GET (nunca por listagem):")
    for tipo, ident in criados:
        d = confere(ident, token)
        diz("   %-9s %s  status=%s  %s"
            % (tipo, ident, d.get("status", d.get("erro", "?")), d.get("name", "")))


# ---------------------------------------------------------------------------
# imagem
# ---------------------------------------------------------------------------
def sobe_midia(argv, tipo):
    """Sobe imagem ou video pra biblioteca da conta e devolve o identificador.

    Sao dois endpoints, os dois em multipart. O nome do campo vira o nome da
    imagem na biblioteca da conta. O id do video que sai DAQUI e o que
    serve pra montar publico de visualizacao depois -- o arquivo no seu disco
    nao existe pra Meta.
    """
    from .cli import token as token_do_cofre
    if len(argv) < 3:
        sys.exit("uso: python -m magicads %s <cliente> <act_...> <arquivo>" % tipo)
    cliente, conta, arquivo = argv[0], argv[1], argv[2]
    if not os.path.exists(arquivo):
        sys.exit("arquivo nao existe: %s" % arquivo)
    _, tok = token_do_cofre(cliente)
    guarda_segredo(tok)

    if tipo == "video":
        diz("subindo %s... (video demora; a Meta ainda processa depois do 200)" % arquivo)
        resp = http_arquivo("%s/%s/advideos" % (GRAPH, conta),
                            {"access_token": tok}, "source", arquivo)
        ident = resp.get("id")
        if not ident:
            diz(json.dumps(resp, ensure_ascii=False))
            return 1
        diz("video_id: %s" % ident)
        diz("")
        diz("Ponha na receita junto de `capa_hash` (um frame subido com `imagem`).")
        diz("O video pode levar alguns minutos pra ficar pronto. Se o anuncio falhar")
        diz("dizendo que o video nao esta disponivel, espere e repita -- nao suba de novo.")
        return 0

    # Multipart, com o nome do arquivo no campo. Duas razoes, e a segunda so
    # apareceu rodando ao vivo:
    #
    #   1. O NOME DO CAMPO vira o nome da imagem na biblioteca da conta. Com o
    #      caminho de base64 o campo TEM que se chamar `bytes` (trocar o nome
    #      derruba o upload com 100/2490361, "arquivo de imagem invalido"), e ai
    #      toda imagem da conta se chama "bytes" -- a biblioteca deixa de servir
    #      pra achar qualquer coisa, e voce nao sabe qual hash e qual criativo.
    #   2. Multipart aceita o nome do arquivo, e a imagem nasce chamada
    #      `oferta-agosto.jpg` em vez de `bytes`.
    campo = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(arquivo)) or "imagem.jpg"
    resp = http_arquivo("%s/%s/adimages" % (GRAPH, conta),
                        {"access_token": tok}, campo, arquivo)
    imagens = resp.get("images") or {}
    for nome, dado in imagens.items():
        diz("imagem_hash: %s   (%s)" % (dado.get("hash"), nome))
    if not imagens:
        diz(json.dumps(resp, ensure_ascii=False))
        return 1
    return 0


def sobe_imagem(argv):
    return sobe_midia(argv, "imagem")


def sobe_video(argv):
    return sobe_midia(argv, "video")


# ---------------------------------------------------------------------------
def main(argv):
    if not argv:
        print(__doc__)
        return 1
    caminho = argv[0]
    if not os.path.exists(caminho):
        sys.exit("receita nao encontrada: %s" % caminho)
    with open(caminho, encoding="utf-8") as fh:
        try:
            r = json.load(fh)
        except ValueError as e:
            sys.exit("receita nao e JSON valido: %s" % e)

    try:
        objetivo, otimizacao, destino, avisos = valida(r)
    except Recusa as e:
        diz("RECEITA RECUSADA: %s" % e)
        return 1

    p_campanha, p_conjunto, criativos, anuncios = monta(r, objetivo, otimizacao, destino)

    diz("receita  %s" % caminho)
    diz("tipo     %s  ·  objetivo %s  ·  otimizacao %s  ·  destino %s"
        % (r["tipo"], objetivo, otimizacao, destino))
    diz("conta    %s  ·  cliente %s" % (r["conta"], r["cliente"]))
    for a in avisos:
        diz("AVISO: %s" % a)

    if "--executar" not in argv:
        diz("")
        diz("ENSAIO. Nada foi enviado. Os payloads montados:")
        diz("-" * 72)
        diz("CAMPANHA\n%s" % json.dumps(p_campanha, ensure_ascii=False, indent=2))
        diz("CONJUNTO\n%s" % json.dumps(p_conjunto, ensure_ascii=False, indent=2))
        for c, a in zip(criativos, anuncios):
            diz("CRIATIVO\n%s" % json.dumps(c, ensure_ascii=False, indent=2))
            diz("ANUNCIO\n%s" % json.dumps(a, ensure_ascii=False, indent=2))
        diz("-" * 72)
        diz("Conferiu? Rode de novo com --executar.")
        return 0

    from .cli import token as token_do_cofre
    _, tok = token_do_cofre(r["cliente"])
    guarda_segredo(tok)
    return executa(r, tok, p_campanha, p_conjunto, criativos, anuncios)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
