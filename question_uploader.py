import pandas as pd
from sqlalchemy import create_engine, text

# === CONFIG ===
engine = create_engine("mysql+pymysql://admin2:admin234@localhost/comm_test_db")

# Load files
short_stories_df = pd.read_csv("short_stories.csv")
passage_df = pd.read_excel("Passage_Comprehension_Updated (9).xlsx")
short_stories_df.fillna('', inplace=True)
passage_df.fillna('', inplace=True)

with engine.begin() as conn:
    # === SHORT STORIES (Section ID 2) ===
    for _, row in short_stories_df.iterrows():
        passage = row["short story"]

        # Insert into section_questions
        insert_question = text("""
            INSERT INTO section_questions (section_id, question_text, is_text_input, is_audio_input)
            VALUES (:section_id, :question_text, 0, 0)
        """)
        result = conn.execute(insert_question, {
            "section_id": 2,
            "question_text": passage
        })
        section_question_id = result.lastrowid

        # Insert 3 MCQs
        for i in range(1, 4):
            q = row.get(f"Question {i}", "").strip()
            if not q:
                continue

            insert_sub = text("""
                INSERT INTO mcq_subquestions (section_question_id, question_text, option_a, option_b, option_c, option_d, correct_option)
                VALUES (:sqid, :qtext, :a, :b, :c, :d, :correct)
            """)
            conn.execute(insert_sub, {
                "sqid": section_question_id,
                "qtext": q,
                "a": row.get(f"Option {i}A", ""),
                "b": row.get(f"Option {i}B", ""),
                "c": row.get(f"Option {i}C", ""),
                "d": row.get(f"Option {i}D", ""),
                "correct": row.get(f"Correct Answer {i}", "").strip()[-1:].upper()
            })

    # === READING COMPREHENSION (Section ID 5) ===
    for _, row in passage_df.iterrows():
        passage = row["Passage Text"]

        result = conn.execute(insert_question, {
            "section_id": 5,
            "question_text": passage
        })
        section_question_id = result.lastrowid

        for i in range(1, 4):
            q = row.get(f"Question {i}", "").strip()
            if not q:
                continue
            conn.execute(insert_sub, {
                "sqid": section_question_id,
                "qtext": q,
                "a": row.get(f"Option {i}A", ""),
                "b": row.get(f"Option {i}B", ""),
                "c": row.get(f"Option {i}C", ""),
                "d": row.get(f"Option {i}D", ""),
                "correct": row.get(f"Correct Answer {i}", "").strip()[-1:].upper()
            })

print("✅ Inserted short stories and reading comprehension questions.")
