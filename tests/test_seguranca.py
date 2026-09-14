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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from magicads import cli, etl  # noqa: E402

# De proposito cheio de "x": assim o scripts/scrub.sh continua rigoroso com o
# repo inteiro, em vez de ganhar uma excecao pra pasta de teste (que viraria o
# lugar perfeito pra um token de verdade passar despercebido).
TOKEN_FALSO = "EAAxxxxxxxxxxxxTOKEN-SO-DE-TESTE-1234567890"


class TokenNaoVaza(unittest.TestCase):
    """O jeito classico de vazar token e a mensagem de ERRO, nao o print feliz."""

    def setUp(self):
        cli.TOK_ATUAL[0] = TOKEN_FALSO

    def tearDown(self):
        cli.TOK_ATUAL[0] = ""

    def test_limpa_troca_o_token_no_meio_do_texto(self):
        sujo = "falhou chamando ...&access_token=%s&fields=name" % TOKEN_FALSO
        self.assertNotIn(TOKEN_FALSO, cli.limpa(sujo))
        self.assertIn("<TOKEN>", cli.limpa(sujo))

    def test_limpa_pega_token_dentro_de_erro_da_meta(self):
        # A Meta ecoa o parametro que voce mandou dentro de `message`.
        er = {"code": 190, "error_subcode": 465,
              "message": "Invalid OAuth access token: %s" % TOKEN_FALSO}
        saida = cli.erro_legivel(er)
        self.assertNotIn(TOKEN_FALSO, saida)
        self.assertIn("subcode=465", saida)

    def test_limpa_nao_estraga_texto_sem_segredo(self):
        self.assertEqual(cli.limpa("tudo certo"), "tudo certo")


class SegredoDoEtlNaoVaza(unittest.TestCase):
    def setUp(self):
        self._antes = list(etl.SEGREDOS)

    def tearDown(self):
        etl.SEGREDOS[:] = self._antes

    def test_env_registra_segredo_e_limpa_apaga(self):
        os.environ["MAGICADS_TESTE_SEGREDO"] = "chave-secreta-bem-longa-123456"
        try:
            v = etl.env("MAGICADS_TESTE_SEGREDO")
            self.assertEqual(v, "chave-secreta-bem-longa-123456")
            self.assertNotIn(v, etl.limpa("erro: apikey=%s" % v))
            self.assertIn("<SEGREDO>", etl.limpa("erro: apikey=%s" % v))
        finally:
            del os.environ["MAGICADS_TESTE_SEGREDO"]

    def test_valor_curto_nao_entra_na_lista(self):
        # Registrar valor curto faria limpa() picotar texto legitimo.
        os.environ["MAGICADS_TESTE_CURTO"] = "v25.0"
        try:
            etl.env("MAGICADS_TESTE_CURTO")
            self.assertEqual(etl.limpa("rodando na v25.0"), "rodando na v25.0")
        finally:
            del os.environ["MAGICADS_TESTE_CURTO"]


class PostValidaAntesDeCriar(unittest.TestCase):
    """O padrao seguro tem que ser o padrao, nao a boa intencao de quem digita."""

    def setUp(self):
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

    def test_sem_executar_vai_em_validate_only(self):
        cli.cmd_chamada("POST", ["cliente", "act_000000000000000/adsets", "name=teste"])
        self.assertEqual(
            json.loads(self.capturado["campos"]["execution_options"]), ["validate_only"])

    def test_com_executar_cria_de_verdade(self):
        cli.cmd_chamada("POST",
                        ["cliente", "act_000000000000000/adsets", "name=teste", "--executar"])
        self.assertNotIn("execution_options", self.capturado["campos"])

    def test_get_nunca_ganha_validate_only(self):
        cli.cmd_chamada("GET", ["cliente", "me/adaccounts", "fields=name"])
        self.assertNotIn("execution_options", self.capturado["campos"])


class Cofre(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._cofre = cli.COFRE
        cli.COFRE = Path(self.tmp)

    def tearDown(self):
        cli.COFRE = self._cofre

    def escreve(self, nome, conteudo):
        p = Path(self.tmp) / nome
        p.write_text(conteudo, encoding="utf-8")
        return p

    def test_acha_por_prefixo(self):
        self.escreve("acmepneus.env", "ACME_META_TOKEN=%s\n" % TOKEN_FALSO)
        nome, tok = cli.token("acme")
        self.assertEqual(nome, "acmepneus")
        self.assertEqual(tok, TOKEN_FALSO)

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


if __name__ == "__main__":
    unittest.main()
