from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from pytz import timezone, utc
from sqlalchemy.exc import OperationalError
import pandas as pd
import secrets
import threading

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
    # Redirect handled in frontend by clearing localStorage
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
    sections = Section.query.all()

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
            num_questions.append(str(int(nq)))  # store as stringified int
            section_durations.append(str(int(dur)))  # force valid integer in minutes


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

    # ✅ Defensive test fetch
    try:
        test = db.session.get(Test, test_id)
    except OperationalError:
        flash("Could not load test from database. Please try again later.", "danger")
        return redirect(url_for('admin_routes.dashboard'))

    if request.method == 'GET':
        session.pop('_flashes', None)

    elif request.method == 'POST':
        # ✅ CONFIRM block
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

            # ✅ Background thread to send emails
            def send_bulk_emails(student_data, test_id):
                for email, password in student_data:
                    try:
                        send_credentials(email=email, password=password, test_id=test_id)
                    except Exception as e:
                        print(f"[EMAIL ERROR] Failed to send to {email}: {e}")

            threading.Thread(target=send_bulk_emails, args=(student_creds, test_id)).start()

            flash("Students assigned! Emails are being sent in the background.", "success")
            return redirect(url_for('admin_routes.dashboard'))

        # ✅ CSV upload preview
        else:
            file = request.files.get('csv_file')
            if not file:
                flash("No file uploaded", "danger")
                return redirect(request.url)

            df = pd.read_csv(file)
            csv_data = df.to_dict(orient='records')
            df.to_csv("temp_upload.csv", index=False)
            flash("Preview the test and students below. Click 'Confirm & Assign Test' to continue.", "info")

    admin = User.query.get(request.user_id)
    return render_template("assign_test.html", test_id=test_id, test=test, csv_data=csv_data, admin=admin)

@bp.route('/admin/add-shell-admin')
def add_shell_admin():
    from app.models import User
    from werkzeug.security import generate_password_hash
    existing = User.query.filter_by(email="bhavesh.chowdary@redsage.global").first()
    if existing:
        return "Admin already exists."

    admin = User(
        name="Admin",
        email="bhavesh.chowdary@redsage.global",
        role="admin",
        password=generate_password_hash("admin123")
    )
    db.session.add(admin)
    db.session.commit()
    return "✅ Admin created successfully!"

@bp.route('/delete_test/<int:test_id>', methods=['POST'])
@jwt_required(role='admin')
def delete_test(test_id):
    # Clean up dependent records
    StudentSectionProgress.query.filter_by(test_id=test_id).delete()
    StudentTestMap.query.filter_by(test_id=test_id).delete()

    # Now delete the test
    Test.query.filter_by(id=test_id).delete()
    db.session.commit()

    flash("Test deleted successfully.", "success")
    return redirect(url_for('admin_routes.dashboard'))


@bp.route('/refresh_token', methods=['POST'])
def refresh_token():
    from flask import request, jsonify
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
