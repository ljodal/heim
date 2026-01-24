/*
 * Netatmo weather station integration
 */

-- Add new attribute types for Netatmo-specific sensors
alter type attribute add value 'co2';
alter type attribute add value 'noise';

-- Netatmo module types
create type netatmo_module_type as enum (
    'NAMain',      -- Indoor base station
    'NAModule1',   -- Outdoor module
    'NAModule2',   -- Wind gauge
    'NAModule3',   -- Rain gauge
    'NAModule4'    -- Additional indoor module
);

-- Netatmo account credentials
create table netatmo_account (
    id integer primary key generated always as identity,
    account_id integer not null references account (id),
    access_token varchar not null,
    refresh_token varchar not null,
    expires_at timestamp with time zone not null,
    -- Constraints
    constraint netatmo_account_unique_account unique (account_id)
);

-- Netatmo sensors (modules)
create table netatmo_sensor (
    sensor_id integer primary key references sensor (id),
    netatmo_account_id integer not null references netatmo_account (id),
    name varchar not null,
    module_type netatmo_module_type not null,
    netatmo_id varchar not null,       -- Module MAC address
    station_id varchar not null,        -- Parent station MAC address
    -- Constraints
    constraint netatmo_sensor_unique_module unique (netatmo_account_id, netatmo_id)
);
