# Fluxo — Google Business (a ficha)

> **A API do GBP não expõe produto.** Post tem endpoint; produto, não.
> Um agente que promete publicar produto na ficha está mentindo, e mentira de
> agente vira promessa para o cliente.

---

## Por que isto está aqui, se não automatiza

Porque **a ficha muda o custo do pago**, e quem só olha o gerenciador nunca vê
isso acontecer.

Quem vê o anúncio procura o nome depois. Se a ficha está vazia, com foto velha ou
com nota 3,2 e nenhuma resposta, o anúncio está pagando para entregar a pessoa
numa vitrine suja. Avaliação e rota custam menos que impressão.

Em conta de **serviço local** e de **balcão**, a ficha é parte da campanha mesmo
quando você só roda Meta.

---

## O tempo aqui é outro

Termo novo na ficha demora da ordem de **dois meses** para aparecer nas buscas.
Isso tem duas consequências práticas:

1. Ficha é trabalho de **mês**, não de sprint.
2. **Medir mudança de ficha em sete dias não mede nada.** Se alguém mostra
   gráfico de sete dias provando que a mudança funcionou, o gráfico está provando
   outra coisa.

E tem a armadilha de sempre: consulta ao GBP devolve `200` com lista vazia quando
não há o que devolver. Igual à Meta sob rate limit, e pela mesma razão você não
pode ler "vazio" como "não existe".

---

## O que o agente entrega

Uma lista, em ordem de impacto, para alguém executar:

1. **Categoria principal certa.** É o que mais move, e é o que mais está errado.
   Categoria secundária ajuda; principal errada derruba o resto.
2. **Horário real**, inclusive feriado. Ficha que diz aberto e está fechada gera
   avaliação de uma estrela por motivo que não é o serviço.
3. **Foto recente**, de dentro, com gente. Fachada de 2019 não responde a
   pergunta que a pessoa está fazendo.
4. **Resposta às avaliações**, principalmente às ruins. Responder a ruim vale
   mais que ganhar uma boa, porque é lida por quem está decidindo.
5. **Serviços e produtos preenchidos** com o vocabulário do cliente, não o
   interno da empresa.
6. **Post** quando houver o que dizer. Post por obrigação semanal não move nada.

O que **não** entra na lista: qualquer coisa que prometa execução automática.

---

## E o que dá para ler

Métrica de GBP não está no ETL. Quando precisar, é pela interface ou pela API de
performance — e a leitura que importa é **ligação, rota e clique no site**, não
impressão.
