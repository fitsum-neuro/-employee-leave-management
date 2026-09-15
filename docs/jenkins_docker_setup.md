# Jenkins Docker Setup Guide

**Author**: Eyob Kassaye (ATE/4534/16) — Person 3, Test Automation Engineer & CI/CD  
**Course**: Software Testing & Validation  
**Project**: Employee Leave Management System

---

## Overview

This guide explains how to run the project's Jenkins CI pipeline using Docker.  
The Jenkins server runs inside a Docker container, and the Flask application is tested
against its SQLite database during each pipeline run.

---

## Prerequisites

| Tool | Minimum Version | Notes |
|------|----------------|-------|
| Docker Desktop | 24.x | Must be running |
| Git | 2.x | Repository must be cloned |
| Chrome / Chromedriver | stable | Only needed for Selenium system tests |

---

## Step 1 — Start Jenkins in Docker

```bash
# Pull the Long-Term Support Jenkins image
docker pull jenkins/jenkins:lts

# Create a persistent volume so data survives container restarts
docker volume create jenkins_home

# Start Jenkins container
docker run -d \
  --name jenkins \
  -p 8080:8080 \
  -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  jenkins/jenkins:lts
```

> **Note**: Mounting `/var/run/docker.sock` allows Jenkins to spawn Docker containers  
> from within the pipeline (Docker-in-Docker), which is useful for Selenium in CI.

---

## Step 2 — Unlock Jenkins

1. Open **http://localhost:8080** in your browser.
2. Run the following to retrieve the initial admin password:
   ```bash
   docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
   ```
3. Paste the password into the browser prompt and click **Continue**.
4. Choose **Install suggested plugins** and wait for installation to complete.
5. Create an admin user account.

---

## Step 3 — Install Required Plugins

In **Manage Jenkins → Plugins → Available plugins**, install:

| Plugin | Purpose |
|--------|---------|
| **Pipeline** | Enables declarative `Jenkinsfile` syntax |
| **GitHub** | GitHub webhook integration |
| **HTML Publisher** | Publishes coverage HTML reports |
| **AnsiColor** | Coloured console output |
| **Workspace Cleanup** | Cleans workspace between runs |

Click **Install** and restart Jenkins when prompted.

---

## Step 4 — Install Python inside Jenkins

The pipeline needs Python 3.10+ inside the Jenkins agent environment.

```bash
# Open a shell inside the running Jenkins container
docker exec -it --user root jenkins bash

# Install Python, pip, and Chrome dependencies
apt-get update -y
apt-get install -y python3 python3-pip python3-venv \
    wget gnupg curl unzip

# Install Google Chrome (for Selenium system tests)
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list
apt-get update -y
apt-get install -y google-chrome-stable

# Install matching ChromeDriver
CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d. -f1)
wget -q "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}" -O /tmp/cv
DRIVER_VERSION=$(cat /tmp/cv)
wget -q "https://chromedriver.storage.googleapis.com/${DRIVER_VERSION}/chromedriver_linux64.zip" -O /tmp/cd.zip
unzip -q /tmp/cd.zip -d /usr/local/bin/
chmod +x /usr/local/bin/chromedriver

exit
```

---

## Step 5 — Create a Pipeline Job

1. From the Jenkins home screen, click **New Item**.
2. Enter name: `employee-leave-management`
3. Select **Pipeline** → click **OK**.
4. Under **Pipeline**:
   - Definition: **Pipeline script from SCM**
   - SCM: **Git**
   - Repository URL: `https://github.com/fitsum-neuro/-employee-leave-management.git`
   - Branch: `*/main` (or `*/person3` for this branch)
   - Script Path: `Jenkinsfile`
5. Click **Save**.

---

## Step 6 — Configure GitHub Webhook (Optional)

To trigger builds automatically on every push:

1. In GitHub → Repository → **Settings → Webhooks → Add webhook**:
   - Payload URL: `http://<YOUR_HOST>:8080/github-webhook/`
   - Content type: `application/json`
   - Events: **Just the push event**
2. In Jenkins job → **Configure → Build Triggers** → ✅ **GitHub hook trigger for GITScm polling**

> **Tip**: For local testing use [ngrok](https://ngrok.com/) to expose your local Jenkins:
> ```bash
> ngrok http 8080
> ```

---

## Step 7 — Run the Pipeline

1. Open the job page and click **Build Now**.
2. Click the build number → **Console Output** to follow the live log.
3. After the build, click **Coverage Report** in the sidebar to view HTML coverage.

### Expected Pipeline Stages

```
Setup
  └─ Creates .venv, installs all dependencies

Unit Tests
  └─ Runs test_business_logic, test_routes, test_decision_table, test_state_transitions
  └─ Publishes unit test coverage HTML

Integration Tests
  └─ Runs test_integration (route → business_logic → model → SQLite DB)
  └─ Publishes integration coverage HTML

System Tests
  └─ Starts Flask on port 5001
  └─ Runs Selenium end-to-end tests in headless Chrome
  └─ Kills Flask server after tests

Defect Probes  [UNSTABLE if defects are still open — expected]
  └─ Runs pytest -m defect; marks build UNSTABLE (not failed)
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `python3: command not found` | Run Step 4 to install Python inside Jenkins container |
| `chromedriver: not found` | Re-run the ChromeDriver install commands in Step 4 |
| Port 8080 already in use | Change the host port: `-p 9090:8080` and open `http://localhost:9090` |
| Selenium tests skip | Set `SELENIUM_DRIVER=chrome` in job environment variables |
| Coverage report not published | Ensure the **HTML Publisher** plugin is installed (Step 3) |

---

## Regression Demonstration Procedure

As required by the assignment, here is how to produce a **fail → fix → pass** demo:

### 1 — Introduce a deliberate bug

```python
# In app/business_logic.py, temporarily change:
if days_requested < 1:
    return False, "Days requested must be at least 1"
# TO:
if days_requested < 0:   # BUG: allows 0-day requests
    return False, "Days requested must be at least 1"
```

### 2 — Push and observe CI failure

```bash
git add app/business_logic.py
git commit -m "demo: introduce boundary bug for regression demo"
git push
```
Take a screenshot of the red/failed build in GitHub Actions or Jenkins.

### 3 — Fix the bug

```bash
# Revert the change
git revert HEAD
git push
```
Take a screenshot of the green/passing build.

### 4 — Include in report

Paste both screenshots into `docs/test_summary_report.md` under the
**Regression Demonstration** section.
