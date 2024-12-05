from flask import Flask, request, redirect, url_for, render_template, flash
import mysql.connector

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Used for flash messages

# Database connection
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="4SF22CD036",
    database="kcet_seat_availability"
)
cursor = conn.cursor()

@app.route('/')
def home():
    # Fetch available seats for all colleges and branches
    cursor.execute("""
        SELECT c.college_name, b.branch_name, b.seats_available
        FROM colleges c
        JOIN branches b ON c.college_id = b.college_id
    """)
    seat_data = cursor.fetchall()
    
    # Organize the data in a dictionary for easier access
    available_seats = {}
    for college_name, branch_name, seats in seat_data:
        if college_name not in available_seats:
            available_seats[college_name] = {}
        available_seats[college_name][branch_name] = seats

    return render_template('index.html', available_seats=available_seats)

@app.route('/allocate', methods=['POST'])
def allocate():
    try:
        # Get form data
        student_rank = request.form.get('student_rank', type=int)
        college_preferences = request.form.get('college_preferences', '').split(",")
        branch_preferences = request.form.get('branch_preferences', '').split(",")

        # Ensure valid form data
        if not student_rank or not college_preferences or not branch_preferences:
            flash("Please provide all required fields.", "error")
            return redirect(url_for('home'))

        # Normalize inputs by stripping extra spaces
        college_preferences = [college.strip() for college in college_preferences if college.strip()]
        branch_preferences = [branch.strip() for branch in branch_preferences if branch.strip()]

        if not college_preferences or not branch_preferences:
            flash("College and branch preferences cannot be empty.", "error")
            return redirect(url_for('home'))

        # Check if the student exists
        cursor.execute("SELECT student_id FROM students WHERE student_rank = %s", (student_rank,))
        student = cursor.fetchone()

        if not student:
            # Add student to the database
            cursor.execute(
                "INSERT INTO students (student_rank, preferred_colleges, preferred_branches) VALUES (%s, %s, %s)",
                (student_rank, ','.join(college_preferences), ','.join(branch_preferences))
            )
            conn.commit()
            student_id = cursor.lastrowid
        else:
            student_id = student[0]

        # Loop through preferences and allocate
        allocated = False
        for college in college_preferences:
            cursor.execute("SELECT college_id FROM colleges WHERE college_name = %s", (college,))
            college_result = cursor.fetchone()
            if not college_result:
                continue
            college_id = college_result[0]

            for branch in branch_preferences:
                cursor.execute(
                    "SELECT branch_id, seats_available FROM branches WHERE branch_name = %s AND college_id = %s",
                    (branch, college_id)
                )
                branch_result = cursor.fetchone()

                if branch_result and branch_result[1] > 0:
                    branch_id = branch_result[0]

                    # Update seat availability
                    cursor.execute(
                        "UPDATE branches SET seats_available = seats_available - 1 WHERE branch_id = %s",
                        (branch_id,)
                    )
                    conn.commit()

                    # Insert allocation record
                    cursor.execute(
                        "INSERT INTO allocations (student_id, college_id, branch_id, status) VALUES (%s, %s, %s, %s)",
                        (student_id, college_id, branch_id, 'Allocated')
                    )
                    conn.commit()

                    allocated = True
                    break  # Stop checking further branches once allocated

            if allocated:
                break  # Stop checking further colleges once allocated

        if not allocated:
            flash("No seats available for the provided preferences.", "error")
            return redirect(url_for('home'))

        flash("Allocation successful!", "success")
        return redirect(url_for('home'))

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "error")
        return redirect(url_for('home'))
    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", "error")
        return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)
