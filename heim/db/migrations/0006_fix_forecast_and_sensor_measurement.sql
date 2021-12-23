alter table sensor_measurement
    alter column sensor_id set not null;

alter table forecast_instance
    alter column forecast_id set not null;

alter table forecast_value
    alter column forecast_instance_id set not null;
