# Fault Tolerance Test Scenarios

These are the live demos to run on presentation day. For each: what you do,
what should happen, and what it proves.

---

## Test 1 — Load balancing across AZs (baseline)

**What you do:**
```bash
for i in {1..10}; do curl -s http://$ALB/health | jq -r .host; done
```

**Expected:** Two different `ip-10-0-x-x` hostnames appear in the output — one from AZ-a, one from AZ-b.

**What it proves:** The ALB is actively distributing requests across both EC2 instances in different AZs.

---

## Test 2 — Web tier failover (kill an EC2)

**What you do:**
1. Open the site in a browser; note the hostname in the footer.
2. In the AWS console, **stop** `clinic-web-1`.
3. Refresh the browser several times over the next 30–60 seconds.

**Expected:**
- Within ~30 seconds, the ALB marks `web-1` as **unhealthy** (visible in Target Groups).
- The site keeps working — every refresh shows `web-2`'s hostname.
- No errors to the user.

**What it proves:** *High availability at the web tier.* One full server died; the service stayed up because the other AZ picked up 100% of the traffic.

**Recovery:** Start `web-1` again. The ALB re-adds it once `/health` returns 200.

---

## Test 3 — Database failover (Multi-AZ)

**What you do:**
1. Open the patient list, note the records.
2. In RDS console, select `clinic-db` → **Actions → Reboot** → tick **Reboot with failover**.
3. Refresh the site every few seconds.

**Expected:**
- For ~30–60 seconds you may see an error page or brief delay (pool_pre_ping catches dead connections).
- RDS promotes the standby in AZ-b. The DNS name `clinic-db.XXXX...` now resolves to the new primary.
- Site recovers automatically — your data is all still there.

**What it proves:** *Synchronous replication + automatic failover at the DB tier.* The standby had every committed write; no data was lost.

**Key talking point for your report:** Multi-AZ uses synchronous replication (`SYNC`), so the standby is always byte-for-byte current. A read replica uses async and would lose the last few seconds of writes — trade-off to mention.

---

## Test 4 — Application-level crash recovery

**What you do:**
1. SSH into `web-1` (or Session Manager).
2. `sudo systemctl kill clinic`  — kills the gunicorn process.
3. Immediately: `curl http://localhost:5000/health`.

**Expected:**
- First curl fails (connection refused).
- Within 3 seconds, systemd restarts the service (`Restart=always, RestartSec=3`).
- Next curl returns 200.

**What it proves:** Defense in depth — even a single-process crash self-heals without human intervention.

---

## Test 5 — Data consistency across AZs

**What you do:**
1. From the browser (hitting `web-1` via ALB), add patient "Test Alice".
2. Force the next request to the other EC2 (stop web-1 briefly, or just refresh until footer hostname changes).
3. The new patient should still be visible.

**Expected:** "Test Alice" appears regardless of which EC2 serves the request.

**What it proves:** There's **one** source of truth (RDS), and both app servers read from the same replicated store. This is the essence of a distributed database system: compute is replicated, but state is consistent.

---

## What to screenshot for the report

1. Target Group health showing both targets healthy, then one unhealthy during Test 2.
2. RDS "Multi-AZ: Yes" in the DB instance summary.
3. CloudWatch metrics: `HealthyHostCount` dropping from 2 → 1 → 2 during Test 2.
4. Two different footer hostnames across browser refreshes.
5. The RDS events log showing "Multi-AZ instance failover started/completed".
