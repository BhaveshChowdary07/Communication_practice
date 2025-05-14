from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pandas as pd
import secrets

from app import db
from app.models import User, Test, Section, StudentTestMap
from app.utils.email_sender import send_credentials
from app.utils.jwt_utils import generate_token, jwt_required

bp = Blueprint('admin_routes', __name__, url_prefix='/admin')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        admin = User.query.filter_by(email=email, role='admin').first()
        if admin and check_password_hash(admin.password, password):
            token = generate_token(admin.id, 'admin')
            response = make_response(redirect(url_for('admin_routes.dashboard')))
            response.set_cookie('jwt_token', token, httponly=True, samesite='Lax')
            return response
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@bp.route('/logout')
def logout():
    response = make_response(redirect(url_for('admin_routes.login')))
    response.set_cookie('jwt_token', '', expires=0)
    return response

@bp.route('/dashboard')
@jwt_required(role='admin')
def dashboard():
    tests = Test.query.order_by(Test.id.desc()).all()
    return render_template('admin_dashboard.html', tests=tests)

@bp.route('/create_test', methods=['GET', 'POST'])
@jwt_required(role='admin')
def create_test():
    sections = Section.query.all()
    if request.method == 'POST':
        test_name = request.form['test_name']
        # Fetch selected sections and corresponding input data
        selected_sections = request.form.getlist('sections[]')
        num_questions = request.form.getlist('num_questions[]')
        section_durations = request.form.getlist('section_durations[]')

        # ✅ Validate at least one section is selected
        if not selected_sections:
            flash("You must select at least one section to create a test.", "danger")
            return redirect(request.url)

        # ✅ Validate corresponding question counts and durations
        valid_section_data = True
        for i in range(len(selected_sections)):
            try:
                nq = int(num_questions[i])
                dur = int(section_durations[i])
                if nq <= 0 or dur <= 0:
                    valid_section_data = False
                    break
            except (ValueError, IndexError):
                valid_section_data = False
                break

        if not valid_section_data:
            flash("Each selected section must have a valid number of questions and duration.", "danger")
            return redirect(request.url)

        test_duration = int(request.form['test_duration'])
        start_date = datetime.strptime(request.form['start_date'], "%Y-%m-%dT%H:%M")
        end_date = datetime.strptime(request.form['end_date'], "%Y-%m-%dT%H:%M")

        test = Test(
            test_name=test_name,
            sections=",".join(selected_sections),
            num_questions=",".join(num_questions),
            section_durations=",".join(section_durations),
            test_duration=test_duration,
            start_date=start_date,
            end_date=end_date,
            created_by=request.user_id
        )
        db.session.add(test)
        db.session.commit()
        flash("Test created successfully!", "success")
        return redirect(url_for('admin_routes.dashboard'))

    return render_template('create_test.html', sections=sections)

@bp.route('/assign_test/<int:test_id>', methods=['GET', 'POST'])
@jwt_required(role='admin')
def assign_test(test_id):
    from flask import session
    csv_data = None
    test = Test.query.get(test_id)

    # ✅ Clear any leftover flash messages if navigating from dashboard
    if request.method == 'GET':
        session.pop('_flashes', None)

    if request.method == 'POST':
        if 'confirm' in request.form:
            try:
                df = pd.read_csv("temp_upload.csv")
            except FileNotFoundError:
                flash("Temporary upload file not found. Please upload the CSV again.", "danger")
                return redirect(request.url)

            csv_data = df.to_dict(orient='records')

            for _, row in df.iterrows():
                name = row['name']
                email = row['email']

                student = User.query.filter_by(email=email, role='student').first()

                if not student:
                    password = secrets.token_urlsafe(6)
                    hashed_pw = generate_password_hash(password)
                    student = User(name=name, email=email, password=hashed_pw, role='student')
                    db.session.add(student)
                    db.session.flush()
                else:
                    password = None  # Keep old password

                existing_map = StudentTestMap.query.filter_by(student_id=student.id, test_id=test_id).first()

                if not existing_map:
                    map_password = secrets.token_urlsafe(6) if password is None else password
                    map_entry = StudentTestMap(
                        student_id=student.id,
                        test_id=test_id,
                        password=map_password
                    )
                    db.session.add(map_entry)

                    send_credentials(email=email, password=map_password, test_id=test_id)

            db.session.commit()
            flash("Students assigned and emails sent!", "success")
            return redirect(url_for('admin_routes.dashboard'))

        else:
            file = request.files.get('csv_file')
            if not file:
                flash("No file uploaded", "danger")
                return redirect(request.url)

            df = pd.read_csv(file)
            csv_data = df.to_dict(orient='records')
            df.to_csv("temp_upload.csv", index=False)

            flash("Preview the test and students below. Click 'Confirm & Assign Test' to continue.", "info")

    return render_template("assign_test.html", test_id=test_id, test=test, csv_data=csv_data)



@bp.route('/delete_test/<int:test_id>', methods=['POST'])
@jwt_required(role='admin')
def delete_test(test_id):
    # delete from student_test_map
    StudentTestMap.query.filter_by(test_id=test_id).delete()

    # delete the test itself
    Test.query.filter_by(id=test_id).delete()
    db.session.commit()

    flash("Test deleted successfully.", "success")
    return redirect(url_for('admin_routes.dashboard'))
