import pandas as pd
from sqlalchemy import create_engine

# === CONFIG ===
engine = create_engine("mysql+pymysql://admin2:admin234@localhost/comm_test_db")

# Load files
short_stories_df = pd.read_csv("short_stories.csv")
passage_df = pd.read_excel("Passage_Comprehension_Updated (9).xlsx")
short_stories_df.fillna('', inplace=True)
passage_df.fillna('', inplace=True)

# Prepare short stories (section_id = 2)
short_rows = []
for _, row in short_stories_df.iterrows():
    passage = row["short story"]
    for i in range(1, 4):
        q = row.get(f"Question {i}", "").strip()
        if not q:
            continue
        short_rows.append({
            "section_id": 2,
            "passage_text": passage,
            "question_text": q,
            "option_a": row.get(f"Option {i}A", ""),
            "option_b": row.get(f"Option {i}B", ""),
            "option_c": row.get(f"Option {i}C", ""),
            "option_d": row.get(f"Option {i}D", ""),
            "correct_option": row.get(f"Correct Answer {i}", "").strip()[-1:],
            "is_text_input": 0,
            "is_audio_input": 0
        })

# Prepare passage comprehension (section_id = 5)
passage_rows = []
for _, row in passage_df.iterrows():
    passage = row["Passage Text"]
    for i in range(1, 4):
        q = row.get(f"Question {i}", "").strip()
        if not q:
            continue
        passage_rows.append({
            "section_id": 5,
            "passage_text": passage,
            "question_text": q,
            "option_a": row.get(f"Option {i}A", ""),
            "option_b": row.get(f"Option {i}B", ""),
            "option_c": row.get(f"Option {i}C", ""),
            "option_d": row.get(f"Option {i}D", ""),
            "correct_option": row.get(f"Correct Answer {i}", "").strip()[-1:],
            "is_text_input": 0,
            "is_audio_input": 0
        })

# Insert into DB
pd.DataFrame(short_rows).to_sql("section_questions", con=engine, if_exists="append", index=False)
pd.DataFrame(passage_rows).to_sql("section_questions", con=engine, if_exists="append", index=False)

print(f"✅ Inserted {len(short_rows)} short story MCQs and {len(passage_rows)} passage MCQs.")
