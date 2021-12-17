create table task (
    id integer primary key generated always as identity,
    name varchar not null,
    arguments jsonb not null check (jsonb_typeof(arguments) = 'object'),
    run_at timestamp with time zone not null,
    started_at timestamp with time zone,
    finished_at timestamp with time zone
);

create table scheduled_task (
    id integer primary key generated always as identity,
    name varchar not null,
    arguments jsonb not null check (jsonb_typeof(arguments) = 'object'),
    expression varchar not null,
    is_enabled boolean not null,
    next_task_id integer references task (id),
    -- Constraints
    constraint scheduled_task_check_has_next check (next_task_id is not null
        or not is_enabled)
);

alter table task
    add column from_schedule_id integer references scheduled_task (id);
