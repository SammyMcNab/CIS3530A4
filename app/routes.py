import psycopg2
from psycopg2 import errors
from flask import Blueprint, render_template, request, redirect, flash, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os

main = Blueprint('main', __name__)

DB_HOST = 'localhost'
DB_USER = 'postgres'
DB_PASSWORD = 'sAmmySaM)(2' # SHOULD BE CHANGED TO PASSWORD YOU CONFIGURE
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

@main.route('/employees')
@login_required
def employee_list():
    """A5: Employee list page (basic info + links for CRUD)."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT e.Ssn,
               e.Fname,
               e.Minit,
               e.Lname,
               d.Dname,
               e.Address,
               e.Salary
        FROM Employee e
        LEFT JOIN Department d ON e.Dno = d.Dnumber
        ORDER BY e.Lname, e.Fname;
    """)
    employees = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('employee_list.html', employees=employees)

@main.route('/employees/add', methods=['GET', 'POST'])
@login_required
def add_employee():
    conn = get_db_connection()
    cur = conn.cursor()

    # Get department list for dropdown
    cur.execute("SELECT Dnumber, Dname FROM Department ORDER BY Dname;")
    departments = cur.fetchall()

    if request.method == 'POST':
        fname = request.form.get('fname', '').strip()
        minit = request.form.get('minit', '').strip()
        lname = request.form.get('lname', '').strip()
        ssn   = request.form.get('ssn', '').strip()
        address = request.form.get('address', '').strip()
        sex   = request.form.get('sex', '').strip()
        salary = request.form.get('salary', '').strip()
        super_ssn = request.form.get('super_ssn', '').strip() or None
        dno = request.form.get('dno', '').strip()
        bdate = request.form.get('bdate') or None
        empdate = request.form.get('empdate') or None

        # Basic validation
        if not (fname and minit and lname and ssn and address and sex and salary and dno):
            flash("All fields except Supervisor SSN, Birth Date, and Employment Date are required.", "danger")
            return render_template('add_employee.html', departments=departments)

        try:
            salary_int = int(salary)
        except ValueError:
            flash("Salary must be a valid integer.", "danger")
            return render_template('add_employee.html', departments=departments)

        try:
            cur.execute("""
                INSERT INTO Employee (Fname, Minit, Lname, Ssn, Address, Sex, Salary, Super_ssn, Dno, BDate, EmpDate)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (fname, minit, lname, ssn, address, sex, salary_int, super_ssn, dno, bdate, empdate))

            conn.commit()
            flash("Employee added successfully.", "success")
            return redirect(url_for('main.employee_list'))

        except errors.UniqueViolation:
            conn.rollback()
            flash("SSN already exists. Please use a unique SSN.", "danger")
            return render_template('add_employee.html', departments=departments)

        except errors.ForeignKeyViolation:
            conn.rollback()
            flash("Invalid Department or Supervisor SSN (foreign key violation).", "danger")
            return render_template('add_employee.html', departments=departments)

        except Exception as e:
            conn.rollback()
            flash(f"Error adding employee: {str(e)}", "danger")
            return render_template('add_employee.html', departments=departments)

        finally:
            cur.close()
            conn.close()

    # GET request
    cur.close()
    conn.close()
    return render_template('add_employee.html', departments=departments)


@main.route('/employees/edit/<ssn>', methods=['GET', 'POST'])
@login_required
def edit_employee(ssn):
    conn = get_db_connection()
    cur = conn.cursor()

    # Get department list
    cur.execute("SELECT Dnumber, Dname FROM Department ORDER BY Dname;")
    departments = cur.fetchall()

    if request.method == 'POST':
        address = request.form.get('address', '').strip()
        salary = request.form.get('salary', '').strip()
        dno = request.form.get('dno', '').strip()

        if not (address and salary and dno):
            flash("Address, Salary, and Department are required.", "danger")
            return redirect(url_for('main.edit_employee', ssn=ssn))

        try:
            salary_int = int(salary)
        except ValueError:
            flash("Salary must be a valid integer.", "danger")
            return redirect(url_for('main.edit_employee', ssn=ssn))

        try:
            cur.execute("""
                UPDATE Employee
                SET Address = %s,
                    Salary = %s,
                    Dno = %s
                WHERE Ssn = %s
            """, (address, salary_int, dno, ssn))

            conn.commit()
            flash("Employee updated successfully.", "success")
            return redirect(url_for('main.employee_list'))

        except errors.ForeignKeyViolation:
            conn.rollback()
            flash("Invalid Department (foreign key violation).", "danger")
            return redirect(url_for('main.edit_employee', ssn=ssn))

        except Exception as e:
            conn.rollback()
            flash(f"Error updating employee: {str(e)}", "danger")
            return redirect(url_for('main.edit_employee', ssn=ssn))

        finally:
            cur.close()
            conn.close()

    # GET: fetch employee info
    cur.execute("""
        SELECT Fname, Minit, Lname, Ssn, Address, Salary, Dno
        FROM Employee
        WHERE Ssn = %s
    """, (ssn,))
    emp = cur.fetchone()

    cur.close()
    conn.close()

    if emp is None:
        flash("Employee not found.", "danger")
        return redirect(url_for('main.employee_list'))

    return render_template('edit_employee.html', emp=emp, departments=departments)


@main.route('/employees/delete/<ssn>', methods=['POST'])
@login_required
def delete_employee(ssn):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("DELETE FROM Employee WHERE Ssn = %s", (ssn,))
        conn.commit()

        if cur.rowcount == 0:
            flash("Employee not found.", "danger")
        else:
            flash("Employee deleted successfully.", "success")

    except errors.ForeignKeyViolation:
        conn.rollback()
        return redirect(
            url_for('main.employee_list', error="delete_failed")
        )
        #conn.rollback()
        #flash(
        #    "Cannot delete employee: They are still assigned to projects, "
        #    "have dependents listed, or are a manager/supervisor.",
        #    "danger"
        #)

    except Exception as e:
        conn.rollback()
        flash(f"Error deleting employee: {str(e)}", "danger")

    finally:
        cur.close()
        conn.close()

    return redirect(url_for('main.employee_list'))

@main.route('/managers_overview')
@login_required
def managers_overview():
    """A6: High-level overview of all departments with manager, headcount, and total hours."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            d.Dnumber,
            d.Dname,
            -- Manager full name (may be NULL if no manager)
            e_mgr.Fname,
            e_mgr.Minit,
            e_mgr.Lname,

            -- DISTINCT employee count in the department
            COUNT(DISTINCT e_emp.Ssn) AS employee_count,

            -- Total hours worked by employees in this department across all projects
            COALESCE(SUM(w.Hours), 0) AS total_hours
        FROM Department d
        LEFT JOIN Employee e_mgr
            ON e_mgr.Ssn = d.Mgr_ssn             -- manager
        LEFT JOIN Employee e_emp
            ON e_emp.Dno = d.Dnumber             -- employees in department
        LEFT JOIN Works_On w
            ON w.Essn = e_emp.Ssn                -- hours for those employees
        GROUP BY
            d.Dnumber, d.Dname,
            e_mgr.Fname, e_mgr.Minit, e_mgr.Lname
        ORDER BY d.Dnumber;
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('managers_overview.html', departments=rows)
