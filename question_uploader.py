import pandas as pd
from sqlalchemy import create_engine, text

# === CONFIG ===
engine = create_engine("mysql+pymysql://admin2:admin234@localhost/comm_test_db")
xlsx_path = "Passage_Comprehension_Updated (9).xlsx"
df = pd.read_excel(xlsx_path).fillna('')

with engine.begin() as conn:
    insert_main = text("""
        INSERT INTO section_questions (section_id, question_text, is_text_input, is_audio_input)
        VALUES (:section_id, :question_text, 0, 0)
    """)
    insert_sub = text("""
        INSERT INTO mcq_subquestions (section_question_id, question_text, option_a, option_b, option_c, option_d, correct_option)
        VALUES (:sqid, :qtext, :a, :b, :c, :d, :correct)
    """)

    for _, row in df.iterrows():
        passage = row["Passage Text"].strip()

        # Insert passage as a question
        result = conn.execute(insert_main, {
            "section_id": 5,  # Reading Comprehension section
            "question_text": passage
        })
        section_question_id = result.lastrowid

        # Insert 3 MCQs
        for i in range(1, 4):
            q = row.get(f"Question {i}", "").strip()
            if not q:
                continue
            conn.execute(insert_sub, {
                "sqid": section_question_id,
                "qtext": q,
                "a": row.get(f"Option {i}A", "").strip(),
                "b": row.get(f"Option {i}B", "").strip(),
                "c": row.get(f"Option {i}C", "").strip(),
                "d": row.get(f"Option {i}D", "").strip(),
                "correct": row.get(f"Correct Answer {i}", "").strip()[-1:].upper()
            })

print("✅ Reading Comprehension passages and MCQs inserted successfully.")
