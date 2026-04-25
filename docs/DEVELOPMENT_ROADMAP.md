# Development Roadmap — What to Build First

**Project:** Fault-Tolerant Clinic Management System
**Deadline:** 2026-05-01
**Team size:** 3

---

## The golden rule: build inside-out, not outside-in

Start with the **database**, then the **backend**, then the **frontend**, then **AWS deployment**, then **fault-tolerance testing**.

**Why this order?**
- You can't build a backend without knowing the data shape.
- You can't build a frontend without working API routes.
- You can't deploy to AWS without a working app locally.
- You can't test failover without something to fail.

Each layer depends on the one below it. Skipping ahead means rework.

---

## Phase 1 — Database design (Day 1-2)

**Goal:** Know exactly what data you're storing before writing any code.

| Step | What to do | Output |
|---|---|---|
| 1.1 | List entities (patient, doctor, appointment) | Diagram on paper / draw.io |
| 1.2 | Define columns, types, constraints | ER diagram |
| 1.3 | Identify relationships (FKs) | Schema in [sql/schema.sql](../sql/schema.sql) |
| 1.4 | Install MySQL **locally** | `mysql` CLI working |
| 1.5 | Run `schema.sql` on localhost | Tables created, sample rows inserted |
| 1.6 | Test: `SELECT * FROM patients;` works | Data visible |

**Do NOT skip local MySQL.** Running the schema locally catches syntax errors before you burn AWS time.

**Deliverable:** Working MySQL database on your laptop with sample data.

---

## Phase 2 — Backend (Day 3-5)

**Goal:** A Flask app that does CRUD against your local database.

| Step | What to do | How to verify |
|---|---|---|
| 2.1 | `python -m venv venv` + `pip install -r requirements.txt` | `flask --version` works |
| 2.2 | Set env vars `DB_HOST=localhost` etc. | `echo $DB_HOST` |
| 2.3 | Run [app.py](../app/app.py) locally: `python app.py` | Server starts on :5000 |
| 2.4 | Test `/health` endpoint | Returns `{"status":"ok"}` |
| 2.5 | Test each route with curl or browser | All CRUD works |
| 2.6 | Write 2-3 manual test cases | Create → Edit → Delete patient |

**Why backend before frontend?** If `/patients` returns JSON, you can test with curl. If you start with the frontend, you have no data to render — you'll build against fake data and discover mismatches later.

**Deliverable:** All 4 CRUD routes work locally when tested with curl.

---

## Phase 3 — Frontend (Day 6-7)

**Goal:** HTML templates that let a human use what the backend already does.

| Step | What to do |
|---|---|
| 3.1 | Build [base.html](../app/templates/base.html) skeleton (nav, footer) |
| 3.2 | Build [patients.html](../app/templates/patients.html) list page |
| 3.3 | Build [patient_form.html](../app/templates/patient_form.html) for add/edit |
| 3.4 | Build [appointments.html](../app/templates/appointments.html) |
| 3.5 | Style pass — colors, icons, polish |
| 3.6 | Test the full user flow in the browser |

**Why frontend last in the app layer?** Templates are the easiest to iterate on. Once the backend is solid, you can rewrite the UI 5 times without breaking anything.

**Deliverable:** Clickable app. Anyone on the team can add a patient and see it appear.

---

## Phase 4 — AWS Infrastructure (Day 8-11)

**Goal:** Get a working single-instance deployment, then scale out.

**Sub-phase 4a — Single-AZ proof of life (Day 8-9)**

| Step | What to do | Why |
|---|---|---|
| 4.1 | Create VPC with 2 public + 2 private subnets across 2 AZs | Foundation for everything else |
| 4.2 | Create security groups (ALB, web, DB) | Network isolation |
| 4.3 | Launch **one** RDS MySQL instance (single-AZ first) | Cheapest way to validate connection |
| 4.4 | Run `schema.sql` against the RDS endpoint | Confirms DB works from outside |
| 4.5 | Launch **one** EC2 with [user_data.sh](../deploy/user_data.sh) | Confirms app boots correctly |
| 4.6 | Hit the EC2's public IP in browser | App loads, CRUD works |

**Checkpoint:** If this works, you've proven the app runs on AWS. Everything after is about adding redundancy.

**Sub-phase 4b — Go Multi-AZ (Day 10-11)**

| Step | What to do |
|---|---|
| 4.7 | Launch second EC2 in the **other AZ** |
| 4.8 | Create ALB target group, register both EC2s |
| 4.9 | Create ALB, point at target group |
| 4.10 | Modify RDS → enable **Multi-AZ deployment** |
| 4.11 | Hit ALB DNS in browser, refresh, see hostname change |

**Deliverable:** ALB URL you can share. Two EC2s. Multi-AZ database. Full flow works through the load balancer.

See [../deploy/DEPLOY.md](../deploy/DEPLOY.md) for detailed instructions.

---

## Phase 5 — Fault Tolerance Testing (Day 12-13)

**Goal:** Prove the system survives failures. This is what you'll demo.

| Test | What you're proving |
|---|---|
| Kill one EC2 | Web tier HA |
| Reboot RDS with failover | DB tier HA + replication |
| Kill gunicorn process | App-level self-healing |
| Cross-AZ data consistency | Single source of truth |

Run each, screenshot the result, write 2 sentences per test.

See [FAULT_TOLERANCE_TESTS.md](FAULT_TOLERANCE_TESTS.md).

**Deliverable:** A test log with screenshots ready for the demo.

---

## Phase 6 — Report + Demo Prep (Day 14)

| Item | Notes |
|---|---|
| Architecture diagram | Use draw.io or Lucidchart; include AZs explicitly |
| Screenshots from fault tests | Before/during/after for each |
| Demo script | 5-min walkthrough: show UI → kill EC2 → site still works → reboot RDS → site recovers |
| Team contribution breakdown | Required for group grading |

---

## Team split suggestion (3 members)

| Person | Phases | Focus |
|---|---|---|
| **A — Database + Backend Lead** | 1, 2 | SQL schema, Flask routes, models |
| **B — Frontend + UX** | 3 | Templates, styling, user flows |
| **C — DevOps + AWS Lead** | 4, 5 | VPC, EC2, RDS, ALB, failover tests |

All three collaborate on Phase 6 (report + demo).

**Parallelism trick:** Once Phase 1 schema is agreed, A (backend) and B (frontend mocked with static data) can work in parallel. C can start reading AWS docs and provisioning the VPC while A and B build the app.

---

## Timeline at a glance

```
Day  1  2  3  4  5  6  7  8  9 10 11 12 13 14
    [DB][  Backend  ][Frontend][  AWS Deploy  ][Tests][Report]
     A   A   A   A   A   B   B   C   C   C   C    C    C    ALL
```

**Slack buffer:** If you finish each phase on time, you'll hit the 2026-05-01 deadline with 3-4 days to spare for debugging. Don't burn the buffer early.

---

## Common mistakes to avoid

1. **Starting with AWS first.** You'll fight config issues with nothing to show. Get the app working locally first.
2. **Using the AWS root account.** Make an IAM user on day one.
3. **Hardcoding passwords in git.** Use env vars or SSM Parameter Store from the start.
4. **Leaving RDS Multi-AZ on overnight.** Outside Free Tier — costs add up. Enable the day of the demo, disable after.
5. **Skipping local MySQL.** Debugging schema issues on RDS is 10x slower.
6. **No snapshots before the fault test.** Take an RDS snapshot before you reboot — safety net.
