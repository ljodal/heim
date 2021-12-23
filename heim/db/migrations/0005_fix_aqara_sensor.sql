alter table aqara_sensor
    drop column id,
    add primary key (sensor_id),
    add column aqara_id varchar not null,
    add unique (aqara_account_id, aqara_id);
