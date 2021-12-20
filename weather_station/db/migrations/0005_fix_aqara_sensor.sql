alter table aqara_sensor
    drop column id,
    add primary key (sensor_id),
    add unique (aqara_account_id, aqara_id);
