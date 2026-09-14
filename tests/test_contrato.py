# -*- coding: utf-8 -*-
"""O contrato nao pode divergir do CLI.

Contrato que descreve comando inexistente e pior que contrato nenhum: o agente
le, confia, roda, erra, e a partir dali passa a desconfiar tambem do que estava
certo. Estes testes existem pra que adicionar comando sem descrever (ou o
contrario) quebre a build, em vez de quebrar a sessao de alguem.
"""
import ast
import io
import re
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from magicads import contrato  # noqa: E402


def comandos_do_cli():
    """Extrai o despacho de `main()` lendo o fonte.

    De proposito le o ARQUIVO em vez de importar e inspecionar: o despacho e uma
    cadeia de `elif`, nao uma tabela, e um teste que so olhasse uma tabela
    passaria feliz enquanto o `elif` de verdade dizia outra coisa.
    """
    with io.open(RAIZ / "magicads" / "cli.py", encoding="utf-8") as fh:
        fonte = fh.read()
    corpo = None
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.FunctionDef) and no.name == "main":
            corpo = ast.get_source_segment(fonte, no)
    assert corpo, "nao achei main() em cli.py"
    # `-h`, `--help` e `help` nao sao operacao, sao cortesia: ficam de fora.
    return set(re.findall(r'c == "([a-z]+)"', corpo)) - {"help"}


class ContratoBateComOCLI(unittest.TestCase):
    def setUp(self):
        self.descritos = {c["nome"] for c in contrato.COMANDOS}
        self.reais = comandos_do_cli()

    def test_todo_comando_do_cli_esta_descrito(self):
        faltando = self.reais - self.descritos
        self.assertFalse(faltando, "comandos sem contrato: %s" % sorted(faltando))

    def test_todo_comando_descrito_existe_no_cli(self):
        sobrando = self.descritos - self.reais
        self.assertFalse(sobrando, "contrato descreve o que nao existe: %s" % sorted(sobrando))


class CadaComandoDizOEssencial(unittest.TestCase):
    def test_campos_obrigatorios(self):
        for c in contrato.COMANDOS:
            for campo in ("nome", "uso", "portao", "faz", "devolve", "quando"):
                self.assertTrue(c.get(campo), "%s sem `%s`" % (c.get("nome"), campo))

    def test_portao_e_um_dos_quatro(self):
        validos = {n for n, _ in contrato.PORTOES}
        for c in contrato.COMANDOS:
            self.assertIn(c["portao"], validos, c["nome"])

    def test_o_uso_comeca_com_o_proprio_nome(self):
        # O agente copia a linha de `uso`. Se ela nao bater com o comando, ele
        # cola algo que nao roda.
        for c in contrato.COMANDOS:
            self.assertIn("magicads %s" % c["nome"], c["uso"], c["nome"])


class OQueGastaDinheiroEstaMarcado(unittest.TestCase):
    """A parte do contrato que importa de verdade: se um comando que gasta
    estiver marcado como LIVRE, o agente vai rodar sozinho."""

    def portao(self, nome):
        return [c for c in contrato.COMANDOS if c["nome"] == nome][0]["portao"]

    def test_ativar_e_humano(self):
        self.assertEqual(self.portao("ativar"), contrato.HUMANO)

    def test_subir_e_humano(self):
        self.assertEqual(self.portao("subir"), contrato.HUMANO)

    def test_post_cru_e_humano(self):
        self.assertEqual(self.portao("post"), contrato.HUMANO)

    def test_pausar_e_freio_e_nao_humano(self):
        # Se `pausar` virasse HUMANO, o agente pediria autorizacao pra pisar no
        # freio -- que e exatamente quando ninguem esta lendo mensagem.
        self.assertEqual(self.portao("pausar"), contrato.FREIO)

    def test_leitura_e_livre(self):
        for nome in ("get", "diag", "relatorio", "clientes", "etl", "contrato", "init"):
            self.assertEqual(self.portao(nome), contrato.LIVRE, nome)


class MatrizDePlataformaEHonesta(unittest.TestCase):
    def test_gbp_nao_promete_api(self):
        # O agente que promete automacao de GBP esta mentindo, e mentira de
        # agente vira promessa pro cliente.
        linha = [p for p in contrato.PLATAFORMAS if "GBP" in p[0]][0]
        self.assertIn("NAO tem API", linha[2])

    def test_instagram_e_posicionamento_e_nao_canal(self):
        linha = [p for p in contrato.PLATAFORMAS if p[0] == "Instagram"][0]
        self.assertIn("POSICIONAMENTO", " ".join(linha).upper())

    def test_google_ads_nao_promete_subida(self):
        linha = [p for p in contrato.PLATAFORMAS if "Google Ads" in p[0]][0]
        self.assertIn("NAO implementada", linha[2])


class SaidaNaoQuebra(unittest.TestCase):
    def test_texto_sai_inteiro(self):
        t = contrato.texto()
        for c in contrato.COMANDOS:
            self.assertIn(c["nome"].upper(), t)

    def test_json_e_json(self):
        import json
        buf, antigo = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            contrato.main(["--json"])
        finally:
            sys.stdout = antigo
        d = json.loads(buf.getvalue())
        self.assertEqual(len(d["comandos"]), len(contrato.COMANDOS))


if __name__ == "__main__":
    unittest.main()
