# Step-by-Step AWS Deployment Guide

Every step has a **Why** so you can explain it in your report.

**Region throughout: `ap-southeast-1` (Singapore).** The two AZs used below are
`ap-southeast-1a` and `ap-southeast-1b` — pick any two in your region.

---

## Prerequisites

- AWS account with Free Tier available
- AWS CLI installed locally (optional but handy)
- A GitHub repo containing the `app/` folder (so EC2 can `git clone` it)
- An EC2 key pair in `ap-southeast-1` called `clinic-key` (create under **EC2 → Key Pairs**)

---

## Step 1 — VPC and subnets

**Why:** A VPC is your private network in AWS. You need subnets in **two different AZs** to prove fault tolerance: if AZ-a fails, AZ-b keeps serving.

1. **VPC → Create VPC → "VPC and more"** (the wizard).
2. Name tag: `clinic-vpc`. IPv4 CIDR: `10.0.0.0/16`.
3. Number of AZs: **2**. Public subnets: **2**. Private subnets: **2**.
4. NAT gateway: **None** (saves cost — we'll make EC2 public for simplicity).
5. Click **Create VPC**.

You now have:
- `public-subnet-1a` (10.0.0.0/20, AZ-a) — for ALB + EC2
- `public-subnet-1b` (10.0.16.0/20, AZ-b) — for ALB + EC2
- `private-subnet-1a`, `private-subnet-1b` — for RDS

---

## Step 2 — Security groups

**Why:** Security groups are stateful firewalls. The principle is *least privilege*: each tier only accepts traffic from the tier directly above it.

Create three:

| Name | Inbound rules |
|---|---|
| `clinic-alb-sg` | HTTP 80 from `0.0.0.0/0` |
| `clinic-web-sg` | TCP 5000 from **`clinic-alb-sg`** (not from the world); SSH 22 from your IP |
| `clinic-db-sg` | MySQL 3306 from **`clinic-web-sg`** only |

Referencing another SG (instead of an IP range) is the AWS-native way to lock down internal traffic — it's also what graders look for.

---

## Step 3 — RDS MySQL Multi-AZ

**Why:** Multi-AZ keeps a synchronous standby copy of your DB in a second AZ. If the primary dies, RDS promotes the standby and updates DNS in ~60s — your app survives without code changes.

1. **RDS → Create database → Standard create → MySQL 8.0.x**.
2. Templates: **Free tier** (then we'll enable Multi-AZ in the next field — note the cost trade-off in README).
3. DB identifier: `clinic-db`. Master username: `admin`. Password: strong, record it.
4. Instance class: `db.t3.micro`. Storage: 20 GiB gp3.
5. **Multi-AZ deployment: Yes** *(outside Free Tier — enable the day of your demo)*.
6. VPC: `clinic-vpc`. Subnet group: let it create one using the private subnets.
7. Public access: **No**. VPC security group: `clinic-db-sg`.
8. Initial database name: `clinic`.
9. Create → wait ~10 min.

Then load the schema. From your laptop via a bastion **or** from an EC2 in the same VPC:
```bash
mysql -h clinic-db.XXXXX.ap-southeast-1.rds.amazonaws.com -u admin -p < sql/schema.sql
```

---

## Step 4 — Launch two EC2 instances (one per AZ)

**Why:** Two instances in two AZs means losing one machine — or one whole data center — doesn't take the site down.

For each of `web-1` (AZ-a) and `web-2` (AZ-b):

1. **EC2 → Launch instances**.
2. Name: `clinic-web-1` / `clinic-web-2`.
3. AMI: **Amazon Linux 2023**.
4. Instance type: `t2.micro` (Free Tier).
5. Key pair: `clinic-key`.
6. Network: VPC `clinic-vpc`, Subnet: `public-subnet-1a` (then `-1b` for web-2).
7. Auto-assign public IP: **Enable**.
8. Security group: `clinic-web-sg`.
9. **Advanced details → User data**: paste `deploy/user_data.sh`. Edit the `git clone` URL and the RDS endpoint/password first.
10. Launch.

After ~2 minutes: `curl http://<instance-public-ip>:5000/health` should return `{"status":"ok",...}`.

---

## Step 5 — Application Load Balancer

**Why:** The ALB is the single public entry point. It spreads traffic across both EC2s and stops sending to any instance that fails its health check — that's how the web tier tolerates failure.

1. **EC2 → Target Groups → Create**. Type: Instances. Protocol: HTTP, port **5000**. VPC: `clinic-vpc`. Health check path: `/health`. Register `web-1` and `web-2`.
2. **EC2 → Load Balancers → Create → Application Load Balancer**. Name: `clinic-alb`. Scheme: internet-facing. VPC: `clinic-vpc`. Mappings: tick **both** public subnets. Security group: `clinic-alb-sg`. Listener: HTTP 80 → forward to the target group above.
3. Create → wait ~3 min for DNS to propagate.

Open the ALB DNS name (e.g., `clinic-alb-123.ap-southeast-1.elb.amazonaws.com`) — you should see the patients page. Refresh a few times: the hostname in the footer switches between `ip-10-0-x-x` addresses — proof the ALB is load-balancing.

---

## Step 6 — IAM (minimum viable)

**Why:** Graders want to see you applied least privilege.

- **EC2 role `clinic-ec2-role`**: attach `AmazonSSMManagedInstanceCore` so you can open a shell via Session Manager without SSH keys. Attach this role to both EC2s.
- **Your user**: don't use the AWS root account — create an IAM user with just the permissions you need (EC2, RDS, ELB, VPC, IAM read).
- **DB password**: store in AWS Systems Manager Parameter Store as a `SecureString` (`/clinic/db/password`) — then have `user_data.sh` fetch it with `aws ssm get-parameter`. This keeps secrets out of your git history.

---

## Step 7 — Verify it's working

```bash
ALB=clinic-alb-xxxxx.ap-southeast-1.elb.amazonaws.com
curl http://$ALB/health        # { status: ok, host: ip-10-0-1-23 }
curl http://$ALB/health        # { status: ok, host: ip-10-0-2-45 }  ← different host
```

If both hosts appear across refreshes, your load balancer is working across AZs.

Next: see [../docs/FAULT_TOLERANCE_TESTS.md](../docs/FAULT_TOLERANCE_TESTS.md) for the demo-day test scenarios.

---

## Cost cleanup after the demo

Tear down in this order to stop charges:
1. Delete ALB (charged hourly)
2. Terminate EC2 instances
3. Delete RDS (take a final snapshot if you want to keep data)
4. Delete NAT gateways if any
5. Delete VPC
