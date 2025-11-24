-------------------------------------
--    User Authentication Table    --
-------------------------------------

CREATE TABLE user_authentication (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin','viewer'))
);

-------------------------------------
--      Index Initializations      --
-------------------------------------

CREATE INDEX idx_employee_lname_fname ON Employee(Lname, Fname);

CREATE INDEX idx_project_name ON Project(Pname);
