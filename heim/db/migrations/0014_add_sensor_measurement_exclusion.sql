create table sensor_measurement_exclusion (
    id integer primary key generated always as identity,
    sensor_id integer not null references sensor(id),
    excluded tstzrange not null
);

create index sensor_measurement_exclusion_sensor_id_idx
    on sensor_measurement_exclusion(sensor_id);
