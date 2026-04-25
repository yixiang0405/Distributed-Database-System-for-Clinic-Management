"""
Clinic Management — Flask app.

Design notes for the DCS assignment:
- The DB endpoint is read from the environment (DB_HOST etc.), so when RDS
  fails over to the standby, we don't need to change code — AWS swaps the
  DNS record and our next connection lands on the new primary.
- /health returns 200 only when the DB is reachable. The ALB uses this to
  decide if an EC2 instance is healthy — that's how failover works at the
  web tier.
- socket.gethostname() is shown in the UI so you can SEE which EC2 served
  the request during the demo (refresh and the hostname switches between AZs).
"""
import os
import socket
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify
from sqlalchemy import text
from models import db, Patient, Doctor, Appointment, MedicalRecord, Medicine

# --- S3 / file upload helpers ---
# boto3 is only imported if S3 env vars are set.
# Locally: files saved to static/uploads/
# On AWS:  files uploaded to S3 bucket.
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_file(file):
    """
    Upload a file either to S3 (when AWS env vars are set)
    or to local static/uploads/ folder (for local dev).
    Returns (file_url, file_name) tuple.
    """
    original_name = file.filename
    ext           = original_name.rsplit(".", 1)[1].lower()
    unique_name   = f"{uuid.uuid4().hex}.{ext}"   # random name avoids collisions

    bucket = os.getenv("S3_BUCKET")

    if bucket:
        # --- AWS S3 upload ---
        import boto3
        region = os.getenv("AWS_REGION", "ap-southeast-1")
        s3 = boto3.client("s3", region_name=region)
        s3.upload_fileobj(
            file,
            bucket,
            f"records/{unique_name}",
            ExtraArgs={"ContentType": file.content_type}
        )
        file_url = f"https://{bucket}.s3.{region}.amazonaws.com/records/{unique_name}"
    else:
        # --- Local storage fallback ---
        upload_folder = os.path.join(os.path.dirname(__file__), "static", "uploads")
        os.makedirs(upload_folder, exist_ok=True)
        file.save(os.path.join(upload_folder, unique_name))
        file_url = f"/static/uploads/{unique_name}"

    return file_url, original_name


def create_app():
    app = Flask(__name__)

    # Build the DB URL from env vars. Default values are just for local dev.
    db_user = os.getenv("DB_USER", "admin")
    db_pass = os.getenv("DB_PASS", "changeme")
    db_host = os.getenv("DB_HOST", "localhost")
    db_name = os.getenv("DB_NAME", "clinic")
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{db_user}:{db_pass}@{db_host}/{db_name}"
    )
    # Recycle connections before RDS kills idle ones — important during failover.
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
    db.init_app(app)

    HOSTNAME = socket.gethostname()

    # --- Health check used by the ALB target group ---
    @app.route("/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify(status="ok", host=HOSTNAME), 200
        except Exception as e:
            return jsonify(status="error", host=HOSTNAME, error=str(e)), 503

    # --- Home: redirect to patient list ---
    @app.route("/")
    def index():
        return redirect(url_for("list_patients"))

    # --- Patient CRUD ---
    @app.route("/patients")
    def list_patients():
        patients      = Patient.query.order_by(Patient.created_at.desc()).all()
        record_count  = MedicalRecord.query.count()
        medicine_count = Medicine.query.count()
        return render_template("patients.html", patients=patients, host=HOSTNAME,
                               record_count=record_count, medicine_count=medicine_count)

    @app.route("/patients/new", methods=["GET", "POST"])
    def new_patient():
        if request.method == "POST":
            p = Patient(
                full_name=request.form["full_name"],
                dob=datetime.strptime(request.form["dob"], "%Y-%m-%d").date(),
                phone=request.form.get("phone"),
                email=request.form.get("email"),
            )
            db.session.add(p)
            db.session.commit()
            return redirect(url_for("list_patients"))
        return render_template("patient_form.html", patient=None, host=HOSTNAME)

    @app.route("/patients/<int:pid>/edit", methods=["GET", "POST"])
    def edit_patient(pid):
        p = Patient.query.get_or_404(pid)
        if request.method == "POST":
            p.full_name = request.form["full_name"]
            p.dob = datetime.strptime(request.form["dob"], "%Y-%m-%d").date()
            p.phone = request.form.get("phone")
            p.email = request.form.get("email")
            db.session.commit()
            return redirect(url_for("list_patients"))
        return render_template("patient_form.html", patient=p, host=HOSTNAME)

    @app.route("/patients/<int:pid>/delete", methods=["POST"])
    def delete_patient(pid):
        p = Patient.query.get_or_404(pid)
        db.session.delete(p)
        db.session.commit()
        return redirect(url_for("list_patients"))

    # --- Appointments ---
    @app.route("/appointments", methods=["GET", "POST"])
    def appointments():
        if request.method == "POST":
            a = Appointment(
                patient_id=int(request.form["patient_id"]),
                doctor_id=int(request.form["doctor_id"]),
                scheduled_at=datetime.strptime(
                    request.form["scheduled_at"], "%Y-%m-%dT%H:%M"
                ),
                reason=request.form.get("reason"),
            )
            db.session.add(a)
            db.session.commit()
            return redirect(url_for("appointments"))
        appts    = Appointment.query.order_by(Appointment.scheduled_at.desc()).all()
        patients = Patient.query.all()
        doctors  = Doctor.query.all()
        return render_template(
            "appointments.html",
            appointments=appts,
            patients=patients,
            doctors=doctors,
            host=HOSTNAME,
        )

    # --- Medical Records CRUD ---
    @app.route("/records")
    def list_records():
        records  = MedicalRecord.query.order_by(MedicalRecord.visit_date.desc()).all()
        return render_template("records.html", records=records, host=HOSTNAME)

    @app.route("/records/new", methods=["GET", "POST"])
    def new_record():
        if request.method == "POST":
            file_url, file_name = None, None
            uploaded = request.files.get("patient_file")
            if uploaded and uploaded.filename and allowed_file(uploaded.filename):
                file_url, file_name = upload_file(uploaded)

            r = MedicalRecord(
                patient_id     = int(request.form["patient_id"]),
                doctor_id      = int(request.form["doctor_id"]),
                appointment_id = request.form.get("appointment_id") or None,
                visit_date     = datetime.strptime(request.form["visit_date"], "%Y-%m-%d").date(),
                diagnosis      = request.form.get("diagnosis"),
                prescription   = request.form.get("prescription"),
                notes          = request.form.get("notes"),
                file_url       = file_url,
                file_name      = file_name,
            )
            db.session.add(r)
            db.session.commit()
            return redirect(url_for("list_records"))
        patients     = Patient.query.order_by(Patient.full_name).all()
        doctors      = Doctor.query.order_by(Doctor.full_name).all()
        appointments = Appointment.query.order_by(Appointment.scheduled_at.desc()).all()
        return render_template("record_form.html", record=None,
                               patients=patients, doctors=doctors,
                               appointments=appointments, host=HOSTNAME)

    @app.route("/records/<int:rid>/edit", methods=["GET", "POST"])
    def edit_record(rid):
        r = MedicalRecord.query.get_or_404(rid)
        if request.method == "POST":
            # Only replace file if a new one was uploaded
            uploaded = request.files.get("patient_file")
            if uploaded and uploaded.filename and allowed_file(uploaded.filename):
                r.file_url, r.file_name = upload_file(uploaded)

            r.patient_id     = int(request.form["patient_id"])
            r.doctor_id      = int(request.form["doctor_id"])
            r.appointment_id = request.form.get("appointment_id") or None
            r.visit_date     = datetime.strptime(request.form["visit_date"], "%Y-%m-%d").date()
            r.diagnosis      = request.form.get("diagnosis")
            r.prescription   = request.form.get("prescription")
            r.notes          = request.form.get("notes")
            db.session.commit()
            return redirect(url_for("list_records"))
        patients     = Patient.query.order_by(Patient.full_name).all()
        doctors      = Doctor.query.order_by(Doctor.full_name).all()
        appointments = Appointment.query.order_by(Appointment.scheduled_at.desc()).all()
        return render_template("record_form.html", record=r,
                               patients=patients, doctors=doctors,
                               appointments=appointments, host=HOSTNAME)

    @app.route("/records/<int:rid>/delete", methods=["POST"])
    def delete_record(rid):
        r = MedicalRecord.query.get_or_404(rid)
        db.session.delete(r)
        db.session.commit()
        return redirect(url_for("list_records"))

    # --- Medicines CRUD ---
    @app.route("/medicines")
    def list_medicines():
        medicines = Medicine.query.order_by(Medicine.name).all()
        return render_template("medicines.html", medicines=medicines, host=HOSTNAME)

    @app.route("/medicines/new", methods=["GET", "POST"])
    def new_medicine():
        if request.method == "POST":
            m = Medicine(
                name        = request.form["name"],
                category    = request.form.get("category"),
                stock_qty   = int(request.form.get("stock_qty") or 0),
                unit        = request.form.get("unit"),
                expiry_date = datetime.strptime(request.form["expiry_date"], "%Y-%m-%d").date()
                              if request.form.get("expiry_date") else None,
            )
            db.session.add(m)
            db.session.commit()
            return redirect(url_for("list_medicines"))
        return render_template("medicine_form.html", medicine=None, host=HOSTNAME)

    @app.route("/medicines/<int:mid>/edit", methods=["GET", "POST"])
    def edit_medicine(mid):
        m = Medicine.query.get_or_404(mid)
        if request.method == "POST":
            m.name        = request.form["name"]
            m.category    = request.form.get("category")
            m.stock_qty   = int(request.form.get("stock_qty") or 0)
            m.unit        = request.form.get("unit")
            m.expiry_date = datetime.strptime(request.form["expiry_date"], "%Y-%m-%d").date() \
                            if request.form.get("expiry_date") else None
            db.session.commit()
            return redirect(url_for("list_medicines"))
        return render_template("medicine_form.html", medicine=m, host=HOSTNAME)

    @app.route("/medicines/<int:mid>/delete", methods=["POST"])
    def delete_medicine(mid):
        m = Medicine.query.get_or_404(mid)
        db.session.delete(m)
        db.session.commit()
        return redirect(url_for("list_medicines"))

    return app


if __name__ == "__main__":
    app = create_app()
    # Dev server. In production (EC2), gunicorn runs the app instead.
    app.run(host="0.0.0.0", port=5000, debug=False)
