# -*- coding: utf-8 -*-
"""O relatorio decide o dia. Numero errado aqui vira campanha pausada a toa.

Testa a agregacao sem banco: um Banco de mentira devolve as linhas, e o que
esta sob teste e a CONTA, que e onde erro passa despercebido.
"""
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from magicads import relatorio  # noqa: E402

HOJE = date.today()
ONTEM = (HOJE - timedelta(days=1)).isoformat()


def linha(slug, canal="meta", conta="act_000000000000002", dia=None, campanha="[C01]",
          gasto=0.0, imp=0, cli=0, conversas=0, conversoes=0):
    """Mesma ordem de `Banco.linhas_no_periodo`."""
    return (slug, canal, conta, dia or ONTEM, campanha,
            gasto, imp, cli, conversas, conversoes)


class BancoFalso(object):
    def __init__(self, linhas=None, antes=None, carteira=None, ultimo=None):
        self._linhas, self._antes = linhas or [], antes or []
        self._carteira, self._ultimo = carteira or [], ultimo or {}
        self.modo = "supabase"

    def linhas_no_periodo(self, desde, ate, slug=None):
        # A janela anterior sempre termina antes do inicio da atual.
        fonte = self._linhas if ate >= HOJE.isoformat() else self._antes
        return [l for l in fonte if not slug or l[0] == slug]

    def carteira(self):
        return self._carteira

    def ultimo_dia_por_conta(self):
        return self._ultimo


class Custo(unittest.TestCase):
    def test_conversao_manda_quando_existe(self):
        # Conta que tem conversao E conversa nao pode somar as duas: seria contar
        # a mesma pessoa duas vezes e dividir o custo pela metade.
        self.assertEqual(relatorio.resultado([100.0, 0, 0, 40, 10]), 10)

    def test_cai_pra_conversa_quando_nao_ha_conversao(self):
        self.assertEqual(relatorio.resultado([100.0, 0, 0, 40, 0]), 40)

    def test_sem_resultado_nao_inventa_custo(self):
        # Dividir por zero viraria infinito; mostrar 0 viraria "custo otimo".
        self.assertIsNone(relatorio.custo([100.0, 0, 0, 0, 0]))
        self.assertEqual(relatorio.linha_custo([100.0, 0, 0, 0, 0]), "sem resultado")

    def test_custo_por_resultado(self):
        self.assertEqual(relatorio.custo([100.0, 0, 0, 0, 4]), 25.0)

    def test_brl_usa_virgula(self):
        self.assertEqual(relatorio.brl(1234.5), "R$ 1234,50")


class Agregacao(unittest.TestCase):
    def test_soma_por_cliente(self):
        linhas = [linha("acme", gasto=10.0, conversas=2),
                  linha("acme", campanha="[C02]", gasto=5.0, conversoes=1),
                  linha("beta", gasto=7.0, conversas=3)]
        fora = relatorio.agrega(linhas, lambda l: l[0])
        self.assertAlmostEqual(fora["acme"][0], 15.0)
        self.assertEqual(fora["acme"][3], 2)
        self.assertEqual(fora["acme"][4], 1)
        self.assertAlmostEqual(fora["beta"][0], 7.0)

    def test_campanha_de_mesmo_nome_em_canais_diferentes_nao_se_mistura(self):
        # "[C01] Institucional" existe na Meta e no Google, e somar os dois
        # esconde qual canal esta caro.
        linhas = [linha("acme", canal="meta", gasto=10.0),
                  linha("acme", canal="google", gasto=4.0)]
        fora = relatorio.agrega(linhas, lambda l: (l[1], l[4]))
        self.assertEqual(len(fora), 2)


class Portfolio(unittest.TestCase):
    def saida(self, banco, dias=7):
        import io
        antigo, buf = sys.stdout, io.StringIO()
        sys.stdout = buf
        try:
            relatorio.portfolio(banco, dias)
        finally:
            sys.stdout = antigo
        return buf.getvalue()

    def test_banco_vazio_ensina_o_proximo_passo(self):
        texto = self.saida(BancoFalso())
        self.assertIn("magicads etl", texto)

    def test_delta_compara_com_a_janela_anterior(self):
        banco = BancoFalso(linhas=[linha("acme", gasto=200.0, conversoes=4)],
                           antes=[linha("acme", gasto=100.0, conversoes=2)])
        texto = self.saida(banco)
        self.assertIn("+100%", texto)

    def test_cliente_novo_nao_vira_delta_falso(self):
        # Sem base anterior, "+100%" seria mentira com cara de numero.
        banco = BancoFalso(linhas=[linha("acme", gasto=200.0, conversoes=4)])
        self.assertIn("novo", self.saida(banco))

    def test_gastou_sem_resultado_e_chamado_pelo_nome(self):
        banco = BancoFalso(linhas=[linha("acme", gasto=300.0),
                                   linha("beta", gasto=50.0, conversoes=5)])
        texto = self.saida(banco)
        self.assertIn("gastaram e nao registraram resultado", texto)
        self.assertIn("acme", texto.split("gastaram e nao registraram resultado")[1])


class Mudas(unittest.TestCase):
    def roda(self, banco):
        import io
        antigo, buf = sys.stdout, io.StringIO()
        sys.stdout = buf
        try:
            codigo = relatorio.mudas(banco)
        finally:
            sys.stdout = antigo
        return codigo, buf.getvalue()

    def test_quem_reporta_nao_vira_alarme(self):
        banco = BancoFalso(carteira=[("acme", "Acme", "meta", "act_000000000000002")],
                           ultimo={("meta", "act_000000000000002"): ONTEM})
        codigo, texto = self.roda(banco)
        self.assertEqual(codigo, 0)
        self.assertIn("reportando normalmente: 1", texto)

    def test_conta_que_emudeceu_vira_alarme(self):
        parou = (HOJE - timedelta(days=6)).isoformat()
        banco = BancoFalso(carteira=[("acme", "Acme", "meta", "act_000000000000002")],
                           ultimo={("meta", "act_000000000000002"): parou})
        codigo, texto = self.roda(banco)
        self.assertEqual(codigo, 1)
        self.assertIn("EMUDECERAM", texto)

    def test_conta_que_nunca_teve_linha_nao_vira_alarme(self):
        # Alertar nela todo dia treina voce a ignorar o alerta, e ai o alerta de
        # verdade passa junto. Ela aparece na lista, mas nao muda o codigo de saida.
        banco = BancoFalso(carteira=[("acme", "Acme", "meta", "act_000000000000002")])
        codigo, texto = self.roda(banco)
        self.assertEqual(codigo, 0)
        self.assertIn("nunca teve linha", texto)
        self.assertNotIn("EMUDECERAM", texto)

    def test_conta_parada_ha_muito_tempo_sai_do_alarme(self):
        velho = (HOJE - timedelta(days=relatorio.DIAS_ATE_ESQUECER + 5)).isoformat()
        banco = BancoFalso(carteira=[("acme", "Acme", "meta", "act_000000000000002")],
                           ultimo={("meta", "act_000000000000002"): velho})
        codigo, texto = self.roda(banco)
        self.assertEqual(codigo, 0)
        self.assertIn("parou em", texto)


if __name__ == "__main__":
    unittest.main()
