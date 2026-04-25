# Clinic Management System — Fault-Tolerant Distributed Database (DCS)

A university assignment demo: a clinic management CRUD web app deployed on AWS
with multi-AZ database replication and automatic failover.

## What this project demonstrates

| Requirement | How it's demonstrated |
|---|---|
| High availability | 2x EC2 instances behind an Application Load Balancer, across 2 AZs |
| Data replication | RDS MySQL Multi-AZ — synchronous replica in a second AZ |
| Automatic failover | ALB health checks + RDS Multi-AZ DNS failover (~60s) |
| CRUD web interface | Flask + Jinja2 HTML templates with Bootstrap |
| Proper architecture | Public ALB → private EC2 → private RDS; IAM, security groups |

## Architecture

```
                    Internet
                       |
                 [Route 53 / ALB DNS]
                       |
          ┌────── Application Load Balancer ──────┐
          |  (public subnets, AZ-a + AZ-b)        |
          |                                       |
   ┌──────▼──────┐                         ┌──────▼──────┐
   │ EC2 web-1   │                         │ EC2 web-2   │
   │ AZ-a        │                         │ AZ-b        │
   │ Flask :5000 │                         │ Flask :5000 │
   └──────┬──────┘                         └──────┬──────┘
          |                                       |
          └────────────┬──────────────────────────┘
                       |
                 [RDS endpoint]
                       |
          ┌─── RDS MySQL Multi-AZ ───┐
          | Primary (AZ-a) ←sync→    |
          | Standby (AZ-b)           |
          └──────────────────────────┘
```

**Why two AZs?** An Availability Zone is a physically separate data center. If one
loses power, the other keeps running — that's our fault tolerance story.

## Free Tier note

RDS Multi-AZ is **not** in the Free Tier (Multi-AZ doubles RDS cost).
For a graded demo, two options:
1. **Enable Multi-AZ for the demo day only**, then disable. Cost ~$0.50/day for db.t3.micro.
2. **Use a read replica** in a second AZ instead (closer to Free Tier, but async replication — document this trade-off in your report).

EC2 + ALB + 20GB storage stay inside Free Tier for 12 months.

## Repo layout

```
DCS/
├── README.md              # this file
├── app/                   # Flask application
│   ├── app.py
│   ├── models.py
│   ├── requirements.txt
│   └── templates/
│       ├── base.html
│       ├── patients.html
│       ├── patient_form.html
│       └── appointments.html
├── sql/
│   └── schema.sql         # database schema + sample data
├── deploy/
│   ├── user_data.sh       # EC2 bootstrap script
│   └── DEPLOY.md          # step-by-step AWS deployment guide
└── docs/
    └── FAULT_TOLERANCE_TESTS.md
```

See [deploy/DEPLOY.md](deploy/DEPLOY.md) for the full deployment walkthrough.
