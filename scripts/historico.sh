#!/usr/bin/env bash
# Varredura do HISTORICO INTEIRO: todo blob de todo commit, mais mensagem,
# nome e e-mail de autor. Usa as MESMAS regras do scrub (scripts/regras.sh).
#
#   ./scripts/historico.sh
#
# POR QUE ISTO EXISTE SEPARADO DO scrub.sh:
#
#   O scrub le a arvore de trabalho. Segredo que entrou num commit e saiu no
#   commit seguinte SOME da arvore e CONTINUA no pack -- e o push leva o pack.
#   Num repo publico isso e definitivo: vazou, e apagar depois nao desfaz.
#   O hook de pre-push ja olha os commits que estao indo naquele push; este
#   aqui olha tudo que ja existe. Rode UMA vez antes de tornar o repo publico,
#   e de novo antes de mandar pra alguem.

set -uo pipefail
cd "$(dirname "$0")/.."
. "$(dirname "$0")/regras.sh"

ACHADOS=$(mktemp)
trap 'rm -f "$ACHADOS"' EXIT INT TERM

# Um regex so, com todas as regras, pra nao pagar 13 processos por blob. O
# titulo da regra e reatribuido depois, so pros poucos trechos que casarem.
TODAS=""
for regra in "${REGRAS[@]}"; do
    TODAS="${TODAS:+$TODAS|}(${regra#*|})"
done

classifica() {   # <trecho> -> titulo da 1a regra que casa
    local trecho="$1" regra
    for regra in "${REGRAS[@]}"; do
        if printf '%s' "$trecho" | grep -qiE "^(${regra#*|})$" 2>/dev/null; then
            printf '%s' "${regra%%|*}"; return
        fi
    done
    printf '%s' "(sem classe)"
}

verifica() {   # <origem>; conteudo em stdin
    local origem="$1" trecho
    while IFS= read -r trecho; do
        [ -n "$trecho" ] || continue
        permitido "$trecho" && continue
        # Grava num ARQUIVO, e nao numa variavel. `... | verifica` roda em
        # subshell, e variavel setada la dentro nao volta pro pai. A 1a versao
        # desta varredura imprimiu 7 achados e concluiu "LIMPO" exatamente por
        # isso -- o mesmo carimbo falso que o autoteste do scrub existe pra
        # impedir. Verdicto que nao pode mentir vale mais que regra nova.
        printf '%s\t%s\t%s\n' "$(classifica "$trecho")" "$origem" "$trecho" >> "$ACHADOS"
    done <<< "$(grep -aoiE "$TODAS" 2>/dev/null | sort -u)"
}

mapa=$(git rev-list --objects --all)
# `--objects` lista TREE junto com blob, e `git cat-file -p` de uma tree
# imprime o SHA de cada filho. SHA e hexadecimal: um que por acaso comece
# com "eaa" casa com a regra do token da Meta (EAA[A-Za-z0-9]{20,}, que
# roda sem diferenciar maiuscula), e a varredura acusa segredo onde ha o
# hash de um diretorio. Aconteceu de verdade, com a origem aparecendo como
# `magicads` -- que nem e um arquivo. Falso positivo em ferramenta de
# seguranca nao e ruido: e o comeco do habito de ignorar o alarme.
blobs=$(printf '%s\n' "$mapa" | awk 'NF>1 {print $1}' | sort -u \
        | git cat-file --batch-check='%(objectname) %(objecttype)' 2>/dev/null \
        | awk '$2 == "blob" {print $1}')
n_blob=$(printf '%s\n' "$blobs" | grep -c .)
n_commit=$(git rev-list --all --count)

# Varredura que leu quase nada nao pode dizer "limpo". Mesmo principio do
# autoteste do scrub: sem prova de que olhou, saida verde nao vale nada.
if [ "$n_blob" -lt 10 ]; then
    echo "ABORTADO: li $n_blob blobs. Isso nao e varredura, e carimbo falso."
    exit 2
fi
# Autoteste ANTES de varrer. Esta ferramenta roda raramente -- uma vez antes
# de abrir o repo, outra antes de mandar pra alguem -- e ferramenta que roda
# raro e onde uma regressao mora por meses sem ninguem notar. A isca passa
# pelo mesmo `verifica` da varredura de verdade: regex combinado, permitido(),
# arquivo de achados. Se ela nao acender, o "LIMPO" la embaixo nao vale nada.
printf 'EAA%s ato act_%s\n' 'AUTOTESTEDAVARREDURANAOEUMTOKENREAL' '778899112233' | verifica "<autoteste>"
if [ ! -s "$ACHADOS" ]; then
    echo "ABORTADO: a isca do autoteste nao acendeu. A varredura esta cega;"
    echo "          um \"LIMPO\" dela nao provaria nada."
    exit 2
fi
: > "$ACHADOS"   # limpa a isca; daqui pra frente so achado de verdade

# Clone raso e a maneira mais facil de esta ferramenta mentir: `git clone
# --depth 1` e o checkout padrao do GitHub Actions trazem UM commit, e ai a
# varredura le a arvore de hoje e assina "historico limpo" sem ter visto
# historico nenhum. Na CI, isso exige `fetch-depth: 0`.
if [ "$(git rev-parse --is-shallow-repository 2>/dev/null)" = "true" ]; then
    echo "ABORTADO: este clone e RASO. Ele nao tem o historico pra varrer."
    echo "          git fetch --unshallow   (ou fetch-depth: 0 na CI)"
    exit 2
fi
echo "varrendo $n_blob blobs de $n_commit commits, mais mensagens e autores"
[ -n "$CLIENTES" ] || { echo; aviso_sem_lista; echo; }

# caminho de cada blob, numa passada so
declare -A CAMINHO=()
while read -r h p; do
    [ -n "${p:-}" ] || continue
    [ -n "${CAMINHO[$h]:-}" ] || CAMINHO[$h]="$p"
done <<< "$mapa"

# As duas ferramentas de varredura ficam de fora: o conteudo delas E os padroes.
# Hoje as regras moram em regras.sh, mas ja moraram dentro do scrub.sh, e no
# HISTORICO esse passado continua la. O buraco que sobra: segredo colado dentro
# de um desses dois arquivos passaria -- e neles que se olha primeiro na duvida.
for b in $blobs; do
    case "${CAMINHO[$b]:-}" in scripts/regras.sh|scripts/scrub.sh) continue ;; esac
    git cat-file -p "$b" 2>/dev/null | verifica "${CAMINHO[$b]:-$b}"
done
git log --all --format='%H%n%an%n%ae%n%cn%n%ce%n%s%n%b' | verifica "<mensagem/autor de commit>"

echo
if [ -s "$ACHADOS" ]; then
    echo "ACHADOS (unicos):"
    sort -u "$ACHADOS" | sed 's/^/  /'
    echo
    echo "Pra achar em que commit: git log --all -S'<o trecho>' --oneline"
    echo
    echo "HISTORICO SUJO. Avalie um por um."
    echo "Se for segredo de verdade: ROTACIONE primeiro. Reescrever o historico"
    echo "nao desfaz o que ja foi clonado, e num repo publico isso e definitivo."
    exit 1
fi
echo "HISTORICO LIMPO: nenhum segredo, identificador real, dado de cliente ou"
echo "infra interna em nenhum blob de nenhum commit, nem em mensagem de commit,"
echo "nome de autor ou e-mail."
