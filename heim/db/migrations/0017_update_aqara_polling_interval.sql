-- Update Aqara sensor polling from every 5 minutes to every 10 minutes
update scheduled_task
set expression = '*/10 * * * *'
where name = 'update-aqara-sensor-data'
  and expression = '*/5 * * * *';
