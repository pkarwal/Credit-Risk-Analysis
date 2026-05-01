

import psycopg2
import psycopg2.extras
import numpy as np
from datetime import date, timedelta
import random

# ── Config 
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "credit_risk",
    "user":     "prabhnoorkaur",
    "password": ""  
}

random.seed(42)
np.random.seed(42)

N_BORROWERS = 10_000
N_LOANS     = 12_000

#  Connect
print("Connecting to PostgreSQL...")
conn = psycopg2.connect(**DB_CONFIG)
conn.autocommit = False
cur = conn.cursor()

# Create schema
print("Creating schema...")
cur.execute("DROP TABLE IF EXISTS risk_segments, repayments, credit_history, loans, borrowers CASCADE")

cur.execute("""
CREATE TABLE borrowers (
    borrower_id         INTEGER PRIMARY KEY,
    age                 INTEGER,
    annual_income       NUMERIC(12, 2),
    employment_years    NUMERIC(5, 1),
    home_ownership      VARCHAR(20),
    state               VARCHAR(5),
    created_at          DATE
)""")

cur.execute("""
CREATE TABLE loans (
    loan_id             INTEGER PRIMARY KEY,
    borrower_id         INTEGER REFERENCES borrowers(borrower_id),
    loan_amount         NUMERIC(12, 2),
    funded_amount       NUMERIC(12, 2),
    term_months         INTEGER,
    interest_rate       NUMERIC(5, 2),
    loan_purpose        VARCHAR(50),
    grade               CHAR(1),
    sub_grade           VARCHAR(3),
    issue_date          DATE,
    loan_status         VARCHAR(30)
)""")

cur.execute("""
CREATE TABLE credit_history (
    credit_id               INTEGER PRIMARY KEY,
    borrower_id             INTEGER REFERENCES borrowers(borrower_id),
    snapshot_date           DATE,
    credit_score            INTEGER,
    debt_to_income          NUMERIC(6, 2),
    revolving_balance       NUMERIC(12, 2),
    revolving_utilization   NUMERIC(5, 2),
    open_accounts           INTEGER,
    delinquencies_2yr       INTEGER,
    public_records          INTEGER,
    total_accounts          INTEGER
)""")

cur.execute("""
CREATE TABLE repayments (
    repayment_id        INTEGER PRIMARY KEY,
    loan_id             INTEGER REFERENCES loans(loan_id),
    payment_date        DATE,
    amount_due          NUMERIC(10, 2),
    amount_paid         NUMERIC(10, 2),
    principal_paid      NUMERIC(10, 2),
    interest_paid       NUMERIC(10, 2),
    late_fee            NUMERIC(8, 2),
    days_past_due       INTEGER DEFAULT 0
)""")

cur.execute("""
CREATE TABLE risk_segments (
    borrower_id         INTEGER PRIMARY KEY REFERENCES borrowers(borrower_id),
    risk_tier           VARCHAR(20),
    pd_score            NUMERIC(5, 4),
    segment_date        DATE
)""")

conn.commit()
print("Schema created.")

#  Borrowers 
print("Inserting borrowers...")
home_options = ["RENT", "OWN", "MORTGAGE"]
home_weights = [0.40, 0.15, 0.45]
states = ["CA","TX","NY","FL","IL","WA","BC","ON","AB","MI","OH","PA","GA","NC"]

ages           = np.random.randint(22, 75, N_BORROWERS)
incomes        = np.round(np.random.lognormal(10.9, 0.6, N_BORROWERS), 2)
emp_years      = np.round(np.clip(np.random.exponential(5, N_BORROWERS), 0, 40), 1)
home_ownership = np.random.choice(home_options, N_BORROWERS, p=home_weights)
state_col      = np.random.choice(states, N_BORROWERS)
created_dates  = [date(2018,1,1) + timedelta(days=int(d)) for d in np.random.randint(0, 365*5, N_BORROWERS)]

borrowers = [
    (i+1, int(ages[i]), float(incomes[i]), float(emp_years[i]),
     home_ownership[i], state_col[i], created_dates[i])
    for i in range(N_BORROWERS)
]
psycopg2.extras.execute_values(cur, "INSERT INTO borrowers VALUES %s", borrowers, page_size=500)
conn.commit()
print(f"  {N_BORROWERS:,} borrowers inserted")

# Loans 
print("Inserting loans...")
purposes = ["debt_consolidation","credit_card","home_improvement","medical",
            "small_business","major_purchase","vacation","moving","other"]
pur_w    = [0.35, 0.25, 0.12, 0.08, 0.07, 0.05, 0.03, 0.03, 0.02]
grades   = list("ABCDEFG")
statuses = ["Fully Paid","Charged Off","Current","Default","Late (31-120 days)"]

borrower_ids = np.random.randint(1, N_BORROWERS + 1, N_LOANS)
loan_amounts = np.round(np.random.lognormal(9.5, 0.8, N_LOANS), 2)
funded       = np.round(loan_amounts * np.random.uniform(0.90, 1.0, N_LOANS), 2)
terms        = np.random.choice([36, 60], N_LOANS, p=[0.65, 0.35])
rates        = np.round(np.random.uniform(5.5, 28.0, N_LOANS), 2)
grade_col    = np.random.choice(grades, N_LOANS, p=[0.18,0.22,0.20,0.17,0.12,0.07,0.04])
sub_grades   = [f"{g}{np.random.randint(1,6)}" for g in grade_col]
purpose_col  = np.random.choice(purposes, N_LOANS, p=pur_w)
issue_dates  = [date(2019,1,1) + timedelta(days=int(d)) for d in np.random.randint(0, 365*4, N_LOANS)]

def pick_status(g):
    base = {
        "A":[0.75,0.04,0.18,0.01,0.02], "B":[0.65,0.08,0.20,0.03,0.04],
        "C":[0.52,0.15,0.20,0.06,0.07], "D":[0.40,0.22,0.20,0.10,0.08],
        "E":[0.28,0.32,0.18,0.14,0.08], "F":[0.18,0.40,0.15,0.18,0.09],
        "G":[0.10,0.48,0.12,0.20,0.10]
    }
    return np.random.choice(statuses, p=base[g])

status_col = [pick_status(g) for g in grade_col]

loans = [
    (i+1, int(borrower_ids[i]), float(loan_amounts[i]), float(funded[i]),
     int(terms[i]), float(rates[i]), purpose_col[i], grade_col[i],
     sub_grades[i], issue_dates[i], status_col[i])
    for i in range(N_LOANS)
]
psycopg2.extras.execute_values(cur, "INSERT INTO loans VALUES %s", loans, page_size=500)
conn.commit()
print(f"  {N_LOANS:,} loans inserted")

# Credit history 
print("Inserting credit history...")
scores    = np.random.randint(580, 850, N_BORROWERS)
dti       = np.round(np.clip(np.random.normal(18, 8, N_BORROWERS), 0, 50), 2)
rev_bal   = np.round(np.random.lognormal(8.5, 1.0, N_BORROWERS), 2)
rev_util  = np.round(np.clip(np.random.beta(2, 3, N_BORROWERS) * 100, 0, 100), 2)
open_accs = np.random.randint(2, 25, N_BORROWERS)
delinq    = np.random.choice([0,1,2,3,4,5], N_BORROWERS, p=[0.68,0.16,0.08,0.04,0.02,0.02])
pub_recs  = np.random.choice([0,1,2], N_BORROWERS, p=[0.90, 0.08, 0.02])
total_acc = open_accs + np.random.randint(0, 20, N_BORROWERS)
snap_dates= [date(2019,1,1) + timedelta(days=int(d)) for d in np.random.randint(0, 365*4, N_BORROWERS)]

credit = [
    (i+1, i+1, snap_dates[i], int(scores[i]), float(dti[i]), float(rev_bal[i]),
     float(rev_util[i]), int(open_accs[i]), int(delinq[i]), int(pub_recs[i]), int(total_acc[i]))
    for i in range(N_BORROWERS)
]
psycopg2.extras.execute_values(cur, "INSERT INTO credit_history VALUES %s", credit, page_size=500)
conn.commit()
print(f"  {N_BORROWERS:,} credit history records inserted")

# Repayments 
print("Inserting repayments...")
active_statuses = {"Fully Paid", "Current", "Late (31-120 days)"}
repayments = []
rep_id = 1

for i in range(N_LOANS):
    if status_col[i] not in active_statuses:
        continue
    n_payments = np.random.randint(2, 6)
    for j in range(n_payments):
        due  = round(float(loan_amounts[i]) * 0.03, 2)
        paid = round(due * float(np.random.uniform(0.0, 1.05)), 2)
        dpd  = 0 if paid >= due else int(np.random.choice(
            [0,5,15,30,60,90], p=[0.3,0.2,0.2,0.15,0.1,0.05]))
        repayments.append((
            rep_id, i+1,
            issue_dates[i] + timedelta(days=30*(j+1)),
            due, paid,
            round(paid*0.6, 2), round(paid*0.4, 2),
            round(max(0, due-paid)*0.05, 2), dpd
        ))
        rep_id += 1

    if len(repayments) >= 5000:
        psycopg2.extras.execute_values(cur, "INSERT INTO repayments VALUES %s", repayments, page_size=500)
        conn.commit()
        repayments = []

if repayments:
    psycopg2.extras.execute_values(cur, "INSERT INTO repayments VALUES %s", repayments, page_size=500)
    conn.commit()

print(f"  {rep_id - 1:,} repayment records inserted")

# Indexes 
print("Adding indexes...")
for stmt in [
    "CREATE INDEX idx_loans_borrower   ON loans(borrower_id)",
    "CREATE INDEX idx_loans_status     ON loans(loan_status)",
    "CREATE INDEX idx_loans_grade      ON loans(grade)",
    "CREATE INDEX idx_loans_issue_date ON loans(issue_date)",
    "CREATE INDEX idx_credit_borrower  ON credit_history(borrower_id)",
    "CREATE INDEX idx_repayments_loan  ON repayments(loan_id)",
]:
    cur.execute(stmt)
conn.commit()

cur.close()
conn.close()
print("\nAll done! Database 'credit_risk' is ready.")
print("Open pgAdmin or VS Code SQLTools and connect to get started.")
