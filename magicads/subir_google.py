# -*- coding: utf-8 -*-
"""Sobe campanha de Search no Google Ads a partir de uma receita JSON.

POR QUE DEMOROU A EXISTIR
Nao foi falta de API. A API do Google Ads cria campanha, grupo, anuncio e
palavra-chave sem problema -- quem nao fazia era esta ferramenta. O que segurou
foi o modelo de receita: a anatomia do Search e outra. Palavra-chave, tipo de
correspondencia, NEGATIVA, grupo de anuncio. Portar a receita da Meta sem essas
pecas produziria campanha que roda e queima, e uma receita que gera Search sem
lista de negativas e uma maquina de comprar clique errado em dois comandos.

Entao a lista de negativas e OBRIGATORIA. Sem ela o codigo recusa, e recusa
antes de falar com o Google.

O QUE E DIFERENTE DA META, E IMPORTA
1. `validateOnly` aqui FUNCIONA. Na Meta ele nao protege em /campaigns: manda e
   cria. No Google Ads ele e honesto em todos os mutate, entao existe um passo
   que a Meta nao pode ter: `--conferir` pergunta ao Google se o payload passa,
   sem criar nada.
2. Tudo sobe numa TRANSACAO SO (`googleAds:mutate`), com id temporario
   negativo amarrando orcamento -> campanha -> grupo -> anuncio. E atomico: ou
   entra tudo, ou nao entra nada. Por isso aqui nao existe orfao, e nao existe
   o "olha o que ja foi criado" que o subir.py da Meta precisa ter.
3. O customer id vai SEM tracos na URL, e o MCC vai no cabecalho
   `login-customer-id`, tambem sem tracos.

SEGURANCA (a mesma do subir.py, e pelo mesmo motivo)
1. Modo ENSAIO por padrao: monta, valida, imprime os payloads e NAO chama o
   Google. Criar de verdade exige --executar.
2. Tudo nasce PAUSED. Nao existe opcao de subir ligado, e isso e de proposito:
   revisar antes de gastar e a diferenca entre erro barato e erro caro.
3. Falha no meio nao deixa rastro, porque a transacao e atomica. O erro do
   Google e traduzido: a mensagem de topo e sempre generica, e o nome do campo
   que faltou mora no fim, dentro de `location.fieldPathElements`.

USO
  python -m magicads subir receitas/google-search-local.json
  python -m magicads subir receitas/google-search-local.json --conferir
  python -m magicads subir receitas/google-search-local.json --executar
"""
import json
import os
import sys

from .comum import diz, env, http, limpa

GADS_VER = os.environ.get("MAGICADS_GADS_VERSION", "v25")
BASE = "https://googleads.googleapis.com/" + GADS_VER

# Constantes geograficas de pais: 2000 + o numero ISO 3166-1 do pais, entao
# BR (076) = 2076. Qualquer outro alvo (estado, cidade, raio) entra como id cru
# em `geo.ids`, porque adivinhar id de cidade e comprar trafego no lugar errado
# sem ninguem perceber.
PAISES = {"BR": 2076, "PT": 2620, "US": 2840, "AR": 2032, "MX": 2484}

# Limites que o Google recusa com mensagem que nao diz qual campo.
LIM_TITULO = 30
LIM_DESCRICAO = 90
MIN_TITULOS = 3      # o anuncio responsivo exige 3 titulos e 2 descricoes
MIN_DESCRICOES = 2

CORRESPONDENCIAS = ("EXACT", "PHRASE", "BROAD")

# Quatro negativas que quase toda conta brasileira precisa. Nao entram
# sozinhas: sao o exemplo que a mensagem de recusa mostra.
NEGATIVAS_MINIMAS = ["gratis", "gratuito", "como fazer", "vaga"]


class Recusa(Exception):
    """Erro de receita: o problema esta no arquivo, nao no Google."""


# ---------------------------------------------------------------------------
# validacao: falhar aqui e de graca, falhar no Google custa uma hora
# ---------------------------------------------------------------------------
def valida(r):
    for campo in ("cliente", "conta", "campanha", "grupo", "anuncio"):
        if not r.get(campo):
            raise Recusa("falta `%s` na receita" % campo)

    conta = str(r["conta"]).replace("-", "")
    if not conta.isdigit() or len(conta) != 10:
        raise Recusa("`conta` tem que ser o customer id de 10 digitos (com ou "
                     "sem tracos), e veio %r" % r["conta"])

    camp = r["campanha"]
    if not camp.get("nome"):
        raise Recusa("falta `campanha.nome`")
    verba = camp.get("verba_diaria")
    if not verba or int(verba) <= 0:
        raise Recusa("falta `campanha.verba_diaria`, em micros da moeda da "
                     "conta: R$ 30,00/dia = 30000000")

    # Geo obrigatorio. Search sem geo entrega no mundo inteiro, e queima verba
    # tao rapido quanto falta de negativa -- so que mais silenciosamente,
    # porque a metrica parece "so" ruim, em vez de errada.
    geo = camp.get("geo") or {}
    if not geo.get("paises") and not geo.get("ids"):
        raise Recusa('falta `campanha.geo`. Search sem geo entrega no mundo '
                     'inteiro. Use {"paises": ["BR"]} ou {"ids": [1001773]}')
    for p in geo.get("paises") or []:
        if p not in PAISES:
            raise Recusa("pais %r nao esta no mapa (%s). Use `ids` com a "
                         "constante geografica crua."
                         % (p, ", ".join(sorted(PAISES))))

    grupo = r["grupo"]
    if not grupo.get("nome"):
        raise Recusa("falta `grupo.nome`")
    if not grupo.get("palavras"):
        raise Recusa("falta `grupo.palavras`: sem palavra-chave o grupo nao entrega")
    for k in grupo["palavras"]:
        if not k.get("texto"):
            raise Recusa("palavra sem `texto`: %r" % (k,))
        corr = (k.get("correspondencia") or "PHRASE").upper()
        if corr not in CORRESPONDENCIAS:
            raise Recusa("correspondencia %r invalida em %r. Use uma de: %s"
                         % (corr, k["texto"], ", ".join(CORRESPONDENCIAS)))

    # A regra por causa da qual esta receita levou tanto tempo pra existir.
    if not grupo.get("negativas"):
        raise Recusa(
            "falta `grupo.negativas`, e aqui ela e OBRIGATORIA.\n"
            "  Search sem lista de negativas compra 'gratis', 'como fazer', "
            "'vaga de emprego', 'curso' e o nome dos seus concorrentes.\n"
            "  Comece por estas quatro: %s\n"
            "  Lista vazia nao conta: se voce escrever [], a recusa continua."
            % json.dumps(NEGATIVAS_MINIMAS, ensure_ascii=False))
    for n in grupo["negativas"]:
        if not str(n).strip():
            raise Recusa("negativa vazia na lista")

    an = r["anuncio"]
    titulos = an.get("titulos") or []
    descricoes = an.get("descricoes") or []
    if len(titulos) < MIN_TITULOS:
        raise Recusa("o anuncio responsivo exige pelo menos %d titulos, e veio %d"
                     % (MIN_TITULOS, len(titulos)))
    if len(descricoes) < MIN_DESCRICOES:
        raise Recusa("o anuncio responsivo exige pelo menos %d descricoes, e veio %d"
                     % (MIN_DESCRICOES, len(descricoes)))
    for t in titulos:
        if len(t) > LIM_TITULO:
            raise Recusa("titulo com %d caracteres (o limite e %d): %r"
                         % (len(t), LIM_TITULO, t))
    for d in descricoes:
        if len(d) > LIM_DESCRICAO:
            raise Recusa("descricao com %d caracteres (o limite e %d): %r"
                         % (len(d), LIM_DESCRICAO, d))
    if not an.get("url"):
        raise Recusa("falta `anuncio.url`")
    if not str(an["url"]).startswith("http"):
        raise Recusa("`anuncio.url` tem que comecar com http(s): %r" % an["url"])
    return conta

# ---------------------------------------------------------------------------
# montagem: UMA transacao com todos os objetos, nao seis chamadas encadeadas
#
# A primeira versao chamava um servico por vez (campaignBudgets, campaigns,
# adGroups...) e usava o resourceName devolvido pra amarrar o proximo. Isso tem
# dois defeitos, e o Google mostrou os dois em dez minutos:
#
# 1. `--conferir` nao funcionava. Em validateOnly nada e criado, entao nao ha
#    resourceName pra referenciar, e a campanha era recusada por
#    `campaign_budget REQUIRED`. Um modo de conferir que nunca passa nao e um
#    modo de conferir.
# 2. Falha no meio deixa ORFAO. Orcamento criado e campanha recusada = lixo na
#    conta do cliente, e lixo que ninguem procura porque ninguem sabe que existe.
#
# `googleAds:mutate` resolve os dois de uma vez: aceita id TEMPORARIO negativo
# (`campaignBudgets/-1`), que as operacoes seguintes referenciam dentro da mesma
# requisicao, e e ATOMICO -- ou entra tudo, ou nao entra nada. Com isso o
# `limpeza()` de orfao deixou de ser necessario, o que e a melhor especie de
# codigo removido.
# ---------------------------------------------------------------------------
def monta(r):
    camp = r["campanha"]
    grupo = r["grupo"]
    an = r["anuncio"]
    conta = str(r["conta"]).replace("-", "")

    def rn(tipo, temp):
        return "customers/%s/%s/%d" % (conta, tipo, temp)

    orcamento = rn("campaignBudgets", -1)
    campanha = rn("campaigns", -2)
    ad_grupo = rn("adGroups", -3)

    ops = []

    ops.append({"campaignBudgetOperation": {"create": {
        "resourceName": orcamento,
        "name": "%s | orcamento" % camp["nome"],
        "amountMicros": str(int(camp["verba_diaria"])),
        "deliveryMethod": "STANDARD",
        # Nao compartilhado: orcamento compartilhado e como uma campanha come a
        # verba da outra sem aparecer em lugar nenhum do relatorio.
        "explicitlyShared": False,
    }}})

    criar_campanha = {
        "resourceName": campanha,
        "name": camp["nome"],
        "campaignBudget": orcamento,
        "status": "PAUSED",                 # sempre, e nao tem flag pra mudar
        "advertisingChannelType": "SEARCH",
        # Campo NOVO e OBRIGATORIO em toda campanha (regra de publicidade
        # politica da UE). Sem ele o Google devolve `REQUIRED` com a mensagem
        # generica "The required field was not present." -- o nome do campo so
        # aparece dentro de `location.fieldPathElements`, que e justamente o
        # que some quando voce trunca o erro. Descoberto com validateOnly numa
        # conta real, e e o tipo de campo que aparece de repente numa versao
        # nova da API e quebra quem nao acompanha o changelog.
        "containsEuPoliticalAdvertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
        # Manual CPC de proposito. Lance automatico precisa de historico de
        # conversao pra ter o que otimizar; numa campanha que nasce hoje ele
        # gasta pra aprender, e quem paga a aula e o cliente.
        "manualCpc": {},
        # So Rede de Pesquisa. Parceiros e Display vem LIGADOS por padrao na
        # interface, e e assim que Search vira Display sem ninguem decidir.
        "networkSettings": {
            "targetGoogleSearch": True,
            "targetSearchNetwork": False,
            "targetContentNetwork": False,
            "targetPartnerSearchNetwork": False,
        },
    }
    if camp.get("inicio"):
        criar_campanha["startDate"] = camp["inicio"]
    if camp.get("fim"):
        criar_campanha["endDate"] = camp["fim"]
    ops.append({"campaignOperation": {"create": criar_campanha}})

    geo = camp.get("geo") or {}
    alvos = ["geoTargetConstants/%d" % PAISES[p] for p in geo.get("paises") or []]
    alvos += ["geoTargetConstants/%s" % i for i in geo.get("ids") or []]
    for alvo in alvos:
        ops.append({"campaignCriterionOperation": {"create": {
            "campaign": campanha,
            "location": {"geoTargetConstant": alvo},
        }}})

    ops.append({"adGroupOperation": {"create": {
        "resourceName": ad_grupo,
        "campaign": campanha,
        "name": grupo["nome"],
        "status": "PAUSED",
        "type": "SEARCH_STANDARD",
        "cpcBidMicros": str(int(grupo.get("lance_micros") or 1000000)),
    }}})

    for k in grupo["palavras"]:
        ops.append({"adGroupCriterionOperation": {"create": {
            "adGroup": ad_grupo,
            "status": "ENABLED",
            "keyword": {"text": k["texto"],
                        "matchType": (k.get("correspondencia") or "PHRASE").upper()},
        }}})
    for n in grupo["negativas"]:
        # Negativa em BROAD: negativa de frase deixa passar a variacao, e a
        # variacao e justamente o que voce nao quer comprar.
        ops.append({"adGroupCriterionOperation": {"create": {
            "adGroup": ad_grupo,
            "negative": True,
            "keyword": {"text": str(n), "matchType": "BROAD"},
        }}})

    rsa = {
        "headlines": [{"text": t} for t in an["titulos"]],
        "descriptions": [{"text": d} for d in an["descricoes"]],
    }
    if an.get("caminho1"):
        rsa["path1"] = an["caminho1"]
    if an.get("caminho2"):
        rsa["path2"] = an["caminho2"]
    ops.append({"adGroupAdOperation": {"create": {
        "adGroup": ad_grupo,
        "status": "PAUSED",
        "ad": {"finalUrls": [an["url"]], "responsiveSearchAd": rsa},
    }}})

    return {"mutateOperations": ops}


def conta_operacoes(payload):
    """Quantas de cada tipo, pro resumo de uma linha."""
    conta = {}
    for op in payload["mutateOperations"]:
        chave = list(op.keys())[0].replace("Operation", "")
        conta[chave] = conta.get(chave, 0) + 1
    return conta


# ---------------------------------------------------------------------------
# execucao
# ---------------------------------------------------------------------------
def token_google():
    """Access token a partir do refresh token. Mesma conta de servico do ETL."""
    import urllib.parse
    import urllib.request
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
        return json.loads(r.read())["access_token"]


def cabecalhos(at):
    dev = env("MAGICADS_GADS_DEVELOPER_TOKEN")
    if not dev:
        raise Recusa(
            "falta MAGICADS_GADS_DEVELOPER_TOKEN.\n"
            "  Ele sai no API Center de uma conta de administrador (MCC), e\n"
            "  nasce em ACESSO DE TESTE, que so fala com conta de teste. Pra\n"
            "  tocar conta de producao voce SOLICITA a subida de nivel, e o\n"
            "  Google revisa. Ver aios/fluxos/google-ads.md")
    h = {"Authorization": "Bearer %s" % at, "developer-token": dev,
         "Content-Type": "application/json"}
    mcc = env("MAGICADS_GADS_LOGIN_CUSTOMER_ID", segredo=False)
    if mcc:
        h["login-customer-id"] = mcc.replace("-", "")
    return h


def explica_erro(bruto):
    """O erro do Google Ads guarda a informacao util no FIM.

    A mensagem de topo e sempre "Request contains an invalid argument.", e o
    nome do campo que faltou mora em `details[].errors[].location
    .fieldPathElements`. Quem trunca o erro pra caber na tela joga fora
    exatamente a unica parte que responde "o que eu faco agora".
    """
    try:
        i = bruto.index("{")
        d = json.loads(bruto[i:])
    except Exception:
        return [limpa(bruto)[:300]]
    saida = []
    for det in (d.get("error", {}).get("details") or []):
        for err in det.get("errors") or []:
            campos = [e.get("fieldName") for e
                      in (err.get("location") or {}).get("fieldPathElements") or []]
            codigo = err.get("errorCode") or {}
            codigo = "%s=%s" % tuple(list(codigo.items())[0]) if codigo else "?"
            saida.append("%s  em `%s`  (%s)"
                         % (err.get("message", "?"), ".".join(c for c in campos if c),
                            codigo))
    return saida or [limpa(bruto)[:300]]


def envia(conta, payload, at, so_validar):
    """Uma transacao. Atomica: ou entra tudo, ou nao entra nada."""
    corpo = dict(payload)
    if so_validar:
        corpo["validateOnly"] = True
    url = "%s/customers/%s/googleAds:mutate" % (BASE, conta)
    return http(url, data=corpo, method="POST", headers=cabecalhos(at))


def resumo_criado(resposta):
    """Os resourceName que nasceram, na ordem."""
    saida = []
    for res in (resposta or {}).get("mutateOperationResponses") or []:
        for chave, corpo in res.items():
            rn = (corpo or {}).get("resourceName")
            if rn:
                saida.append((chave.replace("Result", ""), rn))
    return saida


def executa(r, conta, payload, so_validar):
    at = token_google()
    try:
        resposta = envia(conta, payload, at, so_validar)
    except Exception as e:
        diz("")
        diz("  O GOOGLE RECUSOU. Nada foi criado (a transacao e atomica).")
        for linha in explica_erro(str(e)):
            diz("    %s" % linha)
        return 1

    criados = resumo_criado(resposta)
    diz("")
    if so_validar:
        diz("  O Google validou a transacao inteira e NAO criou nada.")
        diz("  %d operacoes. Agora com --executar, se estiver certo."
            % len(payload["mutateOperations"]))
        return 0

    for rotulo, rn in criados:
        diz("  %-22s %s" % (rotulo, rn))
    diz("")
    diz("  Tudo PAUSED. Revise na interface e ligue la.")
    diz("  Ligar por aqui nao existe de proposito: revisar antes de gastar e a")
    diz("  diferenca entre erro barato e erro caro.")
    return 0


def sobe(r, argv):
    """Chamado pelo `subir` quando a receita diz `canal: google`."""
    executar = "--executar" in argv
    conferir = "--conferir" in argv

    conta = valida(r)
    payload = monta(r)
    quantos = conta_operacoes(payload)

    diz("")
    diz("GOOGLE ADS - SEARCH - %s - conta %s" % (r.get("cliente"), conta))
    diz("=" * 72)
    grupo = r["grupo"]
    diz("  %d palavra(s), %d negativa(s), %d titulo(s), %d descricao(oes)"
        % (len(grupo["palavras"]), len(grupo["negativas"]),
           len(r["anuncio"]["titulos"]), len(r["anuncio"]["descricoes"])))
    diz("  %d operacoes numa transacao atomica: %s"
        % (len(payload["mutateOperations"]),
           ", ".join("%s x%d" % (k, v) for k, v in sorted(quantos.items()))))

    if not executar and not conferir:
        diz("")
        diz("ENSAIO. Nada foi enviado ao Google.")
        diz("")
        diz(json.dumps(payload, indent=2, ensure_ascii=False))
        diz("")
        diz("Conferir COM o Google, sem criar:  --conferir")
        diz("Criar de verdade (nasce PAUSED):   --executar")
        return 0

    if conferir and not executar:
        diz("")
        diz("CONFERINDO com o Google (validateOnly). Nada sera criado.")
        diz("Este passo so existe no Google porque aqui o validateOnly e honesto.")
        diz("Na Meta, /campaigns com validate_only CRIA de verdade.")
        return executa(r, conta, payload, so_validar=True)

    diz("")
    diz("EXECUTANDO. Tudo nasce PAUSED.")
    return executa(r, conta, payload, so_validar=False)


# ---------------------------------------------------------------------------
# remocao
# ---------------------------------------------------------------------------
def remove(conta, campanha_id, executar):
    """Remove a campanha E o orcamento dela, e PROVA relendo.

    O orcamento nao vai junto. Remover a campanha na interface deixa o
    `campaignBudget` vivo e sem dono, e ele nao aparece em nenhuma tela que voce
    olha no dia a dia. Numa conta que ja apanhou de script, orcamento orfao e o
    lixo mais comum que existe -- e como este modulo cria um orcamento por
    campanha, seria ele mesmo produzindo o lixo.

    Prova por LEITURA, nunca pela resposta do mutate. A licao veio da Meta, onde
    `_method=DELETE` devolve `{"success": true}` com o objeto vivo: resposta de
    sucesso nao e prova de nada, reler e.
    """
    conta = str(conta).replace("-", "")
    at = token_google()
    h = cabecalhos(at)

    def busca(sql):
        return http("%s/customers/%s/googleAds:search" % (BASE, conta),
                    data={"query": sql}, method="POST", headers=h).get("results", [])

    achados = busca(
        "SELECT campaign.resource_name, campaign.name, campaign.status, "
        "campaign_budget.resource_name, campaign_budget.name "
        "FROM campaign WHERE campaign.id = %s" % int(campanha_id))
    if not achados:
        diz("campanha %s nao existe nessa conta." % campanha_id)
        return 1
    x = achados[0]
    camp_rn = x["campaign"]["resourceName"]
    orc_rn = x["campaignBudget"]["resourceName"]
    diz("")
    diz("  campanha  %s  [%s]" % (x["campaign"]["name"], x["campaign"]["status"]))
    diz("  orcamento %s" % x["campaignBudget"]["name"])

    if not executar:
        diz("")
        diz("  ENSAIO. Nada foi removido.")
        diz("  Remover nao tem desfazer barato: a campanha vira REMOVED pra")
        diz("  sempre e o historico dela fica, mas ela nao volta.")
        diz("")
        diz("  Se e isso mesmo:")
        diz("    python -m magicads remover-google %s %s --executar"
            % (conta, campanha_id))
        return 0

    def mutate(ops):
        return http("%s/customers/%s/googleAds:mutate" % (BASE, conta),
                    data={"mutateOperations": ops}, method="POST", headers=h)

    try:
        mutate([{"campaignOperation": {"remove": camp_rn}}])
        diz("  campanha  removida")
        mutate([{"campaignBudgetOperation": {"remove": orc_rn}}])
        diz("  orcamento removido")
    except Exception as e:
        diz("")
        diz("  FALHOU:")
        for linha in explica_erro(str(e)):
            diz("    %s" % linha)
        return 1

    depois = busca("SELECT campaign.status FROM campaign WHERE campaign.id = %s"
                   % int(campanha_id))
    orcs = busca("SELECT campaign_budget.status FROM campaign_budget "
                 "WHERE campaign_budget.resource_name = '%s'" % orc_rn)
    st_camp = depois[0]["campaign"]["status"] if depois else "SUMIU"
    st_orc = orcs[0]["campaignBudget"]["status"] if orcs else "SUMIU"
    diz("")
    diz("  conferido relendo: campanha=%s orcamento=%s" % (st_camp, st_orc))
    if st_camp not in ("REMOVED", "SUMIU") or st_orc not in ("REMOVED", "SUMIU"):
        diz("  NAO REMOVEU. Nao risque da lista.")
        return 1
    diz("  removido de verdade.")
    return 0


def main_remover(argv):
    executar = "--executar" in argv
    argv = [a for a in argv if a != "--executar"]
    if len(argv) < 2:
        sys.exit("uso: python -m magicads remover-google <conta> <id-da-campanha> "
                 "[--executar]")
    return remove(argv[0], argv[1], executar)


def pausa(conta, campanha_id):
    """Freio. Executa direto, sem --executar, e PROVA relendo.

    Sem cerimonia de proposito, igual ao `pausar` da Meta: freio que exige
    confirmacao e freio que nao se usa na hora do aperto. Pausar tambem nao
    destroi nada -- da pra despausar na interface --, entao o risco de errar e
    baixo e o custo de hesitar e alto.
    """
    conta = str(conta).replace("-", "")
    h = cabecalhos(token_google())

    def busca(sql):
        return http("%s/customers/%s/googleAds:search" % (BASE, conta),
                    data={"query": sql}, method="POST", headers=h).get("results", [])

    achados = busca("SELECT campaign.resource_name, campaign.name, campaign.status "
                    "FROM campaign WHERE campaign.id = %s" % int(campanha_id))
    if not achados:
        diz("campanha %s nao existe nessa conta." % campanha_id)
        return 1
    c = achados[0]["campaign"]
    if c["status"] == "PAUSED":
        diz("  %s ja estava PAUSED. Nada a fazer." % c["name"])
        return 0
    if c["status"] == "REMOVED":
        diz("  %s esta REMOVED: pausar nao se aplica." % c["name"])
        return 1

    try:
        http("%s/customers/%s/googleAds:mutate" % (BASE, conta),
             data={"mutateOperations": [{"campaignOperation": {
                 "update": {"resourceName": c["resourceName"], "status": "PAUSED"},
                 "updateMask": "status"}}]},
             method="POST", headers=h)
    except Exception as e:
        diz("  FALHOU:")
        for linha in explica_erro(str(e)):
            diz("    %s" % linha)
        return 1

    # Resposta de sucesso nao e prova. A licao veio da Meta, onde o DELETE
    # devolve {"success": true} com o objeto vivo.
    depois = busca("SELECT campaign.status FROM campaign WHERE campaign.id = %s"
                   % int(campanha_id))
    st = depois[0]["campaign"]["status"] if depois else "?"
    diz("  %s  %s -> %s" % (c["name"], c["status"], st))
    if st != "PAUSED":
        diz("  NAO PAUSOU. Nao confie: confira no gerenciador.")
        return 1
    diz("  pausada, conferido relendo.")
    return 0


def main_pausar(argv):
    if len(argv) < 2:
        sys.exit("uso: python -m magicads pausar-google <conta> <id-da-campanha>")
    return pausa(argv[0], argv[1])
