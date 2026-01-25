/*
 * Table to store running statistics for forecast bias correction.
 *
 * Uses exponentially weighted moving average (EWMA) for statistics:
 * - count: total number of samples seen
 * - mean: exponentially weighted mean of (forecast - observed) errors
 * - var: exponentially weighted variance
 *
 * The bucket encodes: lead_time * 100 + season * 10 + time_of_day
 * Where:
 * - lead_time: 0 (0-6h), 6 (6-12h), 12 (12-24h), 24 (24-48h), 48 (48h+)
 * - season: 0 (winter), 1 (spring), 2 (summer), 3 (fall)
 * - time_of_day: 0 (night), 1 (morning), 2 (afternoon), 3 (evening)
 */
create table forecast_bias_stats (
    id integer primary key generated always as identity,
    location_id integer not null references location (id),
    sensor_id integer not null references sensor (id),
    forecast_id integer not null references forecast (id),
    attribute attribute not null,
    -- Encoded bucket: lead_time * 100 + season * 10 + time_of_day
    bucket integer not null,
    -- EWMA state
    count integer not null default 0,
    mean double precision not null default 0,
    var double precision not null default 0,
    -- Metadata
    last_updated timestamp with time zone not null default now(),
    -- Constraints
    constraint forecast_bias_stats_unique unique (
        location_id, sensor_id, forecast_id, attribute, bucket
    )
);

-- Index for efficient lookups when computing adjusted forecasts
create index forecast_bias_stats_lookup_idx on forecast_bias_stats (
    location_id, forecast_id, attribute
);
