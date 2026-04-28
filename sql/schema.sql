-- Clinic Management System schema
-- Run this once against your RDS endpoint after it's created:
--   mysql -h <rds-endpoint> -u admin -p < schema.sql

CREATE DATABASE IF NOT EXISTS clinic
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE clinic;

-- Users: application login accounts (clinic staff).
-- Passwords are stored as werkzeug PBKDF2-SHA256 hashes, never plain text.
-- The default admin password ('admin123') is seeded at the bottom of this
-- file via the placeholder hash — replace it with a real hash before demo.
CREATE TABLE IF NOT EXISTS users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  username      VARCHAR(50)  UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role          VARCHAR(20)  DEFAULT 'staff',
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Patients: the core entity
CREATE TABLE IF NOT EXISTS patients (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  full_name    VARCHAR(120) NOT NULL,
  dob          DATE         NOT NULL,
  phone        VARCHAR(30),
  email        VARCHAR(120),
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_name (full_name)
) ENGINE=InnoDB;

-- Doctors
CREATE TABLE IF NOT EXISTS doctors (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  full_name   VARCHAR(120) NOT NULL,
  specialty   VARCHAR(80)
) ENGINE=InnoDB;

-- Appointments: links patients and doctors (many-to-many over time)
CREATE TABLE IF NOT EXISTS appointments (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  patient_id    INT NOT NULL,
  doctor_id     INT NOT NULL,
  scheduled_at  DATETIME NOT NULL,
  reason        VARCHAR(255),
  status        ENUM('scheduled','completed','cancelled') DEFAULT 'scheduled',
  FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
  FOREIGN KEY (doctor_id)  REFERENCES doctors(id),
  INDEX idx_sched (scheduled_at)
) ENGINE=InnoDB;

-- Medical Records: history of each patient visit/diagnosis
CREATE TABLE IF NOT EXISTS medical_records (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  patient_id     INT NOT NULL,
  doctor_id      INT NOT NULL,
  appointment_id INT,
  visit_date     DATE NOT NULL,
  diagnosis      VARCHAR(255),
  prescription   TEXT,
  notes          TEXT,
  file_url       VARCHAR(500),   -- S3 URL or local path to uploaded file
  file_name      VARCHAR(255),   -- original filename shown to user
  created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (patient_id)     REFERENCES patients(id) ON DELETE CASCADE,
  FOREIGN KEY (doctor_id)      REFERENCES doctors(id),
  FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE SET NULL,
  INDEX idx_patient (patient_id),
  INDEX idx_visit (visit_date)
) ENGINE=InnoDB;

-- Medicines: inventory of medicines available at the clinic
CREATE TABLE IF NOT EXISTS medicines (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  name         VARCHAR(120) NOT NULL,
  category     VARCHAR(80),
  stock_qty    INT DEFAULT 0,
  unit         VARCHAR(30),
  expiry_date  DATE,
  updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_medicine_name (name)
) ENGINE=InnoDB;

-- Sample data so the demo isn't empty
INSERT INTO doctors (full_name, specialty) VALUES
  ('Dr. Aisha Tan',   'General Practice'),
  ('Dr. Ben Rahman',  'Pediatrics'),
  ('Dr. Clara Lim',   'Cardiology');

INSERT INTO patients (full_name, dob, phone, email) VALUES
  ('Alice Wong',  '1990-05-12', '+65 9123 4567', 'alice@example.com'),
  ('Bob Kumar',   '1985-11-03', '+65 9234 5678', 'bob@example.com');

INSERT INTO medicines (name, category, stock_qty, unit, expiry_date) VALUES
  ('Paracetamol 500mg', 'Analgesic',    200, 'tablets', '2027-01-01'),
  ('Amoxicillin 250mg', 'Antibiotic',    80, 'capsules','2026-12-01'),
  ('Cetirizine 10mg',   'Antihistamine', 150, 'tablets', '2027-06-01');

-- Default admin user is created automatically by the Flask app on first
-- startup (see ensure_default_admin() in app.py). Username: admin / Password: admin123.
-- We do this in Python rather than SQL so werkzeug generates a valid PBKDF2 hash.
