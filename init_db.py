from app import db, app
from app.models import User, Test, StudentTestMap, Section
from werkzeug.security import generate_password_hash

# Create app context for database setup
with app.app_context():
    db.create_all()
    print("✅ Database initialized and tables created.")

    # Optional: Add predefined 9 communication sections
    if not Section.query.first():
        default_sections = [
            ("Sentence Repeating", "audio", "Listen and repeat the sentence."),
            ("Short Stories", "mcq", "Read a story and answer MCQs."),
            ("Just a Minute", "audio", "Speak for a minute on a given topic."),
            ("Sentence Reading", "audio", "Read aloud the given sentence."),
            ("Passage Comprehension", "mcq", "Comprehend a passage and answer."),
            ("Grammar", "mcq", "Grammar-based fill in the blanks or MCQs."),
            ("Essay Writing", "text", "Write an essay on the topic."),
            ("Jumbled Sentence", "audio", "Reorder a jumbled spoken sentence."),
            ("Story Retelling", "audio", "Listen and retell the story.")
        ]
        for name, typ, desc in default_sections:
            section = Section(name=name, type=typ, description=desc)
            db.session.add(section)
        db.session.commit()
        print("✅ Default communication sections added.")

    # Optional: Add default admin user (only if not exists)
    if not User.query.filter_by(email='admin@example.com').first():
        admin = User(
            name='Admin',
            email='ankurah777@gmail.com',
            password=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Default admin user created: admin@example.com / admin123")
