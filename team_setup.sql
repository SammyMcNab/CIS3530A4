-------------------------------------
--    User Authentication Table    --
-------------------------------------

CREATE TABLE user_authentication (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin','viewer'))
)

