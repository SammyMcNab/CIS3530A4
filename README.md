# Project Setup

### 1. Setup Environment
* Ensure you have python and pip installed. You can check with `python --version`, and `pip --version`.
* Run `python3 -m venv .venv` in the terminal. This creates a remote environment.
* Run `source .venv/bin/activate` in the terminal. This connects you to the remote environment.
* Run `pip install -r requirements.txt` in the terminal. This downloads all the needed dependencies for the project.

### 2. Setup Database
* Ensure you have postgresql and postgresql-contrib installed (can be installed with `sudo apt install postgresql postgresql-contrib`).
* Start postgresql by running `sudo systemctl start postgresql` in the terminal. It can be confirmed running with `sudo systemctl status postgresql`.
* Next, swap to the postgres user by running `sudo -i -u postgres` in the terminal.
* Run `createdb my_company_db` to create the database.
* Set a password by first moving into the psql terminal with the command `psql`, then doing `ALTER USER postgres PASSWORD 'yourpassword';`, replacing 'yourpassword' with your preferred password. Run `exit` to leave the query terminal.
* Next, run `export DATABASE_URL="postgresql://postgres:yourpassword@localhost/my_company_db"`, with the 'yourpassword' replaced with your set password.
* Finally, the database can be loaded from the files using the commands `psql -d $DATABASE_URL -f company_v3.02.sql` and `psql -d $DATABASE_URL -f team_setup.sql`.

### 3. Running the Application
* Ensure flask is downloaded with `flask --version`.
* Run `export FLASK_APP="run:create_app"` to set up Flask to run.
* Run `flask run` to start the application.
* The terminal will now provide the host address that the app is on. Go to that address on your preferred browser.

# Index Justification
* The indexes have not been selected at this time.
