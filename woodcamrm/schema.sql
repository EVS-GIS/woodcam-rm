DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS settings;
DROP TABLE IF EXISTS stations;
DROP TABLE IF EXISTS hydrodata;
DROP TABLE IF EXISTS records;
DROP TABLE IF EXISTS jobs;
DROP TYPE IF EXISTS roles;
DROP TYPE IF EXISTS metrics;
DROP TYPE IF EXISTS job_state;

CREATE TYPE roles AS ENUM ('administrator', 'viewer');
CREATE TYPE metrics AS ENUM ('H', 'Q');
CREATE TYPE job_state AS ENUM ('running', 'warn', 'error', 'stopped');

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role roles NOT NULL,
    notify BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE settings (
    id SERIAL PRIMARY KEY,
    parameter TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL
);

CREATE TABLE stations (
    id SERIAL PRIMARY KEY,
    common_name TEXT UNIQUE NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    api_name TEXT,
    monthly_data INTEGER,
    current_data NUMERIC,
    last_data_check TIMESTAMP,
    reset_day INTEGER,
    phone_number TEXT,
    ip INET,
    mqtt_prefix TEXT,
    last_ping TIMESTAMP,
    last_hydro_time TIMESTAMP,
    last_hydro NUMERIC,
    current_recording TEXT,
    last_record_change TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    jan_threshold NUMERIC,
    feb_threshold NUMERIC,
    mar_threshold NUMERIC,
    apr_threshold NUMERIC,
    may_threshold NUMERIC,
    jun_threshold NUMERIC,
    jul_threshold NUMERIC,
    aug_threshold NUMERIC,
    sep_threshold NUMERIC,
    oct_threshold NUMERIC,
    nov_threshold NUMERIC,
    dec_threshold NUMERIC
);

-- CREATE TABLE hydrodata (
--     id SERIAL PRIMARY KEY,
--     api_name TEXT NOT NULL,
--     metric metrics NOT NULL,
--     date_begin_serie TIMESTAMP,
--     date_obs_elab TIMESTAMP,
--     date_end_serie TIMESTAMP,
--     date_obs TIMESTAMP,
--     date_prod TIMESTAMP,
--     observation NUMERIC,
--     observation_elab NUMERIC
-- );

-- CREATE TABLE records (
--     id SERIAL PRIMARY KEY,
--     station_id INTEGER NOT NULL,
--     date_begin TIMESTAMP,
--     date_end TIMESTAMP,
--     size TEXT,
--     path TEXT NOT NULL,
--     downloaded BOOLEAN NOT NULL DEFAULT FALSE,
--     deleted BOOLEAN NOT NULL DEFAULT FALSE,
--     flagged BOOLEAN NOT NULL DEFAULT FALSE,
--     hydro_min NUMERIC,
--     hydro_max NUMERIC,
--     hydro_mean NUMERIC
-- );

CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    job_name TEXT NOT NULL,
    priority INTEGER NOT NULL,
    full_name TEXT NOT NULL,
    description TEXT,
    last_execution TIMESTAMP,
    state job_state DEFAULT 'warn',
    message TEXT
);