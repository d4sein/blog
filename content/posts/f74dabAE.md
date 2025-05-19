---
title: Designing a database interface with postgres schemas
date: 2025-05-18T04:56:12-03:00
lastmod: 2025-05-18T04:56:12-03:00
author: Willian Nascimento

description: In this post I describe how I designed a database interface using postgres schemas and functions
categories: [Programming]
tags: [English]

draft: false
---

![](/../imgs/Military-Art-Italy-097.jpg)

I'm currently working on a project — a highly customizable logbook with analytics tools — and part of the design process was defining the communication between my app and the database.

I wanted to apply some ideas I've been cooking for a while and that I don't see very often in the industry, that is using schemas for separation of concerns and functions for the contracts. This setup provides a clear interface while omitting implementation details, *which is what we do in everything else, right?*

> Disclaimer: This concept is nothing new and PostgREST offers a similar solution.

First, I created my schemas, the `app_user` role, and set the permissions. My current setup has four custom schemas, each with a specific responsibility:
- `core` is where all tables related to the business are created; the heart of the database.
- `api` is where all functions related to the interface are created; effectively, this is the only schema my `app_user` can see.
- `internal` is where I usually keep utility functions.
- `checks` is a nice way to organize validation functions that return a Boolean; those can be used for business validation inside a function, or in a check constraint.

```sql
BEGIN;

-- Create the four core schemas
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS api;
CREATE SCHEMA IF NOT EXISTS internal;
CREATE SCHEMA IF NOT EXISTS checks;

-- Replace 'supersecurepassword' with your real secret
CREATE ROLE app_user LOGIN PASSWORD 'supersecurepassword';

-- Revoke ALL access from PUBLIC (i.e., all users) on all custom schemas
REVOKE ALL ON SCHEMA core, api, internal, checks FROM PUBLIC;

-- Revoke all privileges on tables and functions (applies to existing objects)
REVOKE ALL ON ALL TABLES IN SCHEMA core, internal, api, checks FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA core, internal, api, checks FROM PUBLIC;

---------------------------------------------------------------------------------
GRANT USAGE ON SCHEMA api TO app_user;

-- One-off grants for existing objects
GRANT SELECT
  ON ALL TABLES IN SCHEMA api
  TO app_user;

GRANT EXECUTE
  ON ALL FUNCTIONS IN SCHEMA api
  TO app_user;

-- Default privileges for future objects
-- Obs: you should have a user with privileges such as api_owner for this.
ALTER DEFAULT PRIVILEGES FOR ROLE api_owner
  IN SCHEMA api
  GRANT SELECT ON TABLES TO app_user;

ALTER DEFAULT PRIVILEGES FOR ROLE api_owner
  IN SCHEMA api
  GRANT EXECUTE ON FUNCTIONS TO app_user;

COMMIT;

```

With this setup, I then proceeded to create internal functions like a snowflake_id generator, and the tables for the system.
```sql
BEGIN;

-- I'm omitting the def of generate_snowflake_id
-- and workout table for the sake of brevity
CREATE TABLE core.exercise (
    exercise_id BIGINT DEFAULT internal.generate_snowflake_id() PRIMARY KEY,
	workout_id BIGINT NOT NULL REFERENCES core.workout(workout_id) ON DELETE CASCADE,
    exercise_name VARCHAR(100) NOT NULL
);

COMMIT;
```

You could add the schema names to the global `search_path`, but I prefer to fully qualify them; it makes it easier to identify which schema each component belongs to.

For the API, I created functions for the operations I needed on a given resource.
```sql
BEGIN;

-- API/CREATE_EXERCISE
CREATE OR REPLACE FUNCTION api.create_exercise(
  p_workout_id     BIGINT,
  p_exercise_name  TEXT
)
RETURNS BIGINT
LANGUAGE sql
SECURITY DEFINER
VOLATILE
SET search_path = api, core, pg_temp
AS $$
  INSERT INTO core.exercise (workout_id, exercise_name)
  VALUES (p_workout_id, p_exercise_name)
  RETURNING exercise_id;
$$;

-- API/GET_EXERCISE_LIST
CREATE OR REPLACE FUNCTION api.get_exercise_list(
  p_workout_id BIGINT
)
RETURNS TABLE (
  exercise_id   BIGINT,
  exercise_name TEXT
)
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = api, core, pg_temp
AS $$
  SELECT exercise_id, exercise_name
  FROM core.exercise
  WHERE workout_id = p_workout_id;
$$;

COMMIT;
```

And that's it! Now I have a clean interface that my application can consume from, which doesn't leak any implementation details, improves code versioning, facilitates changes to business rules in real time, and has a safer environment for production.

Important notes:
- `SECURITY DEFINER` specifies that the function is to be executed with the privileges of the user that owns it, which is necessary for functions to access other schemas. Read it more here on how to do this safely: https://www.postgresql.org/docs/current/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY
- Read functions can be `STABLE`; write functions must be `VOLATILE`.
- If you update your tables, the functions will not update automatically. You might want to look into migration tools like Flyway to mitigate this problem.