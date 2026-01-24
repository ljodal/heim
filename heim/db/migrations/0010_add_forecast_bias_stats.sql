/*
 * Table to store running statistics for forecast bias correction.
 *
 * Uses Welford's algorithm for online mean/variance calculation:
 * - count: number of samples
 * - mean: running mean of (forecast - observed) errors
 * - m2: sum of squared differences from the mean (for variance)
 *
 * Variance = m2 / count
 * Std deviation = sqrt(m2 / count)
 */
create table forecast_bias_stats (
    id integer primary key generated always as identity,
    location_id integer not null references location (id),
    sensor_id integer not null references sensor (id),
    forecast_id integer not null references forecast (id),
    attribute attribute not null,
    -- Lead time bucket in hours (e.g., 0 = 0-6h, 6 = 6-12h, 12 = 12-24h, etc.)
    lead_time_bucket integer not null,
    -- Welford's algorithm state
    count integer not null default 0,
    mean double precision not null default 0,
    m2 double precision not null default 0,
    -- Metadata
    last_updated timestamp with time zone not null default now(),
    -- Constraints
    constraint forecast_bias_stats_unique unique (
        location_id, sensor_id, forecast_id, attribute, lead_time_bucket
    )
);

-- Index for efficient lookups when computing adjusted forecasts
create index forecast_bias_stats_lookup_idx on forecast_bias_stats (
    location_id, forecast_id, attribute
);
