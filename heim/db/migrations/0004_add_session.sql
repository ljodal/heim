create extension if not exists pgcrypto;

create table session (
    key varchar primary key default gen_random_uuid (),
    account_id integer not null references account (id),
    data jsonb not null check (jsonb_typeof(data) = 'object')
);
