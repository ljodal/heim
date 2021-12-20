create type aqara_sensor_type as enum (
    'lumi.airmonitor.acn01',
    'lumi.camera.gwag03',
    'lumi.plug.maeu01',
    'lumi.weather.v1'
);

alter table aqara_sensor
    add column sensor_type aqara_sensor_type not null;
