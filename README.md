# Web Automation Project - Installation Guide

This project is a web automation system that tests web platforms across multiple countries using Selenium WebDriver. It includes support for AppTweak integration for app store testing.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation Steps](#installation-steps)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have the following installed on your system:

- **Python 3.8 or higher** - [Download Python](https://www.python.org/downloads/)
- **Git** (optional, for version control) - [Download Git](https://git-scm.com/)
- **Google Chrome or Chromium browser** - Latest version recommended

### System Requirements
- **Windows 10/11** (or Linux/macOS with Python support)
- **Minimum 4GB RAM**
- **500MB free disk space** for dependencies and logs
- **Internet connection** for downloading drivers and accessing web platforms

---

## Installation Steps

### Step 1: Clone or Download the Project

If you have Git installed:
```powershell
git clone <repository-url>
cd WEB_AUTOMATION
```

Or download the project folder manually and navigate to it.

### Step 2: Create a Python Virtual Environment

Navigate to the project directory and create a virtual environment:

```powershell
# On Windows PowerShell
python -m venv venv

# Activate the virtual environment
.\venv\Scripts\Activate.ps1

# If you get an execution policy error, run:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

On Linux/macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Upgrade pip, setuptools, and wheel

Ensure you have the latest package installer tools:

```powershell
python -m pip install --upgrade pip setuptools wheel
```

### Step 4: Install Project Dependencies

Install all required Python packages from requirements.txt:

```powershell
pip install -r requirements.txt
```

This will install:
- **selenium** (>= 4.15.0) - Web browser automation framework
- **webdriver-manager** (>= 4.0.1) - Automatic WebDriver management for Chrome


## Troubleshooting

### Issue 1: Virtual Environment Activation Fails

**Error**: `ExecutionPolicy`

**Solution**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Issue 2: Chrome Driver Not Found

**Error**: `no such file or directory: chromedriver`

**Solution**:
The `webdriver-manager` package should handle this automatically. If it doesn't:
```powershell
pip install --upgrade webdriver-manager
```
