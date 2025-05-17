from app import db
from datetime import datetime

# --- Unified User Model for Admin and Students ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(512), nullable=False)
    role = db.Column(db.String(20), nullable=False)

# --- Test Model ---
class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_name = db.Column(db.String(100), nullable=False)
    sections = db.Column(db.String(300))
    num_questions = db.Column(db.String(100))
    section_durations = db.Column(db.String(100))
    test_duration = db.Column(db.Integer)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))

# --- Student-Test Assignment Map ---
class StudentTestMap(db.Model):
    __tablename__ = 'student_test_map'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'))
    assigned_date = db.Column(db.DateTime)
    password = db.Column(db.String(255))

    test = db.relationship('Test', backref='assigned_students')

# --- Section Table ---
class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    type = db.Column(db.String(50))
    description = db.Column(db.Text)
class SectionQuestion(db.Model):
    __tablename__ = 'section_questions'  # ✅ matches your table

    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('section.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_audio = db.Column(db.LargeBinary)
    # Optional fields depending on your section types
    option_a = db.Column(db.Text)
    option_b = db.Column(db.Text)
    option_c = db.Column(db.Text)
    option_d = db.Column(db.Text)
    correct_option = db.Column(db.String(1))  # if MCQ
    is_text_input = db.Column(db.Boolean, default=True)
    is_audio_input = db.Column(db.Boolean, default=False)
class StudentSectionProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'))
    section_id = db.Column(db.Integer, db.ForeignKey('section.id'))
    start_time = db.Column(db.DateTime)
    submitted = db.Column(db.Boolean, default=False)
