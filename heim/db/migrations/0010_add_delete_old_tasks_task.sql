-- Schedule the task's next run
with task_id as (
    insert into task (name, arguments, run_at) values ('delete-old-tasks', '{}', now()) returning id
),
-- Create the schedule
schedule_id as (
    insert into scheduled_task (
        name, arguments, expression, is_enabled, next_task_id
    ) values (
        'delete-old-tasks', '{}', '0 0 * * *', true, (select id from task_id)
    ) returning id
)
-- Set which schedule the task comes from
update task set from_schedule_id = (select id from schedule_id) where id = (select id from task_id);
