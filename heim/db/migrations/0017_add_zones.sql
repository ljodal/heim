-- Add zone concept to separate physical sensors from logical measurement locations
--
-- Zones represent logical locations we want to track over time (e.g., "Living Room").
-- Sensors are physical devices that can be assigned to zones for specific time periods.
-- This allows moving sensors between zones and replacing sensors while maintaining
-- continuous historical data for a zone.

-- Create zone table (logical measurement location)
create table zone (
    id integer primary key generated always as identity,
    location_id integer not null references location(id),
    name text not null,
    is_outdoor boolean not null default false,
    color text,
    unique (location_id, name)
);

-- Create sensor-zone assignment table with time ranges
-- Uses GiST exclusion constraint to prevent overlapping assignments for the same sensor
create table sensor_zone_assignment (
    id integer primary key generated always as identity,
    zone_id integer not null references zone(id),
    sensor_id integer not null references sensor(id),
    active_range tstzrange not null,
    -- Prevent a sensor from being assigned to multiple zones at the same time
    exclude using gist (sensor_id with =, active_range with &&)
);

create index sensor_zone_assignment_zone_id_idx on sensor_zone_assignment(zone_id);
create index sensor_zone_assignment_sensor_id_idx on sensor_zone_assignment(sensor_id);
create index sensor_zone_assignment_active_range_idx on sensor_zone_assignment using gist(active_range);

-- Migrate existing sensors to zones:
-- 1. Create a zone for each existing sensor with the same name, location, is_outdoor, and color
-- 2. Create an assignment from the sensor to the zone, starting from the sensor's first measurement

-- Step 1: Create zones from existing sensors
insert into zone (location_id, name, is_outdoor, color)
select location_id, coalesce(name, 'Sensor ' || id), coalesce(is_outdoor, false), color
from sensor;

-- Step 2: Create assignments from sensors to their corresponding zones
-- The assignment starts from the sensor's first measurement (or now if no measurements)
-- and is open-ended (null upper bound means still active)
insert into sensor_zone_assignment (zone_id, sensor_id, active_range)
select
    z.id as zone_id,
    s.id as sensor_id,
    tstzrange(
        coalesce(
            (select min(measured_at) from sensor_measurement where sensor_id = s.id),
            now()
        ),
        null,
        '[)'
    ) as active_range
from sensor s
join zone z on z.location_id = s.location_id
    and z.name = coalesce(s.name, 'Sensor ' || s.id);

-- Note: We keep sensor.location_id, sensor.is_outdoor, and sensor.color for now
-- to allow gradual migration of code. These columns can be dropped in a future
-- migration once all code uses zones instead.
