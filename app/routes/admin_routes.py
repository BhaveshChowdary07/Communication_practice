from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pandas as pd
import secrets

from app.utils.jwt_utils import generate_access_token, generate_refresh_token, decode_token, jwt_required
from app import db
from app.models import User, Test, Section, StudentTestMap
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
    tests = Test.query.order_by(Test.id.desc()).all()
    return render_template('admin_dashboard.html', tests=tests)


@bp.route('/create_test', methods=['GET', 'POST'])
@jwt_required(role='admin')
def create_test():
    sections = Section.query.all()

    if request.method == 'POST':
        test_name = request.form['test_name']
        test_duration = int(request.form['test_duration'])
        start_date = datetime.strptime(request.form['start_date'], "%Y-%m-%dT%H:%M")
        end_date = datetime.strptime(request.form['end_date'], "%Y-%m-%dT%H:%M")

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
            num_questions.append(nq)
            section_durations.append(dur)

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

    return render_template('create_test.html', sections=sections)


@bp.route('/assign_test/<int:test_id>', methods=['GET', 'POST'])
@jwt_required(role='admin')
def assign_test(test_id):
    from flask import session
    csv_data = None
    test = Test.query.get(test_id)

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
                    # Generate new password
                    password_plain = secrets.token_urlsafe(6)
                    hashed_pw = generate_password_hash(password_plain)
                    student = User(name=name, email=email, password=hashed_pw, role='student')
                    db.session.add(student)
                    db.session.flush()
                else:
                    # Reuse old password if available from any previous assignment
                    existing_map_any = StudentTestMap.query.filter_by(student_id=student.id).first()
                    if existing_map_any and existing_map_any.password:
                        password_plain = existing_map_any.password
                    else:
                        password_plain = secrets.token_urlsafe(6)
                        student.password = generate_password_hash(password_plain)

                # Assign test if not already done
                existing_map = StudentTestMap.query.filter_by(student_id=student.id, test_id=test_id).first()
                if not existing_map:
                    map_entry = StudentTestMap(
                        student_id=student.id,
                        test_id=test_id,
                        password=password_plain
                    )
                    db.session.add(map_entry)

                # ✅ Send email with reused/generated password
                send_credentials(email=email, password=password_plain, test_id=test_id)

            db.session.commit()
            flash("Students assigned and credentials sent!", "success")
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
    StudentTestMap.query.filter_by(test_id=test_id).delete()
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
