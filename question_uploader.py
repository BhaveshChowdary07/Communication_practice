import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import SectionQuestion
from app import db

# === CONFIG ===
AUDIO_FOLDER = os.path.join(os.getcwd(), "audio", "story_outputs")
SECTION_ID = 9  # JAM section
DB_URI = "mysql+pymysql://admin2:admin234@localhost/comm_test_db"

# === Setup SQLAlchemy ===
engine = create_engine(DB_URI)
Session = sessionmaker(bind=engine)
session = Session()

# === Upload audio files ===
for filename in os.listdir(AUDIO_FOLDER):
    if filename.endswith(".mp3") or filename.endswith(".wav"):
        filepath = os.path.join(AUDIO_FOLDER, filename)
        with open(filepath, "rb") as f:
            audio_blob = f.read()

        question = SectionQuestion(
            section_id=SECTION_ID,
            question_text=f"story retelling - {filename}",
            question_audio=audio_blob,
            is_audio_input=True
        )
        session.add(question)
        print(f"✅ Added: {filename}")

session.commit()
session.close()
print("🎉 All JAM audio files uploaded!")
