-- 注册 timescaledb 插件
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- PostgreSQL 相关表
CREATE TABLE IF NOT EXISTS seat(
    seat_id INT NOT NULL,
    name VARCHAR(32) NOT NULL,
    last_login_time TIMESTAMPTZ,
    portrait BYTEA,
    PRIMARY KEY (seat_id)
);

CREATE TABLE IF NOT EXISTS chat(
    chat_id SERIAL NOT NULL,
    title VARCHAR(64),
    time DATE,
    PRIMARY KEY (chat_id)
);

CREATE TABLE IF NOT EXISTS message(
    chat_id INT NOT NULL,
    sequence INT NOT NULL,
    content JSONB NOT NULL,
    PRIMARY KEY (chat_id, sequence),
    FOREIGN KEY (chat_id) REFERENCES chat(chat_id) ON DELETE CASCADE
);

-- timescaledb

CREATE TABLE IF NOT EXISTS state(
    seat_id INT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    heart_rate INT,
    emo_v DOUBLE PRECISION,
    emo_a DOUBLE PRECISION,
    pose_0 DOUBLE PRECISION,
    pose_1 DOUBLE PRECISION,
    pose_2 DOUBLE PRECISION,
    ear DOUBLE PRECISION,
    mar DOUBLE PRECISION,
    label VARCHAR(16),
    eye_close_freq INT,
    iris_ratio_x DOUBLE PRECISION,
    iris_ratio_y DOUBLE PRECISION,
    PRIMARY KEY (seat_id, timestamp),
    FOREIGN KEY (seat_id) REFERENCES seat(seat_id)
) WITH (
  tsdb.hypertable
);

CREATE TYPE ALERT_LEVEL AS ENUM ('低', '中', '高', '严重');

CREATE TABLE IF NOT EXISTS alert(
    seat_id INT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    summary VARCHAR,
    level ALERT_LEVEL,
    -- base ENUM(),
    base VARCHAR(64),
    settled BOOLEAN,
    reason TEXT,
    suggestion TEXT,    
    video VARCHAR(128),
    tag JSONB,
    PRIMARY KEY (seat_id, timestamp),
    FOREIGN KEY (seat_id) REFERENCES seat(seat_id)
) WITH (
  tsdb.hypertable
);