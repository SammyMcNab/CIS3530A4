from flask import Blueprint, render_template, request, redirect, flash, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os

main = Blueprint('main', __name__)

DB_HOST = 'localhost'
DB_USER = 'postgres'
DB_PASSWORD = 'password123' # SHOULD BE CHANGED TO PASSWORD YOU CONFIGURE
DB_NAME = 'my_company_db'

def get_db_connection():
    import psycopg2
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
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

@main.route('/')
def home():
    return render_template('home.html')

@main.route('/login_page')
def login_page():
    return render_template('login.html')

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

@main.route('/logout')
def logout():
    session.clear()
    return render_template('home.html')

@main.route('/create_account_page')
def create_account_page():
    return render_template('create_account.html')

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

    # Conrimm validity of parameters according to whitelist
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
