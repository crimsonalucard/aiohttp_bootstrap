CREATE DATABASE neptune;

CREATE TABLE users (
  id   SERIAL PRIMARY KEY,
  name TEXT,
  dob  DATE
)