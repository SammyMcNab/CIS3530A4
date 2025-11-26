import psycopg2
from psycopg2 import errors
from flask import Blueprint, render_template, request, redirect, flash, session, url_for, Response
import csv
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

def login_required_admin(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        # If no user_id or not admin, restrict access and send to login page
        if "user_id" not in session or session.get("role") != "admin":
            flash("You must be an admin to access this page.", "danger")
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
    cur.execute("SELECT id, username, password_hash, role FROM user_authentication WHERE username = %s", (username,))
    user = cur.fetchone()

    # Validate password and user existence
    if user is None or not check_password_hash(user[2], password):
        flash("Invalid username or password.", "danger")
        return render_template("login.html")
    
    # Clear session and replace with new login values
    session.clear()
    session["user_id"] = user[0]
    session["username"] = user[1]
    session["role"] = user[3]

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
    role = request.form.get("role")

    # Validate
    if not username or not password or not role:
        flash("Username, password, and role are required.", "danger")
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
    """, (username, password_hash, role))

    # Commit change
    conn.commit()

    return render_template('home.html')

# For searching employees
@main.route('/search')
@login_required
def search():
    # Get query parameters
    selected_dept = request.args.get('department')
    sort_by = request.args.get('sort_by')
    sort_column = request.args.get('sort_column')
    search_name = request.args.get('search_name', '').strip()
    search_pattern = f"%{search_name}%"
    export = request.args.get('export')

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
    query = "SELECT e.Fname, e.Minit, e.Lname, d.Dname, COUNT(DISTINCT dp.Dependent_name) AS num_dependents, COUNT(DISTINCT w.Pno) AS num_projects, COALESCE(SUM(w.Hours), 0) AS total_hours FROM Employee e LEFT JOIN Department d ON e.Dno = d.Dnumber LEFT JOIN Dependent dp ON e.Ssn = dp.Essn LEFT JOIN Works_On w ON e.Ssn = w.Essn WHERE (%s = '' OR (e.Fname || ' ' || REPLACE(e.Minit, '.', '') || ' ' || e.Lname) ILIKE REPLACE(%s, '.', ''))"

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

    if export:
        def generate_csv():
            output = []
            header = ['First Name', 'Middle Initial', 'Last Name', 'Department', 'Num Dependents', 'Num Projects', 'Total Hours']
            output.append(','.join(header))
            for e in employees:
                output.append(','.join([str(item) for item in e]))
            return '\n'.join(output)

        csv_content = generate_csv()

        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=employees.csv"}
        )
    return render_template('search.html', employees=employees)

@main.route('/employees')
@login_required_admin
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
@login_required_admin
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
@login_required_admin
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
# For the A3. Projects Portfolio Summary 
@main.route('/projects')
@login_required
def projects():
    sort_by = request.args.get("sort_by", "headcount")
    order = request.args.get("order", "ASC").upper()
    export = request.args.get('export')

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

        if export:
            def generate_csv():
                output = []
                header = ['Project Name', 'Owning Department', 'Headcount', 'Total Hours']
                output.append(','.join(header))
                for p in projects:
                    output.append(','.join([str(item) for item in p]))
                return '\n'.join(output)

            csv_content = generate_csv()

            return Response(
                csv_content,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment;filename=projects.csv"}
            )

        return render_template("projects.html", projects=projects)

    # Returns an empty projects.html in case of an error
    except Exception as exception:
        print("Error while fetching projects:", exception)
        return render_template("projects.html", projects=[])


# For the A4. Project Details & Assignment "Upsert" component 
# Run with the url extension /project_details_and_upsert/<int:project_id> where project_id is a valid integer relevant to a project from the database 
@main.route("/project_details_and_upsert/<int:project_id>", methods=["GET", "POST"])
@login_required_admin
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

