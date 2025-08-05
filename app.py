import streamlit as st
import sqlite3
import pandas as pd
import bcrypt
import plotly.express as px
import qrcode
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# ---------------------- DATABASE ----------------------
conn = sqlite3.connect("hospital.db")
c = conn.cursor()

def create_tables():
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password BLOB,
                    role TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS patients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    age INTEGER,
                    gender TEXT,
                    phone TEXT,
                    address TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER,
                    doctor TEXT,
                    date TEXT,
                    status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS billing (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER,
                    amount REAL,
                    details TEXT)''')
    conn.commit()

create_tables()

# ---------------------- AUTH ----------------------
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)

def add_user(username, password, role):
    hashed_pw = hash_password(password)
    c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
              (username, hashed_pw, role))
    conn.commit()

def login_user(username, password):
    c.execute("SELECT password, role FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    if result and check_password(password, result[0]):
        return result[1]
    return None

# ---------------------- PATIENT ----------------------
def add_patient(name, age, gender, phone, address):
    c.execute("INSERT INTO patients (name, age, gender, phone, address) VALUES (?, ?, ?, ?, ?)",
              (name, age, gender, phone, address))
    conn.commit()

def get_patients():
    return pd.read_sql("SELECT * FROM patients", conn)

# ---------------------- APPOINTMENTS ----------------------
def add_appointment(patient_id, doctor, date, status="Scheduled"):
    c.execute("INSERT INTO appointments (patient_id, doctor, date, status) VALUES (?, ?, ?, ?)",
              (patient_id, doctor, date, status))
    conn.commit()

def get_appointments():
    return pd.read_sql("""SELECT a.id, p.name as patient, a.doctor, a.date, a.status
                          FROM appointments a
                          JOIN patients p ON a.patient_id = p.id""", conn)

# ---------------------- BILLING ----------------------
def add_bill(patient_id, amount, details):
    c.execute("INSERT INTO billing (patient_id, amount, details) VALUES (?, ?, ?)",
              (patient_id, amount, details))
    conn.commit()

def get_bills():
    return pd.read_sql("""SELECT b.id, p.name as patient, b.amount, b.details
                          FROM billing b
                          JOIN patients p ON b.patient_id = p.id""", conn)

# ---------------------- QR CODE ----------------------
def generate_qr(data):
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    buf = BytesIO()
    img.save(buf)
    return buf.getvalue()

# ---------------------- PDF GENERATOR ----------------------
def generate_prescription_pdf(patient_name, doctor_name, medicines, filename="prescription.pdf"):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, "Hospital Prescription")
    p.setFont("Helvetica", 12)
    p.drawString(50, 770, f"Patient: {patient_name}")
    p.drawString(50, 750, f"Doctor: {doctor_name}")
    p.drawString(50, 730, "Medicines:")
    y = 710
    for med in medicines.split("\n"):
        p.drawString(70, y, f"- {med}")
        y -= 20
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

def generate_invoice_pdf(patient_name, amount, details, filename="invoice.pdf"):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, "Hospital Invoice")
    p.setFont("Helvetica", 12)
    p.drawString(50, 770, f"Patient: {patient_name}")
    p.drawString(50, 750, f"Amount: ₹{amount}")
    p.drawString(50, 730, "Details:")
    y = 710
    for line in details.split("\n"):
        p.drawString(70, y, f"- {line}")
        y -= 20
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# ---------------------- MAIN APP ----------------------
st.set_page_config(page_title="Hospital Management System", layout="wide")
st.title("🏥 Hospital Management System")

menu = ["Login", "Register"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "Register":
    st.subheader("Create Account")
    new_user = st.text_input("Username")
    new_pass = st.text_input("Password", type="password")
    role = st.selectbox("Role", ["Admin", "Doctor", "Receptionist", "Patient"])
    if st.button("Register"):
        add_user(new_user, new_pass, role)
        st.success(f"User {new_user} registered as {role}")

elif choice == "Login":
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        role = login_user(username, password)
        if role:
            st.success(f"Welcome {username}! Role: {role}")

            if role == "Admin":
                tabs = st.tabs(["Dashboard", "Manage Patients", "Appointments", "Billing"])
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
                    st.subheader("🧍 Add Patient")
                    name = st.text_input("Name")
                    age = st.number_input("Age", 1, 120)
                    gender = st.selectbox("Gender", ["Male", "Female", "Other"])
                    phone = st.text_input("Phone")
                    address = st.text_area("Address")
                    if st.button("Add Patient"):
                        add_patient(name, age, gender, phone, address)
                        st.success("Patient Added")
                    st.dataframe(get_patients())

                with tabs[2]:
                    st.subheader("📅 Add Appointment")
                    patients_df = get_patients()
                    patient_names = patients_df["name"].tolist()
                    patient_choice = st.selectbox("Select Patient", patient_names)
                    doctor = st.text_input("Doctor Name")
                    date = st.date_input("Date")
                    if st.button("Book Appointment"):
                        patient_id = patients_df[patients_df["name"] == patient_choice]["id"].values[0]
                        add_appointment(patient_id, doctor, str(date))
                        st.success("Appointment Booked")
                    st.dataframe(get_appointments())

                with tabs[3]:
                    st.subheader("💰 Billing")
                    patients_df = get_patients()
                    patient_names = patients_df["name"].tolist()
                    patient_choice = st.selectbox("Select Patient", patient_names)
                    amount = st.number_input("Amount", 0)
                    details = st.text_area("Details")
                    if st.button("Add Bill"):
                        patient_id = patients_df[patients_df["name"] == patient_choice]["id"].values[0]
                        add_bill(patient_id, amount, details)
                        st.success("Bill Added")
                    st.dataframe(get_bills())

            elif role == "Doctor":
                st.subheader("📝 Generate Prescription")
                patients_df = get_patients()
                patient_names = patients_df["name"].tolist()
                patient_choice = st.selectbox("Select Patient", patient_names)
                medicines = st.text_area("Medicines (one per line)")
                if st.button("Generate Prescription PDF"):
                    pdf_buffer = generate_prescription_pdf(patient_choice, username, medicines)
                    st.download_button("📥 Download Prescription", data=pdf_buffer, file_name="prescription.pdf", mime="application/pdf")

            elif role == "Receptionist":
                st.subheader("Book Appointments")
                patients_df = get_patients()
                patient_names = patients_df["name"].tolist()
                patient_choice = st.selectbox("Select Patient", patient_names)
                doctor = st.text_input("Doctor Name")
                date = st.date_input("Date")
                if st.button("Book Appointment"):
                    patient_id = patients_df[patients_df["name"] == patient_choice]["id"].values[0]
                    add_appointment(patient_id, doctor, str(date))
                    st.success("Appointment Booked")
                st.dataframe(get_appointments())

            elif role == "Patient":
                st.subheader("My Bills & Prescriptions")
                st.dataframe(get_bills())
        else:
            st.error("Invalid Username or Password")
