# -*- coding: utf-8 -*-
"""As garantias de seguranca, testadas em vez de prometidas.

    python -m unittest discover -s tests -v

Sem dependencia: unittest da stdlib.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from magicads import cli, comum, etl  # noqa: E402

# De proposito cheio de "x": assim o scripts/scrub.sh continua rigoroso com o
# repo inteiro, em vez de ganhar uma excecao pra pasta de teste (que viraria o
# lugar perfeito pra um token de verdade passar despercebido).
TOKEN_FALSO = "EAAxxxxxxxxxxxxTOKEN-SO-DE-TESTE-1234567890"


class Isolado(unittest.TestCase):
    """Devolve a lista de segredos ao estado anterior: teste que suja estado
    global passa sozinho e falha quando roda junto com os outros."""

    def setUp(self):
        self._segredos = list(comum.SEGREDOS)

    def tearDown(self):
        comum.SEGREDOS[:] = self._segredos


class TokenNaoVaza(Isolado):
    """O jeito classico de vazar token e a mensagem de ERRO, nao o print feliz."""

    def setUp(self):
        Isolado.setUp(self)
        cli.usa(TOKEN_FALSO)

    def tearDown(self):
        cli.TOK_ATUAL[0] = ""
        Isolado.tearDown(self)

    def test_limpa_troca_o_token_no_meio_do_texto(self):
        sujo = "falhou chamando ...&access_token=%s&fields=name" % TOKEN_FALSO
        self.assertNotIn(TOKEN_FALSO, cli.limpa(sujo))
        self.assertIn("<SEGREDO>", cli.limpa(sujo))

    def test_limpa_pega_token_dentro_de_erro_da_meta(self):
        # A Meta ecoa o parametro que voce mandou dentro de `message`.
        er = {"code": 190, "error_subcode": 465,
              "message": "Invalid OAuth access token: %s" % TOKEN_FALSO}
        saida = cli.erro_legivel(er)
        self.assertNotIn(TOKEN_FALSO, saida)
        self.assertIn("subcode=465", saida)

    def test_limpa_nao_estraga_texto_sem_segredo(self):
        self.assertEqual(cli.limpa("tudo certo"), "tudo certo")

    def test_o_filtro_e_um_so(self):
        # O ponto do refactor: token que entrou pelo cofre (cli) tambem some da
        # saida do ETL. Dois filtros separados sao a chance de um ficar pra tras
        # quando a regra mudar.
        self.assertIs(cli.limpa, comum.limpa)
        self.assertIs(etl.diz, comum.diz)
        self.assertNotIn(TOKEN_FALSO, comum.limpa("tok=%s" % TOKEN_FALSO))


class SegredoDeAmbienteNaoVaza(Isolado):
    def test_env_registra_segredo_e_limpa_apaga(self):
        os.environ["MAGICADS_TESTE_SEGREDO"] = "chave-secreta-bem-longa-123456"
        try:
            v = comum.env("MAGICADS_TESTE_SEGREDO")
            self.assertEqual(v, "chave-secreta-bem-longa-123456")
            self.assertNotIn(v, comum.limpa("erro: apikey=%s" % v))
            self.assertIn("<SEGREDO>", comum.limpa("erro: apikey=%s" % v))
        finally:
            del os.environ["MAGICADS_TESTE_SEGREDO"]

    def test_valor_curto_nao_entra_na_lista(self):
        # Registrar valor curto faria limpa() picotar texto legitimo.
        os.environ["MAGICADS_TESTE_CURTO"] = "v25.0"
        try:
            comum.env("MAGICADS_TESTE_CURTO")
            self.assertEqual(comum.limpa("rodando na v25.0"), "rodando na v25.0")
        finally:
            del os.environ["MAGICADS_TESTE_CURTO"]

    def test_url_do_supabase_nao_e_segredo(self):
        # Se a URL entrasse como segredo, toda mensagem de erro viraria
        # "<SEGREDO>/rest/v1/..." e ninguem descobriria o que quebrou.
        os.environ["MAGICADS_TESTE_URL"] = "https://exemplo.supabase.co"
        try:
            v = comum.env("MAGICADS_TESTE_URL", segredo=False)
            self.assertIn(v, comum.limpa("falhou em %s/rest/v1/metricas" % v))
        finally:
            del os.environ["MAGICADS_TESTE_URL"]


class PostValidaAntesDeCriar(Isolado):
    """O padrao seguro tem que ser o padrao, nao a boa intencao de quem digita."""

    def setUp(self):
        Isolado.setUp(self)
        self.capturado = {}
        self._chamada = cli.chamada
        self._token = cli.token

        def falsa(metodo, caminho, campos):
            self.capturado = {"metodo": metodo, "caminho": caminho, "campos": dict(campos)}
            return {"id": "120000000000000000"}, None

        cli.chamada = falsa
        cli.token = lambda c: ("cliente", TOKEN_FALSO)

    def tearDown(self):
        cli.chamada = self._chamada
        cli.token = self._token
        Isolado.tearDown(self)

    def test_sem_executar_vai_em_validate_only(self):
        cli.cmd_chamada("POST", ["cliente", "act_000000000000000/adsets", "name=teste"])
        self.assertEqual(
            json.loads(self.capturado["campos"]["execution_options"]), ["validate_only"])

    def test_com_executar_cria_de_verdade(self):
        cli.cmd_chamada("POST",
                        ["cliente", "act_000000000000000/adsets", "name=teste", "--executar"])
        self.assertNotIn("execution_options", self.capturado["campos"])

    def test_campanha_sem_executar_e_RECUSADA(self):
        """Aqui nao da pra "avisar e mandar".

        `validate_only` nao protege em /campaigns: a Meta cria de verdade, com a
        flag ou sem ela. A versao anterior imprimia "a Meta vai conferir e NAO
        criar", avisava logo abaixo que ali era mentira, e mandava assim mesmo.
        Quem leu a primeira linha ficava com campanha de verdade na conta do
        cliente. Divulgar nao e controlar: tem que recusar."""
        with self.assertRaises(SystemExit):
            cli.cmd_chamada("POST", ["cliente", "act_000000000000000/campaigns",
                                     "name=teste"])
        self.assertEqual(self.capturado, {}, "recusou e mandou assim mesmo")

    def test_campanha_com_executar_passa(self):
        cli.cmd_chamada("POST", ["cliente", "act_000000000000000/campaigns",
                                 "name=teste", "--executar"])
        self.assertEqual(self.capturado["caminho"], "act_000000000000000/campaigns")
        self.assertNotIn("execution_options", self.capturado["campos"])

    def test_get_nunca_ganha_validate_only(self):
        cli.cmd_chamada("GET", ["cliente", "me/adaccounts", "fields=name"])
        self.assertNotIn("execution_options", self.capturado["campos"])


class ApagarNaoPodeMentir(Isolado):
    """`{"success": true}` nao e prova de que apagou.

    O `subir` imprimia, quando falhava no meio, um comando de limpeza que NAO
    limpava: `post <id> _method=DELETE`. A Graph API aceita o POST, responde
    `success: true` e deixa o objeto vivo (medido em 14/09/2026, com 8s de espera
    e dois GET). O estrago e pior que nao ter comando nenhum: voce risca o orfao
    da lista e ele fica la, na conta do cliente.
    """

    def setUp(self):
        Isolado.setUp(self)
        self.visto = []
        self._chamada = cli.chamada
        self._token = cli.token

        def falsa(metodo, caminho, campos):
            self.visto.append((metodo, caminho))
            if metodo == "GET":
                # antes do DELETE esta vivo; depois, apagado.
                morto = any(m == "DELETE" for m, _ in self.visto)
                return {"id": caminho, "name": "campanha",
                        "status": "DELETED" if morto else "PAUSED"}, None
            return {"success": True}, None

        cli.chamada = falsa
        cli.token = lambda c: ("cliente", TOKEN_FALSO)

    def tearDown(self):
        cli.chamada = self._chamada
        cli.token = self._token
        Isolado.tearDown(self)

    def test_sem_executar_nao_apaga(self):
        cli.cmd_remover(["cliente", "120000000000000000"])
        self.assertNotIn("DELETE", [m for m, _ in self.visto])

    def test_com_executar_usa_delete_de_verdade(self):
        cli.cmd_remover(["cliente", "120000000000000000", "--executar"])
        self.assertIn("DELETE", [m for m, _ in self.visto])

    def test_confere_relendo_o_objeto(self):
        # Um GET antes (pra mostrar o que vai morrer) e um DEPOIS (a prova).
        cli.cmd_remover(["cliente", "120000000000000000", "--executar"])
        self.assertEqual([m for m, _ in self.visto], ["GET", "DELETE", "GET"])

    def test_sai_1_se_o_objeto_sobreviveu(self):
        # A Meta dizendo `success` com o objeto de pe: e exatamente o caso que
        # existia, e ele nao pode passar calado.
        cli.chamada = lambda metodo, caminho, campos: (
            ({"id": caminho, "name": "c", "status": "PAUSED"}, None) if metodo == "GET"
            else ({"success": True}, None))
        with self.assertRaises(SystemExit) as e:
            cli.cmd_remover(["cliente", "120000000000000000", "--executar"])
        self.assertEqual(e.exception.code, 1)

    def test_a_limpeza_do_subir_aponta_pro_comando_que_funciona(self):
        from magicads import subir
        saida = []
        _diz = subir.diz
        subir.diz = lambda *a: saida.append(" ".join(str(x) for x in a))
        try:
            subir.limpeza([("campanha", "120000000000000001"),
                           ("conjunto", "120000000000000002")])
        finally:
            subir.diz = _diz
        texto = "\n".join(saida)
        self.assertNotIn("_method=DELETE", texto)
        self.assertIn("magicads remover", texto)
        # do mais novo pro mais velho: apagar a campanha primeiro deixa o resto orfao.
        # (so a parte dos comandos: a lista de cima esta na ordem em que criou)
        ordens = texto[texto.index("Pra remover"):]
        self.assertLess(ordens.index("120000000000000002"), ordens.index("120000000000000001"))


class OVereditoDoDiag(unittest.TestCase):
    """O `diag` e o PRIMEIRO comando que o README manda rodar. Se ele responde
    errado, a conclusao natural de quem chegou agora e "a ferramenta esta
    quebrada", e nao "falta uma coisa na minha conta".

    O portao de WhatsApp so vale pra CTWA, entao ele NAO pode reprovar quem vai
    subir campanha de site. E a sonda dele precisa de uma campanha ja existente
    pra se pendurar, o que conta nova nunca tem.
    """

    def texto(self, prontas, paginas, zap):
        return chr(10).join(cli.veredito(prontas, paginas, zap))

    def test_conta_nova_sem_campanha_pode_subir(self):
        # Tudo OK nos outros portoes e a sonda sem onde rodar: isso e PODE SUBIR.
        s = self.texto(["act_1"], [{"id": "1"}], None)
        self.assertIn("PODE SUBIR", s)
        self.assertIn("NAO TESTADO", s)

    def test_loja_sem_whatsapp_pode_subir(self):
        # Quem vende no site nao precisa de WhatsApp na Pagina.
        s = self.texto(["act_1"], [{"id": "1"}], False)
        self.assertIn("PODE SUBIR", s)
        self.assertIn("MENOS CTWA", s)

    def test_sem_conta_pronta_nao_sobe(self):
        s = self.texto([], [{"id": "1"}], True)
        self.assertIn("NAO SUBA AINDA", s)
        self.assertNotIn("PODE SUBIR", s)

    def test_sem_pagina_nao_sobe(self):
        s = self.texto(["act_1"], [], True)
        self.assertIn("NAO SUBA AINDA", s)

    def test_nunca_manda_resolver_o_que_nao_esta_faltando(self):
        # O caso que existia: cinco portoes OK, nenhuma linha dizendo FALTA, e
        # mesmo assim "resolva o que esta FALTA acima".
        for zap in (None, False, True):
            s = self.texto(["act_1"], [{"id": "1"}], zap)
            self.assertNotIn("resolva o que esta FALTA", s)

class Cofre(Isolado):
    def setUp(self):
        Isolado.setUp(self)
        self.tmp = tempfile.mkdtemp()
        self._cofre = cli.COFRE
        cli.COFRE = Path(self.tmp)

    def tearDown(self):
        cli.COFRE = self._cofre
        Isolado.tearDown(self)

    def escreve(self, nome, conteudo):
        p = Path(self.tmp) / nome
        p.write_text(conteudo, encoding="utf-8")
        return p

    def test_acha_por_prefixo(self):
        self.escreve("acmepneus.env", "ACME_META_TOKEN=%s\n" % TOKEN_FALSO)
        nome, tok = cli.token("acme")
        self.assertEqual(nome, "acmepneus")
        self.assertEqual(tok, TOKEN_FALSO)

    def test_token_do_cofre_ja_sai_protegido(self):
        # Quem chama `token()` nao precisa lembrar de registrar o segredo, e por
        # isso nao tem como esquecer.
        self.escreve("acme.env", "ACME_META_TOKEN=%s\n" % TOKEN_FALSO)
        cli.token("acme")
        self.assertIn("<SEGREDO>", comum.limpa("vazou? %s" % TOKEN_FALSO))

    def test_prefixo_ambiguo_para_em_vez_de_chutar(self):
        # Escolher sozinho entre dois clientes e como subir na conta errada.
        self.escreve("acme-um.env", "A_META_TOKEN=%s\n" % TOKEN_FALSO)
        self.escreve("acme-dois.env", "B_META_TOKEN=%s\n" % TOKEN_FALSO)
        with self.assertRaises(SystemExit):
            cli.token("acme")

    def test_ignora_comentario_e_exige_sufixo_certo(self):
        self.escreve("acme.env", "# comentario\nOUTRA_COISA=xxx\nACME_META_TOKEN=%s\n"
                     % TOKEN_FALSO)
        _, tok = cli.token("acme")
        self.assertEqual(tok, TOKEN_FALSO)

    def test_arquivo_sem_token_falha_explicito(self):
        self.escreve("acme.env", "ACME_APP_ID=123\n")
        with self.assertRaises(SystemExit):
            cli.token("acme")


class FreioGeral(Isolado):
    """`pausar --tudo` mexe em varias campanhas de uma vez. O que nao pode
    acontecer e ele encostar em conta que nao e do cliente."""

    def setUp(self):
        Isolado.setUp(self)
        self.chamadas = []
        self._chamada, self._token = cli.chamada, cli.token
        self.ativas = {}          # conta -> [campanhas]
        self.efetivo = {}         # id -> effective_status depois do POST

        def falsa(metodo, caminho, campos):
            self.chamadas.append((metodo, caminho, dict(campos)))
            if metodo == "GET" and caminho.endswith("/campaigns"):
                conta = caminho.split("/")[0]
                return {"data": self.ativas.get(conta, [])}, None
            if metodo == "GET":
                return {"id": caminho,
                        "effective_status": self.efetivo.get(caminho, "PAUSED")}, None
            return {"success": True}, None

        cli.chamada = falsa
        cli.token = lambda c: ("acme", TOKEN_FALSO)

    def tearDown(self):
        cli.chamada, cli.token = self._chamada, self._token
        Isolado.tearDown(self)

    def roda(self, argv):
        import io
        antigo, buf = sys.stdout, io.StringIO()
        sys.stdout = buf
        try:
            codigo = cli.cmd_freio(argv)
        finally:
            sys.stdout = antigo
        return codigo, buf.getvalue()

    def test_sem_carteira_e_sem_act_explicito_ele_para(self):
        # O contrario disto seria derivar de me/adaccounts e pausar a campanha
        # do cliente vizinho.
        os.environ.pop("MAGICADS_SUPABASE_URL", None)
        os.environ.pop("DATABASE_URL", None)
        with self.assertRaises(SystemExit):
            self.roda(["acme"])
        self.assertFalse([c for c in self.chamadas if "adaccounts" in c[1]])

    def test_act_explicito_e_respeitado(self):
        self.ativas["act_000000000000002"] = [{"id": "120000000000000001", "name": "[C01]"}]
        codigo, texto = self.roda(["acme", "act_000000000000002"])
        self.assertEqual(codigo, 0)
        self.assertIn("pausada 120000000000000001", texto)
        posts = [c for c in self.chamadas if c[0] == "POST"]
        self.assertEqual(posts[0][2]["status"], "PAUSED")

    def test_lista_vazia_nao_e_declarada_como_tudo_certo(self):
        # data:[] com HTTP 200 e o que a Meta devolve sob rate limit. Dizer
        # "nada ativo" aqui e mandar a pessoa dormir com a conta gastando.
        codigo, texto = self.roda(["acme", "act_000000000000002"])
        self.assertEqual(codigo, 0)
        self.assertIn("rate limit", texto)

    def test_pos_confere_por_get_e_denuncia_quem_nao_parou(self):
        self.ativas["act_000000000000002"] = [{"id": "120000000000000001", "name": "[C01]"}]
        self.efetivo["120000000000000001"] = "ACTIVE"    # a Meta aceitou e nao aplicou
        codigo, texto = self.roda(["acme", "act_000000000000002"])
        self.assertEqual(codigo, 1)
        self.assertIn("AINDA ATIVAS", texto)

    def test_ativar_tudo_nao_existe(self):
        with self.assertRaises(SystemExit):
            cli.cmd_status(["acme", "--tudo"], "ACTIVE")


class ContagemDeResultado(unittest.TestCase):
    def test_conta_conversa_e_conversao(self):
        actions = [
            {"action_type": etl.MSG_INICIADA, "value": "10"},
            {"action_type": "lead", "value": "3"},
            {"action_type": "offsite_conversion.fb_pixel_purchase", "value": "2"},
        ]
        self.assertEqual(etl.conta_resultados(actions), (10, 5))

    def test_depth_5_nao_conta_como_gente(self):
        # depth_5 conta MENSAGEM ENVIADA, e por isso consegue ser maior que o
        # numero de conversas iniciadas. Se entrasse, inflaria o resultado.
        actions = [
            {"action_type": etl.MSG_INICIADA, "value": "10"},
            {"action_type": "onsite_conversion.messaging_user_depth_5_message_send",
             "value": "292"},
        ]
        self.assertEqual(etl.conta_resultados(actions), (10, 0))

    def test_valor_lixo_nao_derruba_a_rodada(self):
        actions = [{"action_type": "lead", "value": "nao-numero"},
                   {"action_type": "lead", "value": "2"}]
        self.assertEqual(etl.conta_resultados(actions), (0, 2))

    def test_sem_actions(self):
        self.assertEqual(etl.conta_resultados(None), (0, 0))

    def test_o_mesmo_lead_em_dois_action_types_conta_uma_vez(self):
        # Visto ao vivo em 21/08/2026 numa conta real: a mesma linha trazia
        # `lead=1` e `offsite_conversion.fb_pixel_lead=1`, que sao o MESMO lead.
        # Somar inflaria o resultado e dividiria o custo pela metade -- o jeito
        # mais caro de errar, porque faz escalar o que nao estava funcionando.
        actions = [{"action_type": "lead", "value": "1"},
                   {"action_type": "offsite_conversion.fb_pixel_lead", "value": "1"}]
        self.assertEqual(etl.conta_resultados(actions), (0, 1))

    def test_sem_o_agregado_o_especifico_vale(self):
        # Conta que so tem pixel nao pode ficar com zero resultado.
        actions = [{"action_type": "offsite_conversion.fb_pixel_lead", "value": "3"}]
        self.assertEqual(etl.conta_resultados(actions), (0, 3))

    def test_familias_diferentes_somam(self):
        # Lead e compra sao coisas distintas: aqui somar e o certo.
        actions = [{"action_type": "lead", "value": "2"},
                   {"action_type": "purchase", "value": "5"}]
        self.assertEqual(etl.conta_resultados(actions), (0, 7))

    def test_compra_agregada_manda_sobre_a_do_pixel(self):
        actions = [{"action_type": "purchase", "value": "4"},
                   {"action_type": "offsite_conversion.fb_pixel_purchase", "value": "4"}]
        self.assertEqual(etl.conta_resultados(actions), (0, 4))

    def test_lead_do_formulario_nao_soma_com_o_total(self):
        actions = [{"action_type": "lead", "value": "6"},
                   {"action_type": "onsite_conversion.lead_grouped", "value": "6"}]
        self.assertEqual(etl.conta_resultados(actions), (0, 6))


class ReadicionarContaTemQueReativar(unittest.TestCase):
    """Nao existe `--readicionar`. Entao repetir o `conta` E o jeito obvio de
    desfazer um `--remover`, e o jeito obvio nao pode falhar calado.

    O upsert atualizava nome e cliente e deixava `ativo` como estava: falso. O
    CLI imprimia `meta act_123 -> acme`, que e mensagem de sucesso, e a conta
    seguia fora da carteira e fora do ETL. As DUAS pernas tinham o bug."""

    def test_a_perna_do_postgrest_manda_ativo(self):
        from magicads.banco import Banco
        import inspect
        fonte = inspect.getsource(Banco.conta_salva)
        self.assertIn('"ativo": True', fonte)

    def test_a_perna_do_sql_manda_ativo(self):
        from magicads.banco import Banco
        import inspect
        fonte = inspect.getsource(Banco.conta_salva)
        self.assertIn("ativo = true", fonte,
                      "o do update set nao reativa a conta")


class MetricaSemCriativoNaoDerrubaAGravacao(unittest.TestCase):
    """`criativo_id` faz parte da chave primaria, e o schema o declara
    `not null default ''` porque null quebra unique (no Postgres null nunca e
    igual a null, entao a mesma linha entraria infinitas vezes).

    Mas DEFAULT so vale quando a coluna e OMITIDA. Mandar null explicito estoura
    23502, e um coletor novo que esqueca a chave derruba a gravacao DEPOIS da
    coleta inteira ter rodado."""

    def test_none_vira_string_vazia(self):
        from magicads.banco import Banco
        saida = Banco._normaliza({"canal": "meta", "criativo_id": None})
        self.assertEqual(saida["criativo_id"], "")

    def test_chave_ausente_ganha_padrao(self):
        from magicads.banco import Banco
        saida = Banco._normaliza({"canal": "linkedin", "campanha": None})
        self.assertEqual(saida["criativo_id"], "")
        self.assertEqual(saida["campanha"], "(sem nome)")
        for m in ("investimento", "impressoes", "cliques", "conversas", "conversoes"):
            self.assertEqual(saida[m], 0)

    def test_valor_de_verdade_nao_e_sobrescrito(self):
        from magicads.banco import Banco
        # normalizar nao pode virar zerar: 0 legitimo e None sao coisas
        # diferentes, e trocar um pelo outro falsifica relatorio.
        saida = Banco._normaliza({"criativo_id": "120xyz", "investimento": 12.5,
                                  "cliques": 0})
        self.assertEqual(saida["criativo_id"], "120xyz")
        self.assertEqual(saida["investimento"], 12.5)
        self.assertEqual(saida["cliques"], 0)

    def test_nao_muda_o_dicionario_de_quem_chamou(self):
        from magicads.banco import Banco
        original = {"canal": "meta"}
        Banco._normaliza(original)
        self.assertNotIn("criativo_id", original)


class FiltroDoPostgrestNaoAceitaValorCru(unittest.TestCase):
    """As duas pernas do banco tinham pesos diferentes.

    psycopg2 passa argumento por fora do SQL; o PostgREST montava a query com
    `%s` cru. E o modo de falhar e traicoeiro: um `&` no valor nao da erro,
    vira OUTRO filtro, e a resposta volta certinha respondendo outra pergunta.
    """

    def test_ampersand_nao_vira_outro_filtro(self):
        from magicads.banco import Banco
        sujo = "acme&limit=1"
        self.assertNotIn('&', Banco._f(sujo))
        self.assertEqual(Banco._f(sujo), "acme%26limit%3D1")

    def test_virgula_nao_passa(self):
        from magicads.banco import Banco
        # a virgula separa argumento em `in.(a,b)` e separa condicao em
        # `or=(...)`, entao ela muda o SENTIDO do filtro.
        self.assertEqual(Banco._f("a,b"), "a%2Cb")

    def test_ponto_passa_de_proposito(self):
        from magicads.banco import Banco
        # so o PRIMEIRO ponto separa operador de valor (`eq.`); os seguintes
        # fazem parte do valor. Escapar seria escapar demais, e escapar demais
        # quebra igual: o slug para de casar com o que ja esta gravado.
        self.assertEqual(Banco._f("acme.com.br"), "acme.com.br")

    def test_slug_normal_continua_legivel(self):
        from magicads.banco import Banco
        # escapar demais tambem quebra: se o slug comum mudar, todo relatorio
        # existente para de casar.
        self.assertEqual(Banco._f("acme-pneus"), "acme-pneus")
        self.assertEqual(Banco._f("2026-09-14"), "2026-09-14")


class WorkflowNaoPedeEscrita(unittest.TestCase):
    """GITHUB_TOKEN com permissao padrao pode nascer com write. Este workflow
    so le, entao declara isso -- e o teste existe pra que nao volte calado."""

    def test_permissions_contents_read(self):
        yml = RAIZ / ".github" / "workflows" / "provas.yml"
        texto = yml.read_text(encoding="utf-8")
        self.assertIn("permissions:", texto)
        self.assertIn("contents: read", texto)
        self.assertNotIn("contents: write", texto)

    def test_varredura_de_historico_nao_roda_em_clone_raso(self):
        """O job que varre o historico PRECISA de fetch-depth: 0.

        O checkout padrao do Actions traz um commit so. Sem essa linha o job
        passaria verde tendo lido a arvore de hoje e nenhum historico, que e
        exatamente o carimbo falso que a ferramenta existe pra nao dar."""
        yml = RAIZ / ".github" / "workflows" / "provas.yml"
        texto = yml.read_text(encoding="utf-8")
        self.assertIn("historico.sh", texto)
        self.assertIn("fetch-depth: 0", texto)


class OModeloNaoPodeReprovarOProprioRepo(unittest.TestCase):
    """O passo 0 do README manda copiar o modelo. Se o modelo vier com nome
    ativo, o primeiro `./scripts/scrub.sh` do clone novo reprova -- e o que ele
    reprova e a DOCUMENTACAO do proprio repo ("Acme Pneus" mora no README, no
    SECURITY e no cli.py). Alarme falso no minuto um e a forma mais rapida de
    alguem desinstalar a trava mentalmente."""

    def test_o_modelo_vem_sem_nome_ativo(self):
        modelo = RAIZ / ".scrub-clientes.local.exemplo"
        vivas = [l for l in modelo.read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.strip().startswith("#")]
        self.assertEqual(vivas, [],
                         "o modelo tem nome ativo: %r" % (vivas,))

    def test_o_modelo_ainda_ensina_o_formato(self):
        # comentar tudo nao pode virar arquivo vazio: quem copia precisa ver
        # como se escreve uma linha.
        texto = (RAIZ / ".scrub-clientes.local.exemplo").read_text(encoding="utf-8")
        self.assertIn("# Acme Pneus", texto)
        self.assertIn("um nome por linha", texto.lower())


class AsRegrasMoramNumLugarSo(unittest.TestCase):
    """Duas listas de regras em dois scripts garantem que uma hora uma regra
    entra numa e nao na outra -- e isso falha calado."""

    # os TRES: scrub (arvore), historico (todo commit) e o hook (o que esta
    # indo agora). O hook ja teve a propria listinha de regex.
    FERRAMENTAS = ("scripts/scrub.sh", "scripts/historico.sh",
                   "scripts/hooks/pre-push")

    def test_as_tres_ferramentas_usam_o_mesmo_regras_sh(self):
        for nome in self.FERRAMENTAS:
            texto = (RAIZ / nome).read_text(encoding="utf-8")
            self.assertIn("regras.sh", texto, "%s nao sourceia as regras" % nome)

    def test_nenhuma_delas_redefine_as_regras(self):
        for nome in self.FERRAMENTAS:
            texto = (RAIZ / nome).read_text(encoding="utf-8")
            vivas = [l for l in texto.splitlines()
                     if l.strip() and not l.strip().startswith("#")]
            cria = [l for l in vivas if "REGRAS=(" in l and "REGRAS=()" not in l]
            self.assertFalse(cria, "%s monta a propria lista de regras" % nome)

    def test_permitido_nao_libera_token_por_conter_sequencia_de_manual(self):
        """`*1234567890*` solto liberava um token de 40 caracteres que por
        acaso contivesse a sequencia. Descoberto plantando a isca
        `EAA...1234567890`: a varredura disse "LIMPO" sobre um token real."""
        regras = (RAIZ / "scripts" / "regras.sh").read_text(encoding="utf-8")
        # so as linhas VIVAS: o comentario que explica a remocao cita o padrao
        # antigo, e um teste que le comentario testa prosa, nao comportamento.
        vivas = [l for l in regras.splitlines()
                 if l.strip() and not l.strip().startswith("#")]
        self.assertFalse([l for l in vivas if "*1234567890*" in l],
                         "o padrao solto voltou pra dentro do permitido()")
        self.assertTrue([l for l in vivas if "1234567890|0123456789)" in l],
                        "a versao ancorada sumiu; o placeholder vai dar alarme falso")


class OExemploDoRepoTemQuePassarNoProprioScrub(unittest.TestCase):
    """O `conta` das receitas e placeholder, e placeholder que o scrub reprova
    e alarme falso no minuto um -- que e a forma mais rapida de alguem
    desinstalar a trava mentalmente.

    Aconteceu de verdade: a receita do Google entrou com `000-000-0000`, e o
    `*00000000*` do permitido() nao alcanca, porque com hifen nao ha oito zeros
    seguidos. So apareceu rodando o scrub na mao. Agora aparece na CI.
    """

    def permitidos(self):
        """Os globs do `case` do permitido(), lidos do regras.sh."""
        import re
        texto = (RAIZ / "scripts" / "regras.sh").read_text(encoding="utf-8")
        corpo = texto.split("permitido() {", 1)[1].split("esac", 1)[0]
        globs = []
        for linha in corpo.splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            m = re.match(r"^(.+?)\)\s+return 0 ;;$", linha)
            if m:
                globs.extend(g.strip() for g in m.group(1).split("|"))
        self.assertTrue(globs, "nao consegui ler o permitido() do regras.sh")
        return globs

    def test_toda_conta_de_receita_e_placeholder_declarado(self):
        import fnmatch
        globs = self.permitidos()
        receitas = sorted((RAIZ / "receitas").glob("*.json"))
        self.assertTrue(receitas)
        for caminho in receitas:
            conta = json.loads(caminho.read_text(encoding="utf-8")).get("conta")
            if not conta:
                continue
            self.assertTrue(
                any(fnmatch.fnmatchcase(conta, g) for g in globs),
                "%s usa %r, que o scrub vai reprovar no primeiro clone"
                % (caminho.name, conta))


class AVarreduraDeHistoricoNaoPodeAcusarHashDeArvore(unittest.TestCase):
    """`git rev-list --objects --all` devolve TREE junto com blob, e o conteudo
    de uma tree e a lista de SHAs dos filhos. SHA e hexadecimal: um que comece
    com "eaa" casa com a regra do token da Meta, e a varredura acusa segredo
    onde ha o hash de um diretorio -- com a origem saindo como `magicads`, que
    nem e um arquivo.

    Falso positivo em ferramenta de seguranca nao e ruido: e o comeco do habito
    de ignorar o alarme."""

    def test_a_varredura_filtra_por_tipo_de_objeto(self):
        texto = (RAIZ / "scripts" / "historico.sh").read_text(encoding="utf-8")
        vivas = "\n".join(l for l in texto.splitlines()
                          if l.strip() and not l.strip().startswith("#"))
        self.assertIn("objecttype", vivas,
                      "a varredura voltou a ler tree como se fosse arquivo")
        self.assertIn('"blob"', vivas)


if __name__ == "__main__":
    unittest.main()
