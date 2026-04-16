Here is the complete guide in **Markdown format**. You can copy this directly into a file named `README.md` in your GitHub repository or share it as a setup document with your team.

***

# 🎓 Frappe LMS Collaboration Guide

This repository contains a customized version of the Frappe LMS application. Follow this guide to set up your local development environment and stay in sync with the team.

## 🛠 Prerequisites
Before starting, ensure your machine has the following installed:
- **Frappe Bench** (Version 15)
- **Python** 3.10 or 3.11
- **Node.js** v18 or v20
- **MariaDB** & **Redis**

---

## 🚀 1. Initial Setup
Run these commands from inside your `frappe-bench` directory.

### Step A: Get the Applications
The LMS app requires the `payments` app to function.
```bash
# 1. Download the mandatory dependency
bench get-app payments

# 2. Download our customized LMS repository
# Replace [REPO_URL] with https://github.com/MikiyasWT/lms.oih.git
bench get-app [REPO_URL] lms
```

### Step B: Create a Local Site
Create a dedicated site for development. You can name it whatever you like (e.g., `lms.test`).
```bash
bench new-site lms.test
```
*Note: Keep track of the **Administrator** password you set.*

### Step C: Install Apps on the Site
```bash
# Install the payments dependency first
bench --site lms.test install-app payments

# Install the LMS application
bench --site lms.test install-app lms
```

### Step D: Sync Database Configurations (Crucial)
To pull in the custom fields, client scripts, and UI changes made by other team members, run:
```bash
bench --site lms.test migrate
```

### Step E: Access the Site
```bash
# Map the site name to your local IP
bench --site lms.test add-to-hosts

# Start the server
bench start
```
Go to: `http://lms.test:8000/lms`

---

## 🔄 2. Daily Team Workflow

### 📥 To Receive Changes (Pulling)
If a teammate has pushed new code or new custom fields, follow these steps:
1. **Pull the latest code:**
   ```bash
   cd apps/lms
   git pull origin main
   ```
2. **Sync the database changes:**
   ```bash
   cd ../..
   bench --site lms.test migrate
   ```

### 📤 To Share Changes (Pushing)

#### Scenario 1: You edited Files (Python, JS, HTML, CSS)
If you only changed files in your code editor:
```bash
cd apps/lms
git add .
git commit -m "Update: Added logic for course certificates"
git push origin main
```

#### Scenario 2: You made changes in the Browser (UI)
If you added **Custom Fields**, **Client Scripts**, or used **Customize Form**:
1. **Export database settings to files:**
   ```bash
   bench --site lms.test export-fixtures
   ```
2. **Commit and Push the generated JSON files:**
   ```bash
   cd apps/lms
   git add .
   git commit -m "Fix: Added custom field to Lesson DocType"
   git push origin main
   ```

---

## ⚠️ Important Rules for Developers
1. **Never track the `frappe-bench` folder.** Only track the `apps/lms` folder.
2. **Always run `bench migrate`** after you pull changes. If you don't, your local database won't match the code requirements and may crash.
3. **Fixtures vs. Data:** 
   - `export-fixtures` saves **Configuration** (new fields, scripts, hidden buttons).
   - It does **NOT** save **Data** (actual courses, lessons, or students you created).
   - If you need to share actual course content, you must share a database backup file.

---

## 🏗 Common Troubleshooting
- **404 Not Found:** Run `bench config dns_multitenant on` and then `bench use lms.test`.
- **Payments Error:** If you see `No module named 'payments'`, ensure you ran `bench get-app payments`.
- **UI/CSS issues:** Run `bench build --app lms` to recompile the frontend assets.
