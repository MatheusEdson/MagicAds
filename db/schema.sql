-- MagicAds: schema mínimo do operador.
-- Postgres 14+ (roda igual no Supabase free e num Postgres seu).
--
-- Filosofia: 4 tabelas. Nada de RLS, nada de view, nada de trigger.
-- O painel multi-cliente com login precisa de 12 tabelas; o operador não.
-- A coluna `cliente_slug` já existe em tudo pra que abrir pro cliente,
-- um dia, seja adicionar RLS e não refazer o modelo.
--
-- Uso:
--   psql "$DATABASE_URL" -f db/schema.sql
--   (ou cole no SQL Editor do Supabase)

begin;

-- ---------------------------------------------------------------------------
-- 1. carteira
-- ---------------------------------------------------------------------------
create table if not exists clientes (
    slug        text primary key,
    nome        text not null,
    nicho       text,
    cidade      text,
    ativo       boolean     not null default true,
    criado_em   timestamptz not null default now()
);

comment on table clientes is 'Quem você atende. O slug é o que você digita no CLI.';

create table if not exists contas (
    canal        text not null check (canal in ('meta', 'google', 'linkedin')),
    account_id   text not null,
    cliente_slug text not null references clientes (slug) on delete cascade,
    nome         text,
    ativo        boolean     not null default true,
    criado_em    timestamptz not null default now(),
    primary key (canal, account_id)
);

comment on table contas is
    'Uma conta de plataforma. O mesmo cliente pode ter Meta e Google. '
    'account_id é o id cru da plataforma (act_..., o customer id do Google, urn:li:...).';

create index if not exists contas_cliente_idx on contas (cliente_slug) where ativo;

-- ---------------------------------------------------------------------------
-- 2. o fato: uma linha por canal/conta/dia/campanha/criativo
-- ---------------------------------------------------------------------------
create table if not exists metricas (
    canal        text  not null,
    account_id   text  not null,
    data         date  not null,
    campanha     text  not null,
    criativo_id  text  not null default '',   -- '' em vez de null: null quebra unique
    cliente_slug text  not null references clientes (slug) on delete cascade,

    investimento numeric(14, 2) not null default 0,
    impressoes   integer        not null default 0,
    cliques      integer        not null default 0,
    conversas    integer        not null default 0,   -- mensagens iniciadas (CTWA, Messenger)
    conversoes   integer        not null default 0,   -- o resultado que você comprou

    atualizado_em timestamptz not null default now(),

    primary key (canal, account_id, data, campanha, criativo_id)
);

comment on table metricas is
    'A chave primária É a chave de idempotência: rodar o ETL dez vezes no mesmo '
    'dia não duplica nada, e nenhum controle de "já rodei hoje" é necessário.';

create index if not exists metricas_cliente_data_idx on metricas (cliente_slug, data desc);
create index if not exists metricas_data_idx on metricas (data desc);

-- ---------------------------------------------------------------------------
-- 3. criativo (opcional, mas é o que responde "o que está funcionando")
-- ---------------------------------------------------------------------------
create table if not exists criativos (
    canal        text not null,
    account_id   text not null,
    data         date not null,
    ad_id        text not null,
    cliente_slug text not null references clientes (slug) on delete cascade,

    campanha     text,
    nome         text,
    thumb        text,                         -- url da miniatura
    investimento numeric(14, 2) not null default 0,
    impressoes   integer        not null default 0,
    cliques      integer        not null default 0,
    resultados   integer        not null default 0,

    atualizado_em timestamptz not null default now(),

    primary key (canal, account_id, data, ad_id)
);

create index if not exists criativos_cliente_data_idx on criativos (cliente_slug, data desc);

commit;

-- ---------------------------------------------------------------------------
-- Consultas que substituem as views que NÃO foram criadas
-- ---------------------------------------------------------------------------

-- Resumo do mês por cliente:
--
--   select c.nome,
--          sum(m.investimento)                                   as investido,
--          sum(m.conversoes)                                     as resultados,
--          round(sum(m.investimento) / nullif(sum(m.conversoes), 0), 2) as custo_por_resultado
--     from metricas m
--     join clientes c on c.slug = m.cliente_slug
--    where m.data >= date_trunc('month', current_date)
--    group by c.nome
--    order by investido desc;

-- Contas que pararam de reportar (o alarme que importa: conta muda é conta
-- quebrada, e ninguém percebe porque o painel simplesmente mostra zero):
--
--   select ct.canal, ct.account_id, ct.nome, max(m.data) as ultimo_dia
--     from contas ct
--     left join metricas m
--            on m.canal = ct.canal and m.account_id = ct.account_id
--    where ct.ativo
--    group by ct.canal, ct.account_id, ct.nome
--   having max(m.data) is null or max(m.data) < current_date - 2
--    order by ultimo_dia nulls first;

-- Ontem contra a média dos 7 dias anteriores, por campanha:
--
--   with d as (
--     select campanha, data, sum(investimento) inv, sum(conversoes) conv
--       from metricas
--      where cliente_slug = :slug and data >= current_date - 8
--      group by campanha, data
--   )
--   select campanha,
--          sum(inv) filter (where data = current_date - 1) as ontem,
--          round(avg(inv) filter (where data < current_date - 1), 2) as media_7d
--     from d group by campanha order by ontem desc nulls last;
