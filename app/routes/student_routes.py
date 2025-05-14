from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, send_file
from werkzeug.security import check_password_hash
from io import BytesIO
from random import sample, shuffle

from app import db
from app.models import User, StudentTestMap, Test, Section, SectionQuestion
from app.utils.jwt_utils import generate_token, jwt_required

bp = Blueprint('student_routes', __name__, url_prefix='/student')

@bp.route('/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        student = User.query.filter_by(email=email, role='student').first()
        if not student:
            flash("No student found with that email.", "danger")
            return redirect(url_for('student_routes.student_login'))

        test_map = StudentTestMap.query.filter_by(student_id=student.id).first()
        if not test_map or not check_password_hash(student.password, password):
            flash("Incorrect password or no test assigned to this email.", "danger")
            return redirect(url_for('student_routes.student_login'))

        token = generate_token(student.id, 'student')
        response = make_response(redirect(url_for('student_routes.dashboard')))
        response.set_cookie('jwt_token', token, httponly=True, samesite='Lax')
        return response

    return render_template("student_login.html")

@bp.route('/logout')
def logout():
    response = make_response(redirect(url_for('student_routes.student_login')))
    response.set_cookie('jwt_token', '', expires=0)
    return response

@bp.route('/dashboard')
@jwt_required(role='student')
def dashboard():
    student_id = request.user_id
    student = User.query.get(student_id)

    test_maps = StudentTestMap.query.filter_by(student_id=student_id).all()
    tests = [Test.query.get(tm.test_id) for tm in test_maps if Test.query.get(tm.test_id)]

    return render_template("student_dashboard.html", tests=tests, student=student)

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

@bp.route('/section/<int:section_id>', methods=['GET'])
@jwt_required(role='student')
def take_section(section_id):
    student_id = request.user_id

    # Verify student is assigned to this section
    test_maps = StudentTestMap.query.filter_by(student_id=student_id).all()
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

    # Determine how many questions to fetch
    section_ids = [sid.strip() for sid in matched_test.sections.split(',') if sid.strip()]
    question_counts = [int(q.strip()) for q in matched_test.num_questions.split(',') if q.strip()]

    if len(section_ids) != len(question_counts):
        flash("Test is misconfigured: section and question count mismatch.", "danger")
        return redirect(url_for('student_routes.dashboard'))

    index = section_ids.index(str(section_id))
    question_limit = question_counts[index]

    if section.type == 'grammar':
        all_questions = SectionQuestion.query.filter_by(section_id=section_id).order_by(SectionQuestion.id).all()
        model1 = all_questions[0:50]
        model2 = all_questions[50:100]
        model3 = all_questions[100:150]

        chunk = question_limit // 3
        questions = (
            sample(model1, chunk) +
            sample(model2, chunk) +
            sample(model3, question_limit - 2 * chunk)
        )
        shuffle(questions)
    else:
        questions = SectionQuestion.query.filter_by(section_id=section_id).limit(question_limit).all()

    return render_template("take_section.html", section=section, questions=questions)

@bp.route('/audio/<int:question_id>')
@jwt_required(role='student')
def get_question_audio(question_id):
    question = SectionQuestion.query.get(question_id)
    if not question or not question.question_audio:
        return "Audio not found", 404

    return send_file(BytesIO(question.question_audio), mimetype='audio/mpeg')
