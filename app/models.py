"""
SQLAlchemy models. These mirror the tables in sql/schema.sql.
We use SQLAlchemy so we get a clean Python API and can switch DB drivers.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """
    Application users (clinic staff). Passwords are stored as PBKDF2-SHA256
    hashes via werkzeug — never plain text. The shared SECRET_KEY in
    /etc/clinic.env lets either EC2 instance validate session cookies issued
    by the other, so users stay logged in regardless of which instance the
    ALB routes them to.
    """
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(50),  unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.String(20),  default="staff")
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow)

    def set_password(self, plain_password):
        self.password_hash = generate_password_hash(plain_password)

    def check_password(self, plain_password):
        return check_password_hash(self.password_hash, plain_password)


class Patient(db.Model):
    __tablename__ = "patients"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    dob = db.Column(db.Date, nullable=False)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Doctor(db.Model):
    __tablename__ = "doctors"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    specialty = db.Column(db.String(80))


class Appointment(db.Model):
    __tablename__ = "appointments"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(255))
    status = db.Column(db.String(20), default="scheduled")

    patient = db.relationship("Patient", backref="appointments")
    doctor = db.relationship("Doctor")


class MedicalRecord(db.Model):
    __tablename__ = "medical_records"
    id             = db.Column(db.Integer, primary_key=True)
    patient_id     = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    doctor_id      = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointments.id"))
    visit_date     = db.Column(db.Date, nullable=False)
    diagnosis      = db.Column(db.String(255))
    prescription   = db.Column(db.Text)
    notes          = db.Column(db.Text)
    file_url       = db.Column(db.String(500))   # S3 URL or local path
    file_name      = db.Column(db.String(255))   # original filename shown to user
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    patient     = db.relationship("Patient", backref="records")
    doctor      = db.relationship("Doctor")
    appointment = db.relationship("Appointment")


class Medicine(db.Model):
    __tablename__ = "medicines"
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(120), nullable=False)
    category    = db.Column(db.String(80))
    stock_qty   = db.Column(db.Integer, default=0)
    unit        = db.Column(db.String(30))
    expiry_date = db.Column(db.Date)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
