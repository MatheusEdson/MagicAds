# -*- coding: utf-8 -*-
"""O contrato da ferramenta: o que existe, o que devolve, e o que pode rodar
sozinho.

POR QUE EXISTE
Um agente que so tem doutrina inventa flag. Ele sabe que "tem que rodar o diag"
e escreve `magicads diag --cliente acme --completo`, que nao existe, ve o erro,
tenta outra coisa, e em tres tentativas ja perdeu a confianca de quem estava
olhando.

A saida disso NAO e escrever a lista de comandos num arquivo de documentacao: a
lista e o codigo divergem no primeiro commit, e ai o agente passa a mentir com
mais confianca ainda. A ferramenta se descreve. O agente roda

    python -m magicads contrato

no comeco da sessao e passa a saber o que existe, de verdade, naquela versao.

OS QUATRO PORTOES
Mais importante que a lista de comandos: cada um carrega o que acontece se der
errado. E isso que decide o que um agente pode fazer sem perguntar.

  LIVRE    nao muda nada fora do seu banco. Rode a vontade.
  ESCREVE  muda algo na conta do cliente, e NAO gasta (cria pausado, sobe
           midia). Agente pode, e conta depois o que fez.
  FREIO    muda na direcao segura: pausa. Em emergencia o agente roda sozinho e
           avisa DEPOIS -- avisar antes e o que faz a conta gastar mais uma
           hora enquanto alguem le a mensagem.
  HUMANO   gasta dinheiro, ou nao tem desfazer barato. O agente NUNCA roda:
           ele monta o comando, mostra, e espera voce colar.

O agente tambem le `aios/fluxos/` -- o que fazer, em que ordem, por plataforma.
Contrato e a lista de ferramentas; fluxo e o oficio.
"""
import json
import sys

LIVRE = "LIVRE"
ESCREVE = "ESCREVE"
FREIO = "FREIO"
HUMANO = "HUMANO"

PORTOES = [
    (LIVRE, "nao muda nada fora do seu banco. Agente roda a vontade."),
    (ESCREVE, "muda na conta do cliente e NAO gasta. Agente roda e conta depois."),
    (FREIO, "pausa. Em emergencia o agente roda sozinho e avisa DEPOIS."),
    (HUMANO, "gasta dinheiro ou nao tem desfazer barato. Agente NUNCA roda: propoe."),
]

# Uma entrada por comando de `magicads`. O teste tests/test_contrato.py exige
# que esta lista e o despacho de cli.main() sejam exatamente o mesmo conjunto:
# contrato que descreve comando que nao existe e pior que contrato nenhum.
COMANDOS = [
    {
        "nome": "contrato",
        "uso": "python -m magicads contrato [--json]",
        "portao": LIVRE,
        "faz": "imprime este contrato: comandos, portoes e o que cada um devolve.",
        "devolve": "texto, ou JSON com --json.",
        "quando": "primeira coisa da sessao, pra saber o que esta versao tem.",
    },
    {
        "nome": "init",
        "uso": "python -m magicads init",
        "portao": LIVRE,
        "faz": "confere cofre, banco e schema, e diz o que falta. Nao toca na Meta.",
        "devolve": "relatorio de setup. Sai 1 quando falta banco ou schema.",
        "quando": "maquina nova, ou quando algo reclama de tabela que nao existe.",
    },
    {
        "nome": "clientes",
        "uso": "python -m magicads clientes",
        "portao": LIVRE,
        "faz": "lista o cofre e testa cada token com GET /me e /me/adaccounts.",
        "devolve": "por cliente: OK com as contas, ou TOKEN MORTO com o code.",
        "quando": "descobrir quais clientes existem e qual token caiu. "
                  "code 190 sozinho = senha trocada; 190 com subcode 465 = o app "
                  "saiu do portfolio, e ai readicionar sem gerar token novo nao resolve.",
    },
    {
        "nome": "cliente",
        "uso": "python -m magicads cliente [<slug> [nome] [--nicho X] [--cidade Y]]",
        "portao": LIVRE,
        "faz": "sem argumento lista; com argumento cria ou atualiza no SEU banco.",
        "devolve": "a tabela de clientes, ou a confirmacao do que salvou.",
        "quando": "cliente novo, antes de cadastrar a conta.",
    },
    {
        "nome": "conta",
        "uso": "python -m magicads conta [<cliente> <meta|google> <id> [nome] [--remover]]",
        "portao": LIVRE,
        "faz": "liga uma conta de anuncio a um cliente na carteira. --remover desativa "
               "sem apagar, porque o historico ainda vale pra comparacao.",
        "devolve": "a carteira, ou a confirmacao.",
        "quando": "antes do primeiro ETL, e antes de qualquer `pausar --tudo`.",
    },
    {
        "nome": "diag",
        "uso": "python -m magicads diag <cliente>",
        "portao": LIVRE,
        "faz": "os 6 portoes que derrubam uma subida: token, conta, escrita, pagamento, "
               "pagina e WhatsApp conectado. O de WhatsApp e uma sonda POST em "
               "validate_only, que a Meta confere e NAO cria.",
        "devolve": "PODE SUBIR, ou a lista do que falta. Metade e acao do CLIENTE.",
        "quando": "SEMPRE antes de subir. E o unico jeito de ver o gate de WhatsApp, "
                  "que nenhuma leitura da API revela.",
    },
    {
        "nome": "get",
        "uso": "python -m magicads get <cliente> <caminho> [campo=valor ...]",
        "portao": LIVRE,
        "faz": "GET cru na Graph API com o token do cofre.",
        "devolve": "o JSON da Meta, com segredo filtrado.",
        "quando": "conferir qualquer coisa. Confira por GET /<id>, nunca por listagem: "
                  "sob rate limit a Meta devolve data:[] com HTTP 200, e isso nao e "
                  "'nao tem', e 'nao vejo'.",
    },
    {
        "nome": "post",
        "uso": "python -m magicads post <cliente> <caminho> <campo=valor ...> [--executar]",
        "portao": HUMANO,
        "faz": "POST cru. Sem --executar vai em validate_only: a Meta confere e nao cria.",
        "devolve": "o JSON da Meta.",
        "quando": "o que `subir` nao cobre. ATENCAO: validate_only NAO protege em "
                  "/campaigns -- ali a Meta cria de verdade com ou sem a flag.",
    },
    {
        "nome": "imagem",
        "uso": "python -m magicads imagem <cliente> <act_...> <arquivo>",
        "portao": ESCREVE,
        "faz": "sobe a imagem pra biblioteca da conta.",
        "devolve": "o hash, que vai em `imagem_hash` na receita.",
        "quando": "antes de subir. Nao gasta nada.",
    },
    {
        "nome": "video",
        "uso": "python -m magicads video <cliente> <act_...> <arquivo>",
        "portao": ESCREVE,
        "faz": "sobe o video pra biblioteca da conta.",
        "devolve": "o id do video, que vai em `video_id` na receita.",
        "quando": "antes de subir criativo de video. O id que sai DAQUI e o que serve "
                  "pra publico de visualizacao depois; o id do arquivo no seu disco "
                  "nao existe pra Meta.",
    },
    {
        "nome": "subir",
        "uso": "python -m magicads subir <receita.json> [--executar]",
        "portao": HUMANO,
        "faz": "campanha + conjunto + criativo + anuncio a partir de uma receita. "
               "Sem --executar e ENSAIO: valida, monta e imprime os payloads, e nao "
               "chama a Meta. Com --executar cria tudo PAUSED.",
        "devolve": "no ensaio, os 4 payloads. Executando, os ids conferidos por GET.",
        "quando": "toda subida. O ensaio o agente pode rodar sozinho (nao sai da "
                  "maquina); o --executar e seu.",
    },
    {
        "nome": "pausar",
        "uso": "python -m magicads pausar <cliente> <id>   |   pausar <cliente> --tudo [act_...]",
        "portao": FREIO,
        "faz": "poe PAUSED. Executa direto, sem --executar: freio que pede confirmacao "
               "e freio que nao se usa na hora do aperto. `--tudo` pausa toda campanha "
               "ativa das contas do cliente, e tira a lista da CARTEIRA, nunca de "
               "me/adaccounts.",
        "devolve": "o que pausou, conferido por GET. Sai 1 se algo continuou ativo.",
        "quando": "emergencia. Se a lista vier vazia, desconfie: data:[] com HTTP 200 "
                  "tambem e o que a Meta devolve sob rate limit.",
    },
    {
        "nome": "ativar",
        "uso": "python -m magicads ativar <cliente> <id> --executar",
        "portao": HUMANO,
        "faz": "poe ACTIVE. Exige --executar porque religar queima dinheiro.",
        "devolve": "o estado conferido por GET.",
        "quando": "depois de VOCE revisar. Nao existe `ativar --tudo`, de proposito.",
    },
    {
        "nome": "etl",
        "uso": "python -m magicads etl [--dias N] [--seco] [--so-meta] [--so-google]",
        "portao": LIVRE,
        "faz": "le Meta e Google e grava a serie diaria no SEU banco. Idempotente: a "
               "chave primaria e a chave de idempotencia, entao rodar duas vezes no "
               "mesmo dia nao duplica. Falha nao vira zero.",
        "devolve": "linhas gravadas, FALHAS e contas MUDAS. Sai 1 se houve falha.",
        "quando": "todo dia, no cron. `--seco` mostra e nao escreve.",
    },
    {
        "nome": "relatorio",
        "uso": "python -m magicads relatorio [<cliente>] [--dias N] [--mudas]",
        "portao": LIVRE,
        "faz": "le o que o ETL gravou. Sem argumento, portfolio com delta contra a "
               "janela anterior. Com cliente, ontem contra a media da propria campanha. "
               "--mudas separa conta que EMUDECEU de conta que nunca teve linha.",
        "devolve": "tabelas. `--mudas` sai 1 quando alguma conta emudeceu.",
        "quando": "antes de opinar qualquer coisa. Numero que nao veio daqui e chute.",
    },
]

# O que cada plataforma DEIXA fazer. Esta tabela existe pra o agente nao
# prometer o que nao tem API. Detalhe em aios/fluxos/README.md.
PLATAFORMAS = [
    ("Meta (Facebook)", "subir, medir, pausar", "completo por API",
     "e o que este CLI cobre ponta a ponta"),
    ("Instagram", "subir, medir", "mesma API da Meta",
     "e POSICIONAMENTO, nao canal separado. Sem `instagram_id` na receita o "
     "anuncio roda no IG com o nome da Pagina do Facebook"),
    ("Google Ads", "medir", "leitura no ETL; subida NAO implementada",
     "subir ainda e na interface. O agente monta o plano, voce executa la"),
    ("Google Business (GBP)", "quase nada", "NAO tem API de produto",
     "post e produto sao na mao. Termo novo demora ~2 meses pra aparecer. "
     "O agente que prometer automacao aqui esta mentindo"),
    ("LinkedIn", "nada ainda", "API separada, fora do ETL",
     "e `introspect` diz revoked com token vivo, entao nao confie nele pra "
     "diagnosticar acesso"),
]


def texto():
    linhas = []
    a = linhas.append
    a("=" * 78)
    a("CONTRATO DA FERRAMENTA  ·  magicads")
    a("=" * 78)
    a("")
    a("OS PORTOES -- o que decide se voce roda sozinho ou propoe:")
    for nome, o_que in PORTOES:
        a("  %-8s %s" % (nome, o_que))
    a("")
    a("-" * 78)
    a("COMANDOS")
    a("-" * 78)
    for c in COMANDOS:
        a("")
        a("%s   [%s]" % (c["nome"].upper(), c["portao"]))
        a("  uso      %s" % c["uso"])
        a("  faz      %s" % c["faz"])
        a("  devolve  %s" % c["devolve"])
        a("  quando   %s" % c["quando"])
    a("")
    a("-" * 78)
    a("O QUE CADA PLATAFORMA DEIXA FAZER")
    a("-" * 78)
    for nome, o_que, como, obs in PLATAFORMAS:
        a("")
        a("%-24s %s" % (nome, o_que))
        a("  %s" % como)
        a("  %s" % obs)
    a("")
    a("-" * 78)
    a("Os fluxos (o que fazer, em que ordem) estao em aios/fluxos/.")
    a("Contrato e a lista de ferramentas. Fluxo e o oficio.")
    a("=" * 78)
    return "\n".join(linhas)


def main(argv):
    if "--json" in argv:
        print(json.dumps({
            "portoes": [{"nome": n, "regra": r} for n, r in PORTOES],
            "comandos": COMANDOS,
            "plataformas": [{"plataforma": p, "da_pra": d, "como": c, "obs": o}
                            for p, d, c, o in PLATAFORMAS],
        }, ensure_ascii=False, indent=2))
        return 0
    print(texto())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
