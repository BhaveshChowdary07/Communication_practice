from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from pytz import timezone, utc
from sqlalchemy.exc import OperationalError
import pandas as pd
import secrets
import threading
import os

from app import db
from app.models import User, Test, Section, StudentTestMap, StudentSectionProgress
from app.utils.jwt_utils import generate_access_token, generate_refresh_token, decode_token, jwt_required
from app.utils.email_sender import send_credentials

bp = Blueprint('admin_routes', __name__, url_prefix='/admin')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        admin = User.query.filter_by(email=email, role='admin').first()

        if admin and check_password_hash(admin.password, password):
            access_token = generate_access_token(admin.id, 'admin')
            refresh_token = generate_refresh_token(admin.id)

            response = jsonify({
                'access_token': access_token,
                'refresh_token': refresh_token,
                'redirect_url': url_for('admin_routes.dashboard')
            })
            response.set_cookie('jwt_token', access_token, httponly=True, max_age=3600, samesite='Lax')
            return response

        else:
            return jsonify({'error': 'Invalid credentials'}), 401

    return render_template('login.html')


@bp.route('/logout')
def logout():
    return redirect(url_for('admin_routes.login'))


@bp.route('/dashboard')
@jwt_required(role='admin')
def dashboard():
    admin_id = request.user_id
    admin = User.query.get(admin_id)
    
    tests = Test.query.order_by(Test.id.desc()).all()
    return render_template('admin_dashboard.html', tests=tests, admin=admin)


@bp.route('/create_test', methods=['GET', 'POST'])
@jwt_required(role='admin')
def create_test():
    try:
        sections = Section.query.all()
    except Exception as e:
        flash("⚠️ Could not load sections from database. Please try again later.", "danger")
        print(f"[CREATE_TEST_ERROR] {e}")
        sections = []

    if request.method == 'POST':
        test_name = request.form['test_name']
        test_duration = int(request.form['test_duration'])
        ist = timezone('Asia/Kolkata')
        try:
            start_date_input = request.form['start_date']
            end_date_input = request.form['end_date']
    
            start_date = ist.localize(datetime.strptime(start_date_input, "%Y-%m-%dT%H:%M")).astimezone(utc)
            end_date = ist.localize(datetime.strptime(end_date_input, "%Y-%m-%dT%H:%M")).astimezone(utc)

            if start_date >= end_date:
                flash("⚠️ Start date must be before end date.", "danger")
                return redirect(request.url)

            if end_date <= datetime.utcnow().astimezone(utc):
                flash("⚠️ End date must be in the future.", "danger")
                return redirect(request.url)

        except (ValueError, KeyError):
            flash("⚠️ Invalid date or time format.", "danger")
            return redirect(request.url)

        selected_sections = request.form.getlist('sections')
        if not selected_sections:
            flash("You must select at least one section to create a test.", "danger")
            return redirect(request.url)

        section_ids, num_questions, section_durations = [], [], []

        for sid in selected_sections:
            nq = request.form.get(f'num_questions_{sid}')
            dur = request.form.get(f'section_durations_{sid}')
            if not nq or not dur or int(nq) <= 0 or int(dur) <= 0:
                flash("Each selected section must have a valid number of questions and duration.", "danger")
                return redirect(request.url)

            section_ids.append(sid)
            num_questions.append(str(int(nq)))
            section_durations.append(str(int(dur)))

        test = Test(
            test_name=test_name,
            sections=",".join(section_ids),
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

    admin = User.query.get(request.user_id)
    return render_template('create_test.html', sections=sections, admin=admin)


@bp.route('/assign_test/<int:test_id>', methods=['GET', 'POST'])
@jwt_required(role='admin')
def assign_test(test_id):
    csv_data = None
    try:
        test = db.session.get(Test, test_id)
    except OperationalError:
        flash("Could not load test from database. Please try again later.", "danger")
        return redirect(url_for('admin_routes.dashboard'))

    if request.method == 'GET':
        session.pop('_flashes', None)

    elif request.method == 'POST':
        if 'confirm' in request.form:
            try:
                df = pd.read_csv("temp_upload.csv")
            except FileNotFoundError:
                flash("Temporary upload file not found. Please upload the CSV again.", "danger")
                return redirect(request.url)

            csv_data = df.to_dict(orient='records')
            student_creds = []

            for _, row in df.iterrows():
                name = row['name']
                email = row['email']

                student = User.query.filter_by(email=email, role='student').first()

                if not student:
                    password_plain = secrets.token_urlsafe(6)
                    hashed_pw = generate_password_hash(password_plain)
                    student = User(name=name, email=email, password=hashed_pw, role='student')
                    db.session.add(student)
                    db.session.flush()
                else:
                    existing_map_any = StudentTestMap.query.filter_by(student_id=student.id).first()
                    if existing_map_any and existing_map_any.password:
                        password_plain = existing_map_any.password
                    else:
                        password_plain = secrets.token_urlsafe(6)
                        student.password = generate_password_hash(password_plain)

                existing_map = StudentTestMap.query.filter_by(student_id=student.id, test_id=test_id).first()
                if not existing_map:
                    map_entry = StudentTestMap(
                        student_id=student.id,
                        test_id=test_id,
                        password=password_plain
                    )
                    db.session.add(map_entry)

                student_creds.append((email, password_plain))

            db.session.commit()

            credentials_records = []
            for idx, (email, password) in enumerate(student_creds, start=1):
                name_row = next((r['name'] for r in csv_data if r['email'] == email), '')
                credentials_records.append({
                    'sno': idx,
                    'name': name_row,
                    'email': email,
                    'test_password': password,
                    'test_login_link': "http://practicetests.in/student/login"
                })

            pd.DataFrame(credentials_records).to_csv("credentials_download.csv", index=False)

            flash("Students assigned! You can now download the credentials.", "success")
            return redirect(url_for('admin_routes.dashboard'))

        else:
            file = request.files.get('csv_file')
            if not file:
                flash("No file uploaded", "danger")
                return redirect(request.url)

            df = pd.read_csv(file)
            rows = []

            for index, row in df.iterrows():
                email = row.get('email') or row.get('Email') or row.get('EMAIL')
                if not email:
                    flash(f"Row {index + 2} is missing an email. Skipping.", "danger")
                    continue

                name = row.get('name') or row.get('Name')
                if not name:
                    name = row.get('roll_number') or row.get('Roll Number') or row.get('Roll_Number') or row.get('roll')

                if not name:
                    flash(f"Row {index + 2} has no name or roll number. Skipping.", "danger")
                    continue

                rows.append({
                    'name': str(name).strip(),
                    'email': str(email).strip()
                })

            if not rows:
                flash("No valid rows found in the uploaded CSV. Please check formatting.", "danger")
                return redirect(request.url)

            df = pd.DataFrame(rows)
            df.to_csv("temp_upload.csv", index=False)
            csv_data = df.to_dict(orient='records')
            flash("Preview the test and students below. Click 'Confirm & Assign Test' to continue.", "info")

    admin = User.query.get(request.user_id)
    return render_template("assign_test.html", test_id=test_id, test=test, csv_data=csv_data, admin=admin)


@bp.route('/download_credentials/<int:test_id>')
@jwt_required(role='admin')
def download_credentials(test_id):
    file_path = "credentials_download.csv"
    if not os.path.exists(file_path):
        flash("Credential file not found. Please assign the test first.", "danger")
        return redirect(url_for('admin_routes.assign_test', test_id=test_id))

    return send_file(file_path, as_attachment=True, download_name=f"test_{test_id}_credentials.csv")


@bp.route('/delete_test/<int:test_id>', methods=['POST'])
@jwt_required(role='admin')
def delete_test(test_id):
    StudentSectionProgress.query.filter_by(test_id=test_id).delete()
    StudentTestMap.query.filter_by(test_id=test_id).delete()
    Test.query.filter_by(id=test_id).delete()
    db.session.commit()

    flash("Test deleted successfully.", "success")
    return redirect(url_for('admin_routes.dashboard'))


@bp.route('/refresh_token', methods=['POST'])
def refresh_token():
    token = request.json.get('refresh_token')
    if not token:
        return jsonify({'error': 'Missing refresh token'}), 401

    payload = decode_token(token)
    if not payload or payload.get('type') != 'refresh':
        return jsonify({'error': 'Invalid or expired refresh token'}), 403

    user_id = payload['sub']
    role = 'admin'
    new_access = generate_access_token(user_id, role)

    return jsonify({'access_token': new_access})
