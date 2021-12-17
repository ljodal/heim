/*
 * Account data
 */
create table account (
    id integer primary key generated always as identity,
    username varchar not null unique,
    password varchar not null
);

create table location (
    id integer primary key generated always as identity,
    account_id integer not null references account (id),
    name varchar not null
);


/*
 * Sensor and forecast data
 */
create table sensor (
    id integer primary key generated always as identity,
    account_id integer not null references account (id),
    location_id integer not null references location (id),
    name varchar
);

create table forecast (
    id integer primary key generated always as identity,
    account_id integer not null references account (id),
    location_id integer not null references location (id),
    name varchar
);

create table forecast_instance (
    id integer primary key generated always as identity,
    forecast_id integer references forecast (id),
    created_at timestamp with time zone not null,
    -- Constraints
    constraint forecast_instance_unique unique (forecast_id, created_at)
);

create type attribute as enum (
    'air temperature',
    'air temperature min',
    'air temperature max',
    'humidity',
    'air pressure',
    'cloud cover',
    'cloud cover low',
    'cloud cover medium',
    'cloud cover high',
    'precipitation amount',
    'precipitation amount min',
    'precipitation amount max',
    'energy',
    'power'
);

create table sensor_measurement (
    sensor_id integer references sensor (id),
    attribute attribute not null,
    measured_at timestamp with time zone not null,
    value integer not null,
    -- Constraints
    constraint sensor_measurement_unique unique (sensor_id, attribute, measured_at)
);

create table forecast_value (
    forecast_instance_id integer references forecast_instance (id),
    attribute attribute not null,
    measured_at timestamp with time zone not null,
    value integer not null,
    -- Constraints
    constraint forecast_value_unique unique (forecast_instance_id, attribute, measured_at)
);


/*
 * Aqara integration
 */
create table aqara_account (
    id integer primary key generated always as identity,
    account_id integer not null references account (id),
    username varchar not null unique,
    access_token varchar not null,
    refresh_token varchar not null,
    expires_at timestamp with time zone not null
);

create table aqara_sensor (
    id varchar primary key,
    aqara_account_id integer not null references aqara_account (id),
    sensor_id integer not null references sensor (id),
    name varchar not null
);


/*
 * Yr integration
 */
create table yr_forecast (
    name varchar not null,
    account_id integer not null references account (id),
    forecast_id integer not null references forecast (id) unique,
    coordinate point not null,
    last_update timestamp with time zone,
    next_update timestamp with time zone
);
