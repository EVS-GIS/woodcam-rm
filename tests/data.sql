INSERT INTO users (username, password, role)
VALUES
    ('test', 'pbkdf2:sha256:50000$TCI4GzcX$0de171a4f4dac32e3364c7ddc7c14f3e2fa61f2d17574483f7ffbb431b4acb2f', 'viewer'),
    ('other', 'pbkdf2:sha256:50000$kJPKsz6N$d2d4784f1b030a9761f5ccaeeaca413f27f2ecb76d6168407af962ddce849f79', 'administrator');

INSERT INTO stations (common_name, api_name)
VALUES
    ('Ain-Chazey', 'V2942010'),
    ('Station Test', NULL);

INSERT INTO hydrodata (api_name, metric, date_begin_serie, date_end_serie, date_obs, observation)
VALUES
    ('V2942010', 'H', TIMESTAMP '2022-01-26 00:00', TIMESTAMP '2022-01-26 15:00', TIMESTAMP '2022-01-26 14:12', 920.0);

INSERT INTO records (station_id, date_begin_record, date_end_record, host, path)
VALUES
    (1, TIMESTAMP '2022-01-26 15:00', TIMESTAMP '2022-01-26 15:59', '127.0.0.1', '/data/records/15to16.mkv'),
    (1, TIMESTAMP '2022-01-26 16:00', TIMESTAMP '2022-01-26 16:59', '127.0.0.1', '/data/records/16to17.mkv');