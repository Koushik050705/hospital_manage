import streamlit as st
import sqlite3
import pandas as pd
import bcrypt
import plotly.express as px
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# =================== DATABASE SETUP ===================
conn = sqlite3.connect("hospital.db")
c = conn.cursor()

def add_column_if_missing(table, column, col_type):
    """Adds a column to an SQLite table if it does not already exist."""
    c.execute(f"PRAGMA table_info({table})")
    columns = [info[1] for info in c.fetchall()]
    if column not in columns:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        conn.commit()
        print(f"Added missing column '{column}' to '{table}' table.")

def create_tables():
    # Users table
    c.execute("""CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password BLOB,
                    role TEXT)""")
    add_column_if_missing("users", "specialization", "TEXT")  # Auto add if missing

    # Patients table
    c.execute("""CREATE TABLE IF NOT EXISTS patients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    age INTEGER,
                    gender TEXT,
                    phone TEXT,
                    address TEXT)""")

    # Appointments table
    c.execute("""CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER,
                    doctor TEXT,
                    date TEXT,
                    status TEXT)""")

    # Billing table
    c.execute("""CREATE TABLE IF NOT EXISTS billing (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER,
                    items TEXT,
                    total REAL)""")

    conn.commit()

create_tables()

# =================== AUTH FUNCTIONS ===================
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)

def add_user(username, password, role, specialization=""):
    hashed_pw = hash_password(password)
    c.execute("INSERT INTO users (username, password, role, specialization) VALUES (?, ?, ?, ?)", 
              (username, hashed_pw, role, specialization))
    conn.commit()

def login_user(username, password):
    c.execute("SELECT password, role, specialization FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    if result and check_password(password, result[0]):
        return result[1], result[2]  # role, specialization
    return None, None

# =================== PATIENT FUNCTIONS ===================
def add_patient(name, age, gender, phone, address):
    c.execute("INSERT INTO patients (name, age, gender, phone, address) VALUES (?, ?, ?, ?, ?)",
              (name, age, gender, phone, address))
    conn.commit()

def get_patients():
    return pd.read_sql("SELECT * FROM patients", conn)

# =================== APPOINTMENT FUNCTIONS ===================
def add_appointment(patient_id, doctor, date, status="Scheduled"):
    c.execute("INSERT INTO appointments (patient_id, doctor, date, status) VALUES (?, ?, ?, ?)",
              (patient_id, doctor, date, status))
    conn.commit()

def get_appointments(doctor=None):
    if doctor:
        query = f"""SELECT a.id, p.name as patient, a.doctor, a.date, a.status
                    FROM appointments a
                    JOIN patients p ON a.patient_id = p.id
                    WHERE a.doctor = '{doctor}'"""
    else:
        query = """SELECT a.id, p.name as patient, a.doctor, a.date, a.status
                   FROM appointments a
                   JOIN patients p ON a.patient_id = p.id"""
    return pd.read_sql(query, conn)

# =================== BILLING FUNCTIONS ===================
def add_bill(patient_id, items, total):
    c.execute("INSERT INTO billing (patient_id, items, total) VALUES (?, ?, ?)",
              (patient_id, items, total))
    conn.commit()

def get_bills():
    return pd.read_sql("""SELECT b.id, p.name as patient, b.items, b.total
                          FROM billing b
                          JOIN patients p ON b.patient_id = p.id""", conn)

# =================== PDF GENERATORS ===================
def generate_invoice_pdf(patient_name, items, total):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica-Bold", 18)
    p.drawString(200, 800, "Hospital Invoice")
    p.setFont("Helvetica", 12)
    p.drawString(50, 770, f"Patient: {patient_name}")
    y = 740
    p.drawString(50, y, "Services/Items:")
    y -= 20
    for item in items.split("\n"):
        p.drawString(70, y, f"- {item}")
        y -= 20
    p.drawString(50, y-10, f"Total: ₹{total}")
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

def generate_prescription_pdf(patient_name, doctor_name, specialization, medicines):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica-Bold", 18)
    p.drawString(180, 800, "Medical Prescription")
    p.setFont("Helvetica", 12)
    p.drawString(50, 770, f"Doctor: {doctor_name} ({specialization})")
    p.drawString(50, 750, f"Patient: {patient_name}")
    y = 720
    p.drawString(50, y, "Medicines:")
    y -= 20
    for med in medicines.split("\n"):
        p.drawString(70, y, f"- {med}")
        y -= 20
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# =================== STREAMLIT UI ===================
st.set_page_config(page_title="Hospital Management System", layout="wide")
st.title("🏥 Hospital Management System")

menu = ["Login", "Register"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "Register":
    st.subheader("Create Account")
    new_user = st.text_input("Username")
    new_pass = st.text_input("Password", type="password")
    role = st.selectbox("Role", ["Admin", "Doctor", "Receptionist", "Patient"])
    specialization = ""
    if role == "Doctor":
        specialization = st.text_input("Specialization (e.g. Cardiologist, Orthopedic)")
    if st.button("Register"):
        add_user(new_user, new_pass, role, specialization)
        st.success(f"User {new_user} registered as {role}")

elif choice == "Login":
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        role, specialization = login_user(username, password)
        if role:
            st.success(f"Welcome {username}! Role: {role}")

            # =================== ADMIN DASHBOARD ===================
            if role == "Admin":
                tabs = st.tabs(["Dashboard", "Patients", "Appointments", "Billing"])
                with tabs[0]:
                    st.subheader("📊 Dashboard")
                    patients_df = get_patients()
                    appt_df = get_appointments()
                    col1, col2 = st.columns(2)
                    col1.metric("Total Patients", len(patients_df))
                    col2.metric("Appointments", len(appt_df))
                    if not appt_df.empty:
                        fig = px.bar(appt_df, x="doctor", color="status", title="Appointments per Doctor")
                        st.plotly_chart(fig)

                with tabs[1]:
                    st.subheader("Add Patient")
                    name = st.text_input("Name")
                    age = st.number_input("Age", 1, 120)
                    gender = st.selectbox("Gender", ["Male", "Female", "Other"])
                    phone = st.text_input("Phone")
                    address = st.text_area("Address")
                    if st.button("Save Patient"):
                        add_patient(name, age, gender, phone, address)
                        st.success("Patient Added")
                    st.dataframe(get_patients())

                with tabs[2]:
                    st.subheader("Schedule Appointment")
                    patients_df = get_patients()
                    patient_names = patients_df["name"].tolist()
                    patient_choice = st.selectbox("Select Patient", patient_names, key="admin_patient_select")
                    doctor = st.text_input("Doctor Name")
                    date = st.date_input("Date")
                    if st.button("Book Appointment"):
                        pid = patients_df[patients_df["name"] == patient_choice]["id"].values[0]
                        add_appointment(pid, doctor, str(date))
                        st.success("Appointment Booked")
                    st.dataframe(get_appointments())

                with tabs[3]:
                    st.subheader("Billing System")
                    patients_df = get_patients()
                    patient_names = patients_df["name"].tolist()
                    patient_choice = st.selectbox("Select Patient", patient_names, key="admin_billing_select")
                    items = st.text_area("Services/Items (one per line: name - ₹price)")
                    if items.strip():
                        total = sum([float(i.split("-")[-1].strip().replace("₹", "")) if "-" in i else 0 for i in items.split("\n")])
                    else:
                        total = 0
                    st.write(f"**Total: ₹{total}**")
                    if st.button("Generate Bill"):
                        pid = patients_df[patients_df["name"] == patient_choice]["id"].values[0]
                        add_bill(pid, items, total)
                        pdf_buffer = generate_invoice_pdf(patient_choice, items, total)
                        st.download_button("📥 Download Invoice", data=pdf_buffer, file_name="invoice.pdf", mime="application/pdf")
                    st.dataframe(get_bills())

            # =================== DOCTOR DASHBOARD ===================
            elif role == "Doctor":
                tabs = st.tabs(["My Appointments", "Prescriptions"])
                with tabs[0]:
                    st.subheader(f"My Appointments ({specialization})")
                    st.dataframe(get_appointments(username))
                with tabs[1]:
                    patients_df = get_patients()
                    patient_names = patients_df["name"].tolist()
                    patient_choice = st.selectbox("Select Patient", patient_names, key="doctor_prescription_select")
                    medicines = st.text_area("Medicines (one per line)")
                    if st.button("Generate Prescription"):
                        pdf_buffer = generate_prescription_pdf(patient_choice, username, specialization, medicines)
                        st.download_button("📥 Download Prescription", data=pdf_buffer, file_name="prescription.pdf", mime="application/pdf")

            # =================== RECEPTIONIST DASHBOARD ===================
            elif role == "Receptionist":
                st.subheader("Book Appointment")
                patients_df = get_patients()
                patient_names = patients_df["name"].tolist()
                patient_choice = st.selectbox("Select Patient", patient_names, key="receptionist_patient_select")
                doctor = st.text_input("Doctor Name")
                date = st.date_input("Date")
                if st.button("Book Appointment"):
                    pid = patients_df[patients_df["name"] == patient_choice]["id"].values[0]
                    add_appointment(pid, doctor, str(date))
                    st.success("Appointment Booked")
                st.dataframe(get_appointments())

            # =================== PATIENT DASHBOARD ===================
            elif role == "Patient":
                st.subheader("My Bills")
                st.dataframe(get_bills())

        else:
            st.error("Invalid Username or Password")
