# Fluxo — Instagram

> **Instagram não é um canal a mais. É posicionamento.**

Mesma Graph API, mesma conta de anúncio, mesma campanha. O que muda é uma linha
no targeting. Tratar como canal separado leva a campanha duplicada e verba
dividida entre duas coisas que a Meta já otimizava junto — e verba dividida em
conta pequena não produz duas leituras, produz dois ruídos.

Por isso não existe `--so-instagram` no ETL nem receita de Instagram: ele já está
no que você sobe.

---

## O que declarar na receita

```json
"conjunto": {
  "posicionamentos": ["facebook", "instagram"],
  "posicoes_instagram": ["stream", "story", "reels"],
  "posicoes_facebook": ["feed"]
},
"instagram_id": "000000000000001"
```

**`posicionamentos`** vira `publisher_platforms`. Sem ele, a Meta escolhe onde
entregar e costuma achar volume barato em **Audience Network** — que enche o
relatório de impressão e não enche mais nada. O `subir` avisa quando você omite.

**`instagram_id`** é a conta do Instagram que assina o anúncio. Sem ele, o
anúncio roda no Instagram com o **nome e a foto da Página do Facebook**.
Funciona, entrega, e parece de outra marca para quem vê. O `subir` também avisa.

---

## O criativo muda de forma, não só de tamanho

Story e Reels são **9:16 e sem borda**. Reaproveitar o quadrado do feed com
barra preta em cima e embaixo não é economia: é o criativo dizendo "isto é
anúncio" antes da primeira palavra.

Se você só tem o quadrado, é melhor rodar **só feed** do que rodar em story com
o quadrado esticado. Menos posicionamento com o criativo certo bate mais
posicionamento com o criativo errado.

Vídeo em story e reels precisa dos três primeiros segundos resolvidos, porque é
onde a decisão de continuar acontece. E precisa de **capa**: sem `capa_hash` a
Meta sorteia um frame, e frame sorteado de vídeo vertical costuma ser a pessoa
de olho fechado.

---

## O que NÃO dá

**Impulsionar post orgânico do Instagram** pela receita. É outro caminho: exige
o id do post e que a conta do Instagram esteja ligada ao portfólio. O `subir`
cria anúncio novo, não promove publicação existente.

**Público de seguidores.** Não use. Perfil com seguidor comprado — e há mais
deles do que se imagina — transforma o público em lista de gente que nunca vai
comprar, e a campanha entrega para ela porque você mandou.

---

## Medir

O ETL traz Meta e Instagram **juntos**, porque é uma campanha só. Para separar, a
quebra é por `publisher_platform` nos insights. Hoje o ETL não faz essa quebra, e
isso é limitação conhecida, não descuido.

Quando precisar da separação agora:

```bash
python -m magicads get <cliente> <act_...>/insights \
  fields=spend,impressions,actions breakdowns=publisher_platform \
  date_preset=last_7d level=campaign
```

Lembrando que `last_7d` **não inclui hoje**.
