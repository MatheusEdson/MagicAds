# -*- coding: utf-8 -*-
"""Os agentes e os fluxos não podem citar comando que não existe.

Este é o teste que faz o conjunto valer alguma coisa. Um agente erra de dois
jeitos, e os dois são silenciosos:

  1. ele INVENTA uma flag (`diag --completo`), roda, erra, e a partir dali quem
     estava olhando para de confiar também no que estava certo;
  2. ele aponta para um fluxo que não existe mais, lê nada, e opina com a
     doutrina genérica que estava na cabeça dele.

Nenhum dos dois aparece revisando código. Os dois aparecem aqui.

A validação de YAML precisa de PyYAML, que NÃO é dependência do projeto — o
MagicAds roda sem instalar nada. Localmente o teste se pula quando falta; na CI
o job `agentes` instala e ele roda de verdade.
"""
import glob
import io
import re
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from magicads import contrato  # noqa: E402

try:
    import yaml
    TEM_YAML = True
except ImportError:
    TEM_YAML = False

AGENTES = sorted(glob.glob(str(RAIZ / "aios" / "agents" / "gandalf*.md")))
FLUXOS = sorted(glob.glob(str(RAIZ / "aios" / "fluxos" / "*.md")))
NOMES = {c["nome"] for c in contrato.COMANDOS}

# `<cliente>`, `<act_...>` e afins são marcadores, não comandos.
CHAMADA = re.compile(r"(?:python -m )?magicads ([a-z]+)")


def texto(caminho):
    with io.open(caminho, encoding="utf-8") as fh:
        return fh.read()


def bloco_yaml(caminho):
    m = re.search(r"```yaml\n(.*?)\n```", texto(caminho), re.S)
    assert m, "sem bloco yaml: %s" % caminho
    return m.group(1)


class ExisteAlgoParaTestar(unittest.TestCase):
    def test_tem_agente(self):
        self.assertTrue(AGENTES)

    def test_tem_fluxo(self):
        self.assertTrue(FLUXOS)


class NinguemInventaComando(unittest.TestCase):
    """Todo `magicads <x>` escrito em agente ou fluxo tem que existir no CLI."""

    def confere(self, arquivos, rotulo):
        inventados = {}
        for caminho in arquivos:
            for achado in CHAMADA.findall(texto(caminho)):
                if achado not in NOMES:
                    inventados.setdefault(Path(caminho).name, set()).add(achado)
        self.assertFalse(inventados, "%s cita comando inexistente: %s" % (rotulo, inventados))

    def test_agentes(self):
        self.confere(AGENTES, "agente")

    def test_fluxos(self):
        self.confere(FLUXOS, "fluxo")

    def test_readme_e_changelog(self):
        self.confere([str(RAIZ / "README.md"), str(RAIZ / "CHANGELOG.md")], "README/CHANGELOG")


class OsPonteirosApontamParaAlgo(unittest.TestCase):
    def test_fluxo_citado_no_agente_existe(self):
        quebrados = {}
        for caminho in AGENTES:
            for alvo in re.findall(r"aios/fluxos/[a-z0-9-]+\.md", texto(caminho)):
                if not (RAIZ / alvo).exists():
                    quebrados.setdefault(Path(caminho).name, set()).add(alvo)
        self.assertFalse(quebrados, "ponteiro morto: %s" % quebrados)

    def test_link_entre_fluxos_existe(self):
        quebrados = {}
        for caminho in FLUXOS:
            for alvo in re.findall(r"\]\(([a-z0-9-]+\.md)\)", texto(caminho)):
                if not (Path(caminho).parent / alvo).exists():
                    quebrados.setdefault(Path(caminho).name, set()).add(alvo)
        self.assertFalse(quebrados, "link morto: %s" % quebrados)

    def test_receita_citada_no_agente_existe(self):
        quebrados = {}
        for caminho in AGENTES:
            for alvo in re.findall(r"receitas/([a-z0-9-]+\.json)", texto(caminho)):
                if not (RAIZ / "receitas" / alvo).exists():
                    quebrados.setdefault(Path(caminho).name, set()).add(alvo)
        self.assertFalse(quebrados, "receita inexistente: %s" % quebrados)


@unittest.skipUnless(TEM_YAML, "PyYAML nao instalado (roda na CI, no job `agentes`)")
class ODefinicaoDoAgenteEValida(unittest.TestCase):
    """O bloco YAML é lido por outra ferramenta. Inválido, ele é ignorado em
    silêncio, e o agente sobe sem nenhuma das regras que você escreveu."""

    def test_todo_agente_parseia(self):
        for caminho in AGENTES:
            try:
                d = yaml.safe_load(bloco_yaml(caminho))
            except yaml.YAMLError as e:
                self.fail("%s: YAML invalido: %s" % (Path(caminho).name, str(e)[:160]))
            self.assertIsInstance(d, dict, Path(caminho).name)

    def test_id_bate_com_o_nome_do_arquivo(self):
        for caminho in AGENTES:
            d = yaml.safe_load(bloco_yaml(caminho))
            self.assertEqual(d["agent"]["id"], Path(caminho).stem, Path(caminho).name)

    def test_todos_se_chamam_gandalf_o_dourado(self):
        for caminho in AGENTES:
            d = yaml.safe_load(bloco_yaml(caminho))
            self.assertEqual(d["agent"]["name"], "Gandalf, o Dourado", Path(caminho).name)

    def test_todo_agente_conhece_os_portoes(self):
        # Sem isto o agente não sabe o que pode rodar sozinho, e a escolha
        # segura dele passa a ser "não faço nada" ou "faço tudo".
        validos = {n for n, _ in contrato.PORTOES}
        for caminho in AGENTES:
            d = yaml.safe_load(bloco_yaml(caminho))
            f = d.get("ferramentas")
            self.assertTrue(f, "%s sem `ferramentas`" % Path(caminho).name)
            self.assertEqual(set(f["portoes"]), validos, Path(caminho).name)
            self.assertIn("magicads contrato", f["contrato"], Path(caminho).name)

    def test_a_ativacao_manda_ler_o_contrato_antes_de_agir(self):
        for caminho in AGENTES:
            d = yaml.safe_load(bloco_yaml(caminho))
            passos = " ".join(
                "%s %s" % (k, v) for p in d["activation-instructions"]
                if isinstance(p, dict) for k, v in p.items())
            self.assertIn("magicads contrato", passos, Path(caminho).name)


if __name__ == "__main__":
    unittest.main()
