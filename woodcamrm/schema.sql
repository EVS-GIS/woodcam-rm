DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS settings;
DROP TABLE IF EXISTS stations;
DROP TABLE IF EXISTS hydrodata;
DROP TABLE IF EXISTS records;

DROP TYPE IF EXISTS roles;
DROP TYPE IF EXISTS metrics;

CREATE TYPE roles AS ENUM ('administrator', 'viewer');
CREATE TYPE metrics AS ENUM ('H', 'Q');

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
    reset_day INTEGER,
    phone_number TEXT,
    ip TEXT,
    proxy TEXT
);

CREATE TABLE hydrodata (
    id SERIAL PRIMARY KEY,
    api_name TEXT NOT NULL,
    metric metrics NOT NULL,
    date_begin_serie TIMESTAMP,
    date_obs_elab TIMESTAMP,
    date_end_serie TIMESTAMP,
    date_obs TIMESTAMP,
    date_prod TIMESTAMP,
    observation NUMERIC,
    observation_elab NUMERIC
);

CREATE TABLE records (
    id SERIAL PRIMARY KEY,
    station_id INTEGER NOT NULL,
    date_begin_record TIMESTAMP,
    date_end_record TIMESTAMP,
    host TEXT NOT NULL,
    path TEXT NOT NULL,
    downloaded BOOLEAN NOT NULL DEFAULT FALSE,
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    flagged BOOLEAN NOT NULL DEFAULT FALSE
);