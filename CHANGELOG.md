# Changelog

## 1.6.3 — 2026-09-14

**A tabela de capacidades dava o mesmo `❌` pro Google Ads e pro Google Business,
e são coisas opostas.** No Business a API de produto **não existe**: ninguém sobe,
nem você nem ferramenta paga. No Ads a API cria campanha, grupo, anúncio e
palavra-chave sem problema — o que falta é código deste repositório.

Lado a lado, com o mesmo símbolo e com “subida é na interface, hoje” na coluna
do lado, isso lia como limitação **da plataforma**. Num arquivo que abre com
“antes de promessa, a verdade”, era a linha errada pra estar errada.

Agora Google Ads é `⚠️ dá, não implementado aqui` e Google Business segue
`❌ não existe API`, com o parágrafo explicando a diferença. Os cinco agentes
passaram a dizer o motivo certo: **nunca “o Google não permite”**.

### O portão que faltava documentar

Quem for implementar esbarra numa burocracia que leva **dias**, não minutos:

1. O `developer token` sai no **API Center de uma conta de administrador (MCC)**.
   Conta comum não emite.
2. Ele nasce em **acesso de teste**, que só fala com **contas de teste**. É a
   pegadinha: o token parece válido, autentica, e só quebra quando você aponta
   pra conta de verdade.
3. Pra tocar produção você **solicita** a subida de nível num formulário que o
   Google revisa.

Quem já lê produção no ETL daqui **já passou** por esse portão — acesso de teste
não leria conta de cliente. Pra essa pessoa falta só o código. Pra quem começa
do zero, o pedido é o primeiro passo e não dá pra pular.

A ressalva de sempre continua de pé: o que trava a implementação aqui não é o
acesso, é o modelo de receita. Search sem lista de negativas é uma máquina de
comprar clique errado.
## 1.6.2 — 2026-09-14

**O passo 0 do README fazia as duas guardas reprovarem no minuto um.** Num clone
limpo, `cp .scrub-clientes.local.exemplo .scrub-clientes.local` copiava um modelo
com nomes **ativos**, e "Acme Pneus" é o exemplo usado no próprio README, no
SECURITY e no `cli.py`. Resultado: o primeiro `./scripts/scrub.sh` de quem acabou
de clonar dizia `NAO EMPURRE`, e o `historico.sh` dizia `HISTORICO SUJO`,
apontando pra **documentação do próprio repo**.

Alarme falso no minuto um é a forma mais rápida de alguém desinstalar a trava
mentalmente, e é irônico que tenha acontecido justo aqui, duas versões depois de
a 1.5.1 consertar um falso positivo pelo mesmo motivo.

Os nomes de exemplo vão comentados. O modelo continua ensinando o formato, e o
scrub avisa que **não checou** até o dono da cópia pôr os clientes dele. Dois
testes seguram: o modelo não pode ter linha ativa, e não pode virar arquivo
vazio.

Achado rodando o caminho do recém-chegado num clone novo do GitHub, do zero,
colando o README linha por linha.

118 testes.
## 1.6.1 — 2026-09-14

O `pre-push` era a **terceira** lista de regras. Ele tinha o próprio regex
(`EAA...` e chave privada, só isso) e o próprio filtro de placeholder, ou seja,
tudo que a 1.6.0 acabou de unificar existia em dobro no lugar mais crítico: a
última trava antes do repo virar público. Nome de cliente, conta de anúncio, DSN
com senha e caminho de máquina **passavam** por ele.

Agora ele sourceia `scripts/regras.sh` como os outros dois, e aplica as 13
regras às linhas adicionadas pelos commits que estão indo naquele push. Teste
novo cobre as três ferramentas, não mais duas.

Medido num clone: token num commit, removido no commit seguinte, `git push`
→ `PUSH BLOQUEADO`, com a classe e o trecho na tela.

116 testes.
## 1.6.0 — 2026-09-14

`scripts/historico.sh`: varre **todo blob de todo commit**, mais mensagem, nome
e e-mail de autor. É outra pergunta que o scrub não responde — segredo que entrou
num commit e saiu no seguinte some da árvore e **continua no pack**, e o push
leva o pack. Num repo público isso é definitivo: vazou, e apagar depois não
desfaz.

Rodado neste repo: **183 blobs, 15 commits. Limpo.** Nenhum segredo, nenhum
identificador real, nenhum nome de cliente, nem em blob, nem em mensagem de
commit, nem em nome ou e-mail de autor.

### As regras agora moram num lugar só

`scripts/regras.sh`, sourceado pelos dois. Duas listas em dois scripts garantem
que uma hora uma regra entra numa e não na outra, e isso não falha barulhento:
falha calado, dizendo “limpo” sobre o que nunca olhou. Teste novo impede que
qualquer um dos dois redefina `REGRAS`.

### Três jeitos de assinar verde sem ter olhado, todos fechados

- **A própria varredura mentiu na primeira versão.** Imprimiu 7 achados e
  concluiu “LIMPO”: `... | verifica` roda em subshell, e a variável de estado
  setada lá dentro não volta pro pai. Agora o veredito sai de um arquivo.
- **Clone raso.** `--depth 1` e o checkout padrão do GitHub Actions trazem
  **um** commit; a varredura leria a árvore de hoje e assinaria “histórico
  limpo” sem ter visto histórico nenhum. Agora recusa, e o job da CI usa
  `fetch-depth: 0`.
- **Isca própria.** Ferramenta que roda raro é onde regressão mora por meses.
  Antes de varrer, ela passa uma isca pelo mesmo caminho da varredura de
  verdade; se não acender, aborta.

### O buraco que a isca abriu

Plantando `EAA<token>1234567890` num commit e removendo no seguinte, a varredura
disse **LIMPO** sobre um token que estava lá. Causa: `*1234567890*` solto na
lista de exceções liberava **qualquer coisa que contivesse** a sequência —
inclusive um token de 40 caracteres que a tivesse no meio. Ancorado. É a mesma
família do bug da 1.5.0: exceção larga demais desarma a regra inteira.

### Outros

- Faixas de documentação (RFC 5737) na lista de exceções, e a isca de IP do
  autoteste com o literal partido — assim o scrub voltou a **se ler**. Só
  `regras.sh` fica de fora, porque o conteúdo dele é, por definição, os padrões.
- DSN cuja senha é a própria palavra “senha” passa a ser tratada como
  placeholder. Troca estreita e consciente: `:Xk9#2p@` continua reprovando.

116 testes.
## 1.5.2 — 2026-09-14

O resto da lista da auditoria. Nada aqui vazou nada; são os pontos em que o
código faria a coisa errada **em silêncio**, que é o que assusta num kit cujo
produto é um número.

- **As duas pernas do banco tinham pesos diferentes.** A de psycopg2 passa
  argumento por fora do SQL; a de PostgREST montava a query com `%s` cru. E o
  modo de falhar é traiçoeiro: um `&` no valor **não dá erro**, vira outro
  filtro, e a resposta volta certinha respondendo outra pergunta. Um
  `--cliente 'acme&limit=1'` truncaria o relatório sem avisar. Agora tudo que
  entra num filtro passa por `Banco._f()`. O `.` segue passando de propósito
  (só o primeiro separa operador de valor), porque escapar demais quebra
  igual: o slug para de casar com o que já está gravado.

- **Token do Google revogado derrubava a rodada inteira.** O refresh roda
  antes do laço, e sem `try` virava traceback — depois do Meta já ter coletado
  e gravado. O dado não se perdia, mas o resumo e o código de saída sim, e quem
  lê cron por e-mail via só o stack trace. Agora falha de canal se comporta
  como falha de conta: entra em `FALHAS` e a rodada segue.

- **O `etl.py` dizia no próprio cabeçalho que tudo passa pelo `limpa()`, e não
  importava o `limpa`.** Na prática funcionava, porque os erros vinham do
  `http()` já redigidos, mas era verdade por acidente. Agora é por construção,
  nos 4 pontos.

- **`schema.sql` explicava por que não tem RLS e não dizia o preço disso no
  Supabase:** tabela em `public` sem RLS é legível por qualquer um com a chave
  `anon`, e a `anon` nasce pra ser pública. O que está ali é a carteira inteira
  e o investimento de cada cliente. O arquivo agora avisa, e traz o `alter
  table ... enable row level security` pronto — que fecha a `anon` sem quebrar
  o CLI, porque a `service_role` ignora RLS.

- **CI com `permissions: contents: read`.** Sem isso o `GITHUB_TOKEN` nasce com
  a permissão padrão do repositório, e qualquer Action de terceiro que entre
  aqui um dia herda o direito de escrever. Barato agora, caro depois.

112 testes.
## 1.5.1 — 2026-09-14

A regra de nome de cliente, que a 1.5.0 tinha acabado de tirar de dentro do
script, precisou de duas correções no primeiro uso real.

- **Alarme falso.** A busca era por substring, então nome curto na lista
  reprovava palavra comum. No primeiro uso real um nome de 5 letras casou com
  uma palavra maior **dentro do próprio CHANGELOG**, e o push travou por causa
  de uma frase em português. Agora casa palavra inteira: "Acme" não reprova mais
  "Acmestore". Alarme falso é como um scrub morre — primeiro irrita, depois
  ninguém lê a saída, e aí ele não protege mais nada.

- **Isca número 4.** Essa é a única regra que depende de um arquivo de fora, ou
  seja, a única que pode ficar calada sem ninguém notar — lista só com
  comentário, encoding errado, um "|" sobrando. O autoteste passou a plantar uma
  isca com o **primeiro nome da sua própria lista** e a exigir que o scrub
  encontre. E o aviso de lista ausente agora separa “não existe” de “existe e
  está vazia”, que são problemas diferentes.

- `.scrub-clientes.local.exemplo` versionado, e `cp` dele no passo 0 do README.
  O primeiro rascunho desse modelo citava um cliente de verdade numa linha de
  explicação, e o próprio scrub barrou o commit.
## 1.5.0 — 2026-09-14

Auditoria antes de mandar o repo pra alguem: um agente de segurança e um de
exposição leram tudo, incluindo os 156 objetos do histórico. **Segredo: zero.**
Nenhuma credencial, nenhum identificador real, nenhum nome de cliente, nem no
HEAD nem em commit nenhum. Nada a rotacionar.

O que apareceu foi pior de um jeito diferente: as **guardas** tinham furo, e
guarda com furo é a única coisa que dá permissão pra parar de olhar.

### Corrigido — segurança

- **A palavra “exemplo” desarmava o scrub inteiro.** A lista de exceções era
  aplicada à **linha**, não ao trecho que casou. Num repo escrito em português,
  todo construído em cima de `exemplos/`, essa é a palavra mais comum que existe.
  Medido:

  ```
  # exemplo de configuracao
  TOKEN=EAA<token de verdade>      ->  “limpo. pode empurrar.”
  conta de exemplo act_<real>      ->  “limpo. pode empurrar.”
  ```

  Agora a exceção olha o **trecho casado**: `EAAxxxxxxxx` é placeholder, `EAA<real>`
  não é, e o comentário em volta não muda nada. Os três casos acima passaram a
  reprovar.

- **O `post` prometia não criar e criava.** Em `/campaigns` o `validate_only` não
  protege, e o CLI imprimia “a Meta vai conferir e NÃO criar”, avisava logo
  abaixo que ali era mentira, e mandava assim mesmo. Divulgar não é controlar:
  agora **recusa** e manda usar o `subir`, que ensaia offline.

- **O scrub nunca olhava o histórico.** Segredo que entrou num commit e saiu no
  seguinte some da árvore e continua no pack, e o push leva o pack. O `pre-push`
  passa a varrer também os commits que estão indo naquele push.

- **Redigir depois de cortar não redige.** O texto do erro era truncado em 400
  caracteres **antes** do filtro de segredo; se o corte cai no meio do token, o
  pedaço que sobra não casa com nada e sai na tela. Invertido nos três pontos.

- **A checagem de permissão do cofre era pulada no Windows**, que é onde este
  projeto é operado, enquanto o `SECURITY.md` prometia que o CLI avisa. Agora ele
  avisa que **não checou**, e diz como conferir a ACL na mão.

- **A lista de clientes do scrub saiu do repositório.** Escrever os nomes da sua
  carteira dentro de um script público é vazar exatamente o que ele existe pra
  proteger. Passa a ler `.scrub-clientes.local`, que está no `.gitignore`. Sem o
  arquivo, ele **avisa** em vez de fingir que checou.

- Classe nova no scrub: **infra** (IP, caminho de máquina) e **customer id cru**
  de 10 dígitos, que antes só era pego por coincidência pela regra de telefone.
  O autoteste passou a plantar **três** iscas, uma delas justamente numa linha com
  a palavra “exemplo”, e ganhou `trap` pra não deixar isca em disco num Ctrl-C.

### Corrigido — o primeiro comando que o recém-chegado roda

- **O `diag` reprovava conta boa.** O veredito exigia o portão de WhatsApp, que só
  vale pra CTWA e cuja sonda precisa de uma campanha já existente. Efeito: conta
  **nova** (sem campanha) e loja que vende **no site** (sem WhatsApp na Página)
  recebiam “NÃO SUBA AINDA” com todos os portões OK, e a mensagem mandava
  “resolver o que está FALTA acima” sem nada estar faltando. Agora quem decide são
  os portões de conta e Página; o WhatsApp vira ressalva (“PODE SUBIR, menos
  CTWA”). Cinco testes novos, num `veredito()` que virou função pura.

- **Os `docs/` ensinavam o caminho antigo.** Nenhum deles citava `subir`, `etl`,
  `relatorio` ou `remover`: o “dia a dia” mandava montar campanha na mão com
  `post`, que é o que o README diz que queima a tarde. Reescritos.

- O comando de limpeza imprimia `<cliente>` literal. Agora sai colável.

### Documentação que dizia o contrário do código

- `SECURITY.md` dizia que o filtro de segredo mora em `cli.py` **e** `etl.py`. Ele
  é um só, em `comum.py`, e o README se orgulha disso em negrito.
- `ARQUITETURA.md`: o filtro troca por `<SEGREDO>` (não `<TOKEN>`); são 4 tabelas
  e **nenhuma** view; e o portão 5 do fluxograma ainda mandava ler Página só pelo
  portfólio, que é o bug que a 1.3.0 consertou.
- `README`: “cinco coisas” numa tabela de seis. Num repo cuja tese é “conte o
  número certo”, esse erro é o que o leitor da área vê sem procurar.
- O CHANGELOG dizia que `logo.svg` e `mark.svg` compartilham geometria “em vez de
  duas cópias”. São duas cópias idênticas. Texto corrigido.
- `gandalf.md` tinha dois STEP 3.

### Instalação

O `cp scripts/hooks/pre-push` virou o **passo 0** do README. É a única proteção
que roda antes do push; a CI só roda depois, e depois já é público.

107 testes.
## 1.4.0 — 2026-09-14

Segunda rodada ao vivo, agora **escrevendo**: ETL gravando num Postgres de
verdade e `subir --executar` criando campanha de verdade. Os dois caminhos
nunca tinham rodado fora de teste. Os dois quebraram.

O padrão se repetiu: **o que falha ao vivo não é o que os testes cobrem, é o
que a Meta responde.** Um teste com API de mentira devolve o que você imaginou
que ela devolve, então ele confirma o seu modelo mental em vez de corrigi-lo.

### Corrigido

- **O `subir --executar` falhava na primeira chamada, sempre.** A Meta recusa
  campanha ABO (verba no conjunto) sem `is_adset_budget_sharing_enabled`
  explícito, e recusa mal: `message` diz só "Invalid parameter", e o motivo real
  só aparece em `error_user_title`.
  - `100 / 4834011`. Como **todas** as receitas do repo põem a verba no conjunto,
    isso derrubava 100% das subidas — o `subir` inteiro era decorativo.
  - Vai `false` de propósito: com `true` a Meta reparte até 20% da verba entre
    os conjuntos, e acaba a separação por loja, praça ou unidade, que costuma ser
    a única razão de ter mais de um conjunto.

- **O comando de limpeza não limpava, e dizia que sim.** Quando o `subir` falha
  no meio, ele imprime como remover o que ficou de pé. O comando impresso era
  `post <id> _method=DELETE`, e a Graph API responde `{"success": true}` **sem
  apagar nada** (medido com 8s de espera e dois GET: o objeto continuava
  `PAUSED`).
  - É pior que não ter comando: você risca o órfão da lista e ele fica lá, na
    conta do cliente, até alguém reparar semanas depois.
  - Agora existe **`remover <cliente> <id> --executar`**: HTTP DELETE de verdade,
    e a prova é **reler o objeto por GET** — `success: true` não é prova, foi
    exatamente o que o caminho quebrado devolvia. Sai em código 1 se o objeto
    sobreviveu. Portão **HUMANO**: apagar não tem desfazer.

- **Toda imagem da conta se chamava `bytes`.** O upload ia em base64, e o nome do
  campo vira o nome da imagem na biblioteca. Com 50 criativos, nenhum deles dá
  pra achar.
  - Trocar o nome do campo no base64 **derruba o upload** (`100 / 2490361`,
    "arquivo de imagem inválido"). O caminho que funciona é multipart, que já
    existia no repositório para vídeo. Agora a imagem nasce com o nome do arquivo.

- `diag` terminava mandando montar com `post`; manda usar `subir`, que ensaia
  antes e nasce `PAUSED`.

### Provado ao vivo

- **ETL gravando**: schema aplicado num Postgres limpo, 16 linhas gravadas, e
  **três rodadas seguidas continuam 16 linhas** — a chave primária é a chave de
  idempotência, e agora isso está medido, não argumentado. `relatorio` leu do
  banco e fechou com o mesmo número.
- **Ciclo completo do `subir`**: campanha + conjunto + criativo + anúncio criados
  de verdade, todos `PAUSED`, conferidos por `GET`, e apagados com `remover`.

### Aviso sobre limpeza

`DELETE /act_<id>/adimages?hash=...` responde `{"success": true}` e **não apaga a
imagem** (conferido 20s depois: `status` continua `ACTIVE`), tenha ela sido usada
por algum criativo ou não. Imagem de teste se apaga na biblioteca do
Gerenciador, na mão. O `remover` do MagicAds cobre campanha, conjunto, anúncio e
criativo, que é onde mora o estrago.

### Testes

100 (eram 93). Os novos travam exatamente o que quebrou: campanha ABO sem o
campo, e o comando de limpeza voltar a apontar para `_method=DELETE`.

## 1.3.0 — 2026-09-14

Primeira rodada **contra conta real** (carteira inteira, só leitura). Achou dois bugs
que nenhum teste com API de mentira acharia, porque os dois dependem do formato
que a Meta devolve de verdade.

### Corrigido

- **O ETL contava o mesmo lead duas vezes.** A Meta reporta o mesmo resultado em
  mais de um `action_type`: `lead` é o total de Leads e **já inclui** o do pixel
  e o do formulário. O parser somava os três.
  - Visto ao vivo: uma linha com `lead=1` e
    `offsite_conversion.fb_pixel_lead=1` — o mesmo lead, contado como dois.
  - É o jeito mais caro de errar: resultado inflado **divide o custo**, então um
    lead de R$ 100 aparece como dois de R$ 50 e você escala o que não estava
    funcionando. Na conta testada, o custo por resultado dobrou depois do
    conserto. Para ser claro: o parser errado é **desta ferramenta**, que nasceu
    em 14/09; nenhum relatório de cliente foi gerado por ele.
  - Agora existem **famílias**: dentro de cada uma o agregado manda e os
    específicos só entram se ele não veio; entre famílias (lead × compra) soma
    normal. Cinco testes de regressão, incluindo o caso real.

- **O `diag` dava "página FALTA" com dez páginas na mão.** Ele lia página só
  pelas bordas do portfólio (`owned_pages`/`client_pages`). Um system user que
  opera o BM do *cliente* sem ser admin de lá recebe **lista vazia** nessas
  bordas — 200 com `data:[]`, não erro. Ao vivo: **todas** as bordas de negócio
  devolveram zero enquanto `me/assigned_pages` devolvia a lista inteira de
  páginas usáveis. Agora usa as duas
  fontes, deduplica, e diz de onde veio cada uma.

### Mudou

- **O veredito do `diag` agora conta.** Com token de frota, "forma de pagamento:
  OK" bastava **uma** conta ter forma de pagamento para a linha ficar verde. Na
  conta real isso escondia que **metade** das contas não estava pronta para subir. As
  linhas passam a mostrar a contagem (`OK (x de y)`) e há uma linha própria de
  `contas prontas p/ subir`.
- A sonda de WhatsApp agora escolhe uma página **com `MESSAGING`** e uma conta
  que realmente pode criar. Pendurada na página errada, ela devolvia outro erro
  e você concluía a coisa errada sobre o WhatsApp.
- 93 testes (eram 88).

## 1.2.0 — 2026-09-14

O elo que faltava: os agentes tinham **doutrina** e nenhum **contrato com a
ferramenta**. Sabiam o que aconselhar e não sabiam o que rodar — e por isso
inventariam flag e prometeriam automação onde não existe API.

### Novo

- **`magicads contrato`** — a ferramenta se descreve. Lista real dos comandos
  daquela versão, com **o portão de cada um**: `LIVRE` (roda à vontade),
  `ESCREVE` (roda e conta depois), `FREIO` (em emergência roda sozinho e avisa
  depois), `HUMANO` (nunca roda: monta, mostra, espera). `--json` para
  ferramenta. Uma lista escrita à mão divergiria do código no primeiro commit,
  e aí o agente passaria a mentir com mais confiança.
- **`aios/fluxos/`** — o ofício: `meta-subir`, `meta-operar`, `meta-emergencia`,
  e um arquivo por plataforma. O `README.md` de lá é **a matriz honesta do que
  cada plataforma deixa fazer**, que é o que impede o agente de prometer o
  impossível.
- **`magicads video`** — sobe vídeo para a biblioteca da conta (multipart, sem
  dependência nova). O `subir` aceita `video_id` + `capa_hash`. Vídeo sem capa
  faz a Meta sortear um frame, e frame sorteado de vídeo vertical costuma ser a
  pessoa de olho fechado — por isso a receita exige.
- **Posicionamento e Instagram no `subir`**: `posicionamentos`,
  `posicoes_instagram`, `posicoes_facebook` e `instagram_id`. Sem declarar
  posicionamento, a Meta vai buscar volume barato em Audience Network; sem
  `instagram_id`, o anúncio roda no IG com a identidade da Página do Facebook.
- **`receitas/loja-video-reels.json`** — a quinta receita, mostrando as três
  peças que só aparecem em vídeo.
- **`tests/test_agentes.py`** — falha se um agente ou fluxo citar comando que
  não existe, apontar para arquivo apagado, ou pedir receita que sumiu. E
  valida o bloco YAML de cada agente (job próprio na CI, com PyYAML instalado
  só lá — o MagicAds continua sem dependência).
- 88 testes (eram 60).

### Corrigido

- **O bloco YAML de dois agentes não era YAML válido**: `description: Monta a
  semana: picos...` tem dois `:` e o parser para no primeiro.
  - Para ser justo com o tamanho do problema: hoje **ninguém parseia esse
    bloco**. No Claude Code o `.md` inteiro vira prompt e o modelo lê como
    texto, então as regras continuavam valendo. O bloco inválido não estava
    apagando nada.
  - Vale arrumar mesmo assim, por dois motivos: um bloco que se anuncia como
    `yaml` e não é vira uma armadilha para a primeira ferramenta que tentar lê-lo
    (um índice, um manifest, um verificador de portões), e ela vai falhar ou
    pular em silêncio. E os testes de conteúdo — id bate com o arquivo, todos se
    chamam Gandalf, todos conhecem os portões — precisam de um parse para
    existir.

### Mudou

- Instagram sai de "🚧 depois" para **feito**: ele nunca foi um canal a mais, é
  posicionamento da mesma campanha. Tratar como canal separado levaria a
  campanha duplicada e verba dividida entre duas coisas que a Meta já otimizava
  junto.
- GBP sai de "🚧 depois" para **⛔ não tem API de produto**. O fluxo está
  escrito; a automação não existe, e prometer que existe seria o pior erro do
  pacote.

## 1.1.0 — 2026-09-14

### Novo

- **`pausar <cliente> --tudo`** — o freio geral. Pausa toda campanha ativa das
  contas do cliente e **executa direto**: digitar `--tudo` já é a confirmação, e
  freio que pede confirmação em cima disso é freio que você não consegue usar
  às 23h. A lista de contas sai da **carteira**, nunca de `me/adaccounts` — o
  token quase sempre enxerga conta de cliente vizinho, e pausar a campanha do
  vizinho é pior que o problema que você estava resolvendo. Sem carteira, exige
  o `act_` na mão. Confere cada uma por `GET` no próprio id e denuncia quem a
  Meta aceitou e não aplicou. Não existe `ativar --tudo`.
  - Lista vazia não é declarada como "nada ativo": `data:[]` com HTTP 200 é
    também o que a Meta devolve sob rate limit, e dizer "tudo certo" aí é mandar
    a pessoa dormir com a conta gastando.
- **CI** (`.github/workflows/provas.yml`): testes em Python 3.8 e 3.12, Linux e
  Windows · o scrub · e o **ensaio de cada receita de exemplo**. O hook de
  pre-push depende de quem clonou ter instalado; quem forka não instala, e aí a
  promessa de "nenhum segredo no repo" valia só na máquina de um.
- 60 testes (eram 55).

### Mudou

- **Nova marca: chapéu de mago**, estilo quadrinho, em ouro — casa com *Gandalf,
  o Dourado* de um jeito que a varinha não casava. `logo.svg` traz a mesma
  geometria do `mark.svg`, deslocada por `transform`. São dois arquivos, então
  retocar um e esquecer o outro continua possível: quem mexer num, confira o
  outro. Legível até 32px.

## 1.0.0 — 2026-09-14

A v0 era biblioteca: dava pra ler a API, mas não dava pra **operar**. Faltavam
as três peças que fecham o ciclo — cadastrar a carteira, subir campanha sem
montar payload na mão, e ler o que o ETL gravou.

### Novo

- **`subir <receita.json>`** — campanha + conjunto + criativo + anúncio a partir
  de um JSON. Modo **ensaio por padrão** (imprime os quatro payloads e não chama
  a Meta); criar de verdade exige `--executar`. Tudo nasce `PAUSED`, e não existe
  opção de subir ligado. Se falhar no meio, imprime o que já foi criado e o
  comando exato pra remover.
- **`receitas/*.json`** — uma por tipo de conta (B2B, local/WhatsApp, loja,
  balcão), casadas com os agentes Gandalf. Cada uma carrega, em `_atencao`, a
  armadilha específica daquele tipo.
- **`relatorio`** — a leitura que faltava, em três perguntas: portfólio (com Δ
  contra a janela anterior e quem **gastou e não registrou resultado**),
  `relatorio <cliente>` (ontem contra a média da própria campanha) e
  `relatorio --mudas` (separa conta que **emudeceu** de conta que nunca teve
  linha — alertar na segunda treina você a ignorar o alerta).
- **`init`** — confere cofre, banco e schema, e **diz o que falta**. Setup que
  falha calado é como se descobre que o banco não tinha tabela depois do ETL
  rodar 20 contas.
- **`cliente` / `conta`** — a carteira, que mora no banco e não em arquivo
  versionado. `conta --remover` desativa sem apagar: o histórico continua
  valendo pra comparação do período anterior.
- **`imagem <cliente> <conta> <arquivo>`** — sobe a imagem e devolve o hash que
  a receita pede.

### Mudou

- **Um filtro de segredo só**, em `magicads/comum.py`. Antes `cli.py` e `etl.py`
  tinham cada um o seu — dois filtros não são redundância, são a chance de um
  ficar pra trás quando a regra mudar. Agora o token sai do cofre já registrado:
  quem chama não precisa lembrar de proteger.
- `magicads/banco.py` separado do ETL, com os dois backends (PostgREST e
  psycopg2) atrás de uma costura só, mais schema e carteira.
- `http()` ganhou `form=` — a Graph API quer POST urlencoded, Supabase e Google
  querem JSON. Misturar os dois dava erro que parecia de permissão.
- 55 testes (eram 16), todos stdlib. Os novos cobrem validação de receita e
  agregação do relatório.

## 0.1.0

Primeiro corte público: guia do app Meta, `diag` com os 6 portões, CLI de
leitura/escrita na Graph, ETL Meta + Google idempotente, schema de 4 tabelas e
os agentes Gandalf.
