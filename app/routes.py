# Some code was adapted from some examples from the Flask_PostgreSQL_Project_update1 slides from class
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import psycopg2

main = Blueprint('main', __name__, template_folder="templates")

# Database configurations to establish a successful connection later in this app.
DATABASE_CONFIGURATION = {
    "dbname": "my_company_db", # For the database name 
    "user": "postgres", # For the user name
    "password": "password123", # For the database password (change to your configured password)
    "host": "localhost", # For the host
    "port": 5432 # Default port number
}

# Whitelist for safe sorting
PROJECT_SORT_WHITELIST = ["headcount", "total_hours"]
ORDER_WHITELIST = ["ASC", "DESC"]

# To establish a database connection
def get_db_connection():
    conn = psycopg2.connect(**DATABASE_CONFIGURATION)
    return conn

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        # If no user_id, restrict access and send to login page
        if "user_id" not in session:
            flash("You must be logged in to access this page.", "danger")
            return redirect(url_for("main.login_page"))
        return view(*args, **kwargs)
    return wrapped_view

# For the home page 
@main.route('/')
def home():
    return render_template('home.html')

# For the login page
@main.route('/login_page')
def login_page():
    return render_template('login.html')

# For the login page logic
@main.route('/login', methods=["POST"])
def login():
    # Get parameters
    username = request.form.get("username", "").strip()
    password = request.form.get("password")

    # Validate
    if not username or not password:
        flash("Username and password are required.", "danger")
        return render_template('login.html')

    # Connect to database
    conn = get_db_connection()
    cur = conn.cursor()

    # Run query
    cur.execute("SELECT id, username, password_hash FROM user_authentication WHERE username = %s", (username,))
    user = cur.fetchone()

    # Validate password and user existence
    if user is None or not check_password_hash(user[2], password):
        flash("Invalid username or password.", "danger")
        return render_template("login.html")
    
    # Clear session and replace with new login values
    session.clear()
    session["user_id"] = user[0]
    session["username"] = user[1]
    return redirect(url_for("main.search"))

# For the logout page
@main.route('/logout')
def logout():
    session.clear()
    return render_template('home.html')

# For the create account page
@main.route('/create_account_page')
def create_account_page():
    return render_template('create_account.html')

# For the logic behind creating a new account 
@main.route('/create_account', methods=["POST"])
def create_new_account():
    # Get parameters
    username = request.form.get("username", "").strip()
    password = request.form.get("password")

    # Validate
    if not username or not password:
        flash("Username and password are required.", "danger")
        return render_template('create_account.html')

    # Get the hashed password
    password_hash = generate_password_hash(password)

    # Connect to database
    conn = get_db_connection()
    cur = conn.cursor()

    # Check if username already exists
    cur.execute("SELECT id FROM user_authentication WHERE username = %s", (username,))
    existing = cur.fetchone()

    # If account username already exists
    if existing:
        flash("Username already exists.", "danger")
        return render_template('create_account.html')

    # Insert new user
    cur.execute("""
        INSERT INTO user_authentication (username, password_hash, role)
        VALUES (%s, %s, %s)
        RETURNING id
    """, (username, password_hash, "viewer"))

    # Commit change
    conn.commit()

    return render_template('home.html')


@main.route('/search')
@login_required
def search():
    # Get query parameters
    selected_dept = request.args.get('department')
    sort_by = request.args.get('sort_by')
    sort_column = request.args.get('sort_column')
    search_name = request.args.get('search_name', '').strip()
    search_pattern = f"%{search_name}%"

    # Whitelist
    allowed_sort_columns = ['e.Lname', 'total_hours']
    allowed_sort_orders = ['asc', 'desc']

    # Confirm validity of parameters according to whitelist
    if sort_column not in allowed_sort_columns:
        sort_column = 'e.Lname'
    
    if sort_by not in allowed_sort_orders:
        sort_by = 'asc'

    # Get connection and start forming query
    conn = get_db_connection()
    cur = conn.cursor()
    query = "SELECT e.Fname, e.Minit, e.Lname, d.Dname, COUNT(DISTINCT dp.Dependent_name) AS num_dependents, COUNT(DISTINCT w.Pno) AS num_projects, COALESCE(SUM(w.Hours), 0) AS total_hours FROM Employee e LEFT JOIN Department d ON e.Dno = d.Dnumber LEFT JOIN Dependent dp ON e.Ssn = dp.Essn LEFT JOIN Works_On w ON e.Ssn = w.Essn WHERE (%s = '' OR e.Fname || ' ' || e.Lname ILIKE %s)"

    params = [search_name, search_pattern]

    # If a department is selected, add to query
    if selected_dept and selected_dept != 'All Departments':
        query += " AND d.Dname = %s"
        params.append(selected_dept)

    # Finalize query
    query += " GROUP BY e.Fname, e.Minit, e.Lname, d.Dname"
    query += f" ORDER BY {sort_column} {sort_by.upper()};"

    # Execute query and create template with responses
    cur.execute(query, params)
    employees = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('search.html', employees=employees)


# For the A3. Projects Portfolio Summary 
@main.route('/projects')
@login_required
def projects():
    sort_by = request.args.get("sort_by", "headcount")
    order = request.args.get("order", "ASC").upper()

    # Establishes the order by checks based on the whitelist (to sort by total hours by ASCending order or sorting by headcount)
    if order not in ORDER_WHITELIST:
        order = "ASC"
    if sort_by not in PROJECT_SORT_WHITELIST:
        sort_by = "headcount"

    try:
        # Establishes the connection
        connection = get_db_connection()
        cursor = connection.cursor() 

        # Selects the relevant data (from the database) satisfying the following SQL expression below
        cursor.execute(f"""
            SELECT p.Pnumber, p.Pname, d.Dname AS owning_department,
                   COUNT(DISTINCT w.Essn) AS headcount,
                   COALESCE(SUM(w.Hours), 0) AS total_hours
            FROM Project p
            LEFT JOIN Works_On w ON w.Pno = p.Pnumber
            LEFT JOIN Employee e ON e.Ssn = w.Essn
            JOIN Department d ON d.Dnumber = p.Dnum
            GROUP BY p.Pnumber, p.Pname, d.Dname
            ORDER BY {sort_by} {order}
        """)
        # Fetches all relevant projects
        projects = cursor.fetchall()

        # Closes the connection with the database
        cursor.close()
        connection.close()

        return render_template("projects.html", projects=projects)

    # Returns an empty projects.html in case of an error
    except Exception as exception:
        print("Error while fetching projects:", exception)
        return render_template("projects.html", projects=[])


# For the A4. Project Details & Assignment "Upsert" component 
# Run with the url extension /project_details_and_upsert/<int:project_id> where project_id is a valid integer relevant to a project from the database 
@main.route("/project_details_and_upsert/<int:project_id>", methods=["GET", "POST"])
@login_required
def project_details(project_id):
    try:
        # Establishes the connection with the database
        connection = get_db_connection()
        cursor = connection.cursor() 

        # Specific project details
        cursor.execute("""
            SELECT p.Pnumber, p.Pname, d.Dname
            FROM Project p
            JOIN Department d ON d.Dnumber = p.Dnum
            WHERE p.Pnumber = %s
        """, (project_id,))
        project = cursor.fetchone()

        # For the relevant employees on this project 
        cursor.execute("""
            SELECT e.Ssn, e.Fname, e.Lname, w.Hours
            FROM Works_On w
            JOIN Employee e ON e.Ssn = w.Essn
            WHERE w.Pno = %s
        """, (project_id,))
        assignments = cursor.fetchall()

        # For the dropdown list for the Select Employee component
        cursor.execute("SELECT Ssn, Fname, Lname FROM Employee ORDER BY Lname")
        employees = cursor.fetchall()

        if request.method == "POST":
            employee = request.form.get("employee_id")
            hours = request.form.get("hours")

            # If the employee is on the project already, this will update their hours from the specified hours input. This new value will be added onto the employee's old hours. 
            # If the employee isn't on the project yet, this will insert them to it with their updated hours. 
            cursor.execute("""
                INSERT INTO Works_On (Essn, Pno, Hours)
                VALUES (%s, %s, %s)
                ON CONFLICT (Essn, Pno)
                DO UPDATE SET Hours = Works_On.Hours + EXCLUDED.Hours
            """, (employee, project_id, hours))

            connection.commit()

            return redirect(url_for('main.project_details', project_id=project_id))

        # Closes the connection with the database 
        cursor.close()
        connection.close()

        return render_template(
            "project_details_and_upsert.html",
            project=project,
            assignments=assignments,
            employees=employees
        )

    # Redirects to main.projects in case there's an error
    except Exception as exception:
        print("Error:", exception)
        return redirect(url_for("main.projects"))

