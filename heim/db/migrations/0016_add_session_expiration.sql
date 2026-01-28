-- Add expiration timestamp to sessions
alter table session add column expires_at timestamptz;

-- Set a default expiration for existing sessions (30 days from now)
update session set expires_at = now() + interval '30 days';

-- Make the column required
alter table session alter column expires_at set not null;

-- Add index for efficient cleanup of expired sessions
create index session_expires_at_idx on session (expires_at);
