/*
 * Easee EV charger integration
 */

-- Add new attribute types for EV charging data
alter type attribute add value 'current';
alter type attribute add value 'voltage';

-- Easee account credentials
create table easee_account (
    id integer primary key generated always as identity,
    account_id integer not null references account (id),
    username varchar not null,
    access_token varchar not null,
    refresh_token varchar not null,
    expires_at timestamp with time zone not null,
    -- Constraints
    constraint easee_account_unique_account unique (account_id)
);

-- Easee chargers
create table easee_charger (
    sensor_id integer primary key references sensor (id),
    easee_account_id integer not null references easee_account (id),
    name varchar not null,
    charger_id varchar not null,  -- Easee charger serial number
    -- Constraints
    constraint easee_charger_unique unique (easee_account_id, charger_id)
);
