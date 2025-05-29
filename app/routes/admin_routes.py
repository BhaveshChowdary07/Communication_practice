from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, send_file, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from pytz import timezone, utc
from sqlalchemy.exc import OperationalError
import pandas as pd
import secrets
import os
from pathlib import Path

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
            flash("Invalid credentials", "danger")
            return redirect(request.url)

    session.pop('_flashes', None)
    return render_template('login.html')


@bp.route('/logout')
def logout():
    return redirect(url_for('admin_routes.login'))


@bp.route('/dashboard')
@jwt_required(role='admin')
def dashboard():
    admin = User.query.get(request.user_id)
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
        ist = timezone('Asia/Kolkata')
        try:
            start_date = ist.localize(datetime.strptime(request.form['start_date'], "%Y-%m-%dT%H:%M")).astimezone(utc)
            end_date = ist.localize(datetime.strptime(request.form['end_date'], "%Y-%m-%dT%H:%M")).astimezone(utc)
            if start_date >= end_date:
                flash("⚠️ Start date must be before end date.", "danger")
                return redirect(request.url)
            if end_date <= datetime.utcnow().astimezone(utc):
                flash("⚠️ End date must be in the future.", "danger")
                return redirect(request.url)
        except (ValueError, KeyError):
            flash("⚠️ Invalid date or time format.", "danger")
            return redirect(request.url)

        section_ids = request.form.getlist('sections')
        if not section_ids:
            flash("You must select at least one section to create a test.", "danger")
            return redirect(request.url)

        num_questions = []
        section_durations = []
        for sid in section_ids:
            nq = request.form.get(f'num_questions_{sid}')
            dur = request.form.get(f'section_durations_{sid}')
            if not nq or not dur or int(nq) <= 0 or int(dur) <= 0:
                flash("Each selected section must have valid question count and duration.", "danger")
                return redirect(request.url)
            num_questions.append(str(int(nq)))
            section_durations.append(str(int(dur)))

        test = Test(
            test_name=test_name,
            sections=",".join(section_ids),
            num_questions=",".join(num_questions),
            section_durations=",".join(section_durations),
            test_duration=0,
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
    test = Test.query.get_or_404(test_id)

    if request.method == 'POST':
        if 'confirm' in request.form:
            try:
                df = pd.read_csv("temp_upload.csv")
            except FileNotFoundError:
                flash("CSV not found. Please upload again.", "danger")
                return redirect(request.url)

            df.reset_index(drop=True, inplace=True)
            csv_data = df.to_dict(orient='records')
            student_creds = []

            for _, row in df.iterrows():
                name = row['name']
                email = row['email']
                student = User.query.filter_by(email=email, role='student').first()

                if not student:
                    password_plain = secrets.token_urlsafe(6)
                    student = User(name=name, email=email,
                                   password=generate_password_hash(password_plain), role='student')
                    db.session.add(student)
                    db.session.flush()
                else:
                    map_any = StudentTestMap.query.filter_by(student_id=student.id).first()
                    if map_any and map_any.password:
                        password_plain = map_any.password
                    else:
                        password_plain = secrets.token_urlsafe(6)
                        student.password = generate_password_hash(password_plain)

                if not StudentTestMap.query.filter_by(student_id=student.id, test_id=test_id).first():
                    db.session.add(StudentTestMap(student_id=student.id, test_id=test_id, password=password_plain))

                student_creds.append((email, password_plain))

            db.session.commit()
            records = [{
                'sno': i + 1,
                'name': next((r['name'] for r in csv_data if r['email'] == email), ''),
                'email': email,
                'test_password': password,
                'test_login_link': "http://practicetests.in/student/login"
            } for i, (email, password) in enumerate(student_creds)]

            # Save to absolute path in app/static/downloads
            download_dir = Path(current_app.root_path) / "static" / "downloads"
            download_dir.mkdir(parents=True, exist_ok=True)

            file_path = download_dir / f"test_{test_id}_credentials.csv"
            pd.DataFrame(records).to_csv(file_path, index=False)
            return redirect(url_for('admin_routes.download_credentials', test_id=test_id))

        else:
            file = request.files.get('csv_file')
            if not file:
                flash("Please upload a CSV file.", "danger")
                return redirect(request.url)

            df = pd.read_csv(file)
            rows = []
            for i, row in df.iterrows():
                email = row.get('email') or row.get('Email')
                name = row.get('name') or row.get('Name') or row.get('roll_number') or row.get('Roll Number')
                if not email or not name:
                    continue
                rows.append({'name': str(name).strip(), 'email': str(email).strip()})

            if not rows:
                flash("CSV is empty or incorrectly formatted.", "danger")
                return redirect(request.url)

            df = pd.DataFrame(rows)
            df.to_csv("temp_upload.csv", index=False)
            csv_data = rows
            flash("CSV uploaded successfully. Preview below.", "info")

    admin = User.query.get(request.user_id)
    return render_template("assign_test.html", test=test, test_id=test_id, csv_data=csv_data, admin=admin)


@bp.route('/download_credentials/<int:test_id>')
@jwt_required(role='admin')
def download_credentials(test_id):
    file_path = Path(current_app.root_path) / 'static' / 'downloads' / f"test_{test_id}_credentials.csv"
    if not file_path.exists():
        flash("Credential file not found. Please assign the test first.", "danger")
        return redirect(url_for('admin_routes.assign_test', test_id=test_id))
    return send_file(file_path, as_attachment=True)


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
    new_access = generate_access_token(user_id, 'admin')
    return jsonify({'access_token': new_access})
