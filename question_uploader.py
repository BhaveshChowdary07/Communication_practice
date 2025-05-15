import pandas as pd
from sqlalchemy import create_engine
import pymysql

# === CONFIG ===
excel_file = "Passage_Comprehension_Updated (9).xlsx"
section_id = 2  # Replace with your actual Passage Comprehension section ID

# MySQL connection
engine = create_engine("mysql+pymysql://admin2:admin234@localhost/comm_test_db")

# Read Excel
df = pd.read_excel(excel_file)

# Normalize columns
df.fillna('', inplace=True)

# Insert loop
rows_to_insert = []

for idx, row in df.iterrows():
    rows_to_insert.append({
        "section_id": section_id,
        "passage_text": row["Passage Text"],
        "question_text": row["Question 1"],
        "option_a": row["Option 1A"],
        "option_b": row["Option 1B"],
        "option_c": row["Option 1C"],
        "option_d": row["Option 1D"],
        "correct_option": row["Correct Answer 1"].strip()[-1],  # (A) -> A
        "is_text_input": 0,
        "is_audio_input": 0
    })

# Convert to DataFrame and insert
insert_df = pd.DataFrame(rows_to_insert)
insert_df.to_sql("section_questions", con=engine, if_exists="append", index=False)

print("✅ Passage comprehension questions inserted successfully.")
