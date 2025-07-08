from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, send_file
from werkzeug.security import check_password_hash
from io import BytesIO
from random import sample, shuffle
import sys
from pytz import timezone
from sqlalchemy import text
from app.utils.jwt_utils import generate_access_token, generate_refresh_token, decode_token, jwt_required
from app import db
from app.models import User, StudentTestMap, Test, Section, SectionQuestion
from datetime import datetime
from sqlalchemy.sql.expression import func
bp = Blueprint('student_routes', __name__, url_prefix='/student')

@bp.route('/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        print("Login POST hit for student:", email, file=sys.stderr)

        student = User.query.filter_by(email=email, role='student').first()
        if not student:
            flash("No student found with that email.", "danger")
            return redirect(url_for('student_routes.student_login'))

        test_map = StudentTestMap.query.filter_by(student_id=student.id).first()
        if not test_map or not check_password_hash(student.password, password):
            flash("Incorrect password or no test assigned.", "danger")
            return redirect(url_for('student_routes.student_login'))

        access_token = generate_access_token(student.id, 'student')
        refresh_token = generate_refresh_token(student.id)

        response = make_response(redirect(url_for('student_routes.dashboard')))
        response.set_cookie('jwt_token', access_token, httponly=True, samesite='Lax', max_age=3600)
        response.set_cookie('refresh_token', refresh_token, httponly=True, samesite='Lax', max_age=86400)
        return response

    return render_template("student_login.html")

@bp.route('/logout')
def logout():
    response = make_response(redirect(url_for('student_routes.student_login')))
    response.set_cookie('jwt_token', '', expires=0)
    response.set_cookie('refresh_token', '', expires=0)
    return response

@bp.route('/dashboard')
@jwt_required(role='student')
def dashboard():
    student_id = request.user_id
    student = User.query.get(student_id)

    test_maps = StudentTestMap.query.filter_by(student_id=student_id).all()
    enriched_tests = []

    ist = timezone('Asia/Kolkata')
    now = datetime.now(ist)

    for tm in test_maps:
        test = Test.query.get(tm.test_id)
        if test:
            # Convert test start and end dates to IST for display
            test.start_date = test.start_date.astimezone(ist)
            test.end_date = test.end_date.astimezone(ist)

            # Determine test availability
            if now < test.start_date:
                test_status = "not_started"
            elif now > test.end_date:
                test_status = "completed"
            else:
                test_status = "active"

            # Get sections
            section_ids = [int(sid) for sid in test.sections.split(',') if sid.strip()]
            sections = Section.query.filter(Section.id.in_(section_ids)).all()

            # Track section completion status
            section_status = {}
            for section in sections:
                from app.models import StudentSectionAttempt
                progress = StudentSectionAttempt.query.filter_by(
                    student_id=student_id,
                    test_id=test.id,
                    section_id=section.id
                ).first()
                section_status[section.id] = 'Completed' if progress else 'Not Started'

            enriched_tests.append({
                'test': test,
                'sections': sections,
                'status': section_status,
                'availability': test_status
            })

    return render_template("student_dashboard.html", tests=enriched_tests, student=student)


@bp.route('/test/<int:test_id>')
@jwt_required(role='student')
def test_sections(test_id):
    student_id = request.user_id
    test_map = StudentTestMap.query.filter_by(student_id=student_id, test_id=test_id).first()

    if not test_map:
        flash("You are not assigned to this test.", "danger")
        return redirect(url_for('student_routes.dashboard'))

    test = Test.query.get(test_id)
    if not test:
        flash("Test not found.", "danger")
        return redirect(url_for('student_routes.dashboard'))

    section_ids = [int(sid) for sid in test.sections.split(',') if sid.strip()]
    sections = Section.query.filter(Section.id.in_(section_ids)).all()

    return render_template("test_sections.html", test=test, sections=sections)

from datetime import datetime, timedelta
from sqlalchemy import text
from random import sample, shuffle
from app.models import (
    User, Test, Section, SectionQuestion,
    StudentTestMap, StudentSectionProgress
)

@bp.route('/section/<int:section_id>', methods=['GET', 'POST'])
@jwt_required(role='student')
def take_section(section_id):
    student_id = request.user_id
    student = User.query.get(student_id)

    test_maps = StudentTestMap.query.filter_by(student_id=student_id).order_by(StudentTestMap.assigned_date.desc()).all()
    matched_test = None
    for test_map in test_maps:
        test = Test.query.get(test_map.test_id)
        if test and str(section_id) in test.sections.split(','):
            matched_test = test
            break

    if not matched_test:
        flash("You are not authorized to access this section.", "danger")
        return redirect(url_for('student_routes.dashboard'))

    section = Section.query.get(section_id)
    section_ids = matched_test.sections.split(',')
    question_counts = matched_test.num_questions.split(',')
    section_durations = matched_test.section_durations.split(',')

    try:
        index = section_ids.index(str(section_id))
        question_limit = int(question_counts[index])
        section_duration = int(section_durations[index])
    except ValueError:
        flash("Section not configured correctly in test.", "danger")
        return redirect(url_for('student_routes.dashboard'))

    progress = StudentSectionProgress.query.filter_by(
        student_id=student_id,
        test_id=matched_test.id,
        section_id=section_id
    ).first()

    if progress and progress.submitted:
        flash("This section has already been submitted.", "warning")
        return redirect(url_for('student_routes.dashboard'))

    if not progress:
        progress = StudentSectionProgress(
            student_id=student_id,
            test_id=matched_test.id,
            section_id=section_id,
            start_time=datetime.utcnow()
        )
        db.session.add(progress)
        db.session.commit()

    # Check time expiry
    from pytz import utc
    end_time = progress.start_time.replace(tzinfo=utc) + timedelta(minutes=section_duration)
    now = datetime.utcnow().replace(tzinfo=utc)
    if now > end_time:
        progress.submitted = True
        db.session.commit()
        flash("Time is up. Section auto-submitted.", "warning")
        return redirect(url_for('student_routes.dashboard'))

    # Question loading
    if not progress.question_ids:
        all_qs = SectionQuestion.query.filter_by(section_id=section_id).order_by(func.random()).limit(question_limit).all()
        question_ids = ','.join(str(q.id) for q in all_qs)
        progress.question_ids = question_ids
        db.session.commit()
    else:
        question_ids = list(map(int, progress.question_ids.split(',')))
        all_qs = SectionQuestion.query.filter(SectionQuestion.id.in_(question_ids)).all()
        all_qs.sort(key=lambda q: question_ids.index(q.id))

    questions = all_qs
    current_index = 0

    if request.method == 'POST':
        try:
            current_index = int(request.form.get('current_index', 0))
        except:
            current_index = 0

        if 'next' in request.form:
            current_index = min(current_index + 1, len(questions) - 1)
        elif 'prev' in request.form:
            current_index = max(current_index - 1, 0)
        elif 'submit' in request.form:
            progress.submitted = True
            db.session.commit()

            from app.models import StudentSectionAttempt
            already_logged = StudentSectionAttempt.query.filter_by(
                student_id=student_id,
                test_id=matched_test.id,
                section_id=section_id
            ).first()
            if not already_logged:
                db.session.add(StudentSectionAttempt(
                    student_id=student_id,
                    test_id=matched_test.id,
                    section_id=section_id
                ))
                db.session.commit()

            results = []
            for q in questions:
                ans = request.form.get(f"answer_{q.id}")
                is_correct = ans == q.correct_option
                results.append({
                    'question': q.question_text,
                    'submitted': ans,
                    'correct': q.correct_option,
                    'is_correct': is_correct
                })

            return render_template("mcq_results.html", section=section, results=results)

    return render_template("take_section.html",
        section=section,
        questions=questions,
        current_index=current_index,
        student=student,
        end_timestamp=int(end_time.timestamp() * 1000),
        submitted=progress.submitted
    )

@bp.route('/audio/<int:question_id>')
@jwt_required(role='student')
def get_question_audio(question_id):
    question = SectionQuestion.query.get(question_id)
    if not question or not question.question_audio:
        return "Audio not found", 404

    return send_file(BytesIO(question.question_audio), mimetype='audio/mpeg')

@bp.route('/refresh_token', methods=['POST'])
def refresh_token():
    token = request.cookies.get('refresh_token')
    if not token:
        return {"error": "Missing refresh token"}, 401

    payload = decode_token(token)
    if not payload or payload.get('type') != 'refresh':
        return {"error": "Invalid or expired refresh token"}, 403

    user_id = payload['sub']
    role = 'student'
    new_access = generate_access_token(user_id, role)

    response = make_response({"message": "Token refreshed"})
    response.set_cookie('jwt_token', new_access, httponly=True, samesite='Lax', max_age=3600)
    return response
