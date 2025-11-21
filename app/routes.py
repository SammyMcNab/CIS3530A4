# Some code was adapted from the some examples for SQL execution, etc from the Flask_PostgreSQL_Project_update1 slides
from flask import Blueprint, render_template, request, redirect, url_for, flash
import psycopg2

main = Blueprint('main', __name__, template_folder="templates")

# Database configurations to establish a successful connection later in this app.
DATABASE_CONFIGURATION = {
    "dbname": "my_company_db", # For the database name (change accordingly)
    "user": "postgres", # For the user name
    "password": "your_password", # For the database password (change accordingly)
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

# For the home page 
@main.route('/')
def home():
    return render_template('home.html')

# For the login page
@main.route('/login')
def login():
    return render_template('login.html')

# For the create account page
@main.route('/create_account')
def create_account():
    return render_template('create_account.html')

# For the A3. Projects Portfolio Summary 
@main.route('/projects')
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

