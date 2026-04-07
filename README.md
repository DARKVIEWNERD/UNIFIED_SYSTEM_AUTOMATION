# Web Automation Project - Installation Guide

This project is a web automation system that tests web platforms across multiple countries using Selenium WebDriver. It includes support for AppTweak integration for app store testing and a universal engine for additional platform types.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation Steps](#installation-steps)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Automation Flow](#automation-flow)
- [Troubleshooting](#troubleshooting)
- [Changelog](#changelog)

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
cd WEB_SCRAPE_AUTOMATION
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

---

## Automation Flow

The main automation process (`run_automation_process`) loops over every combination of **country × web platform × category** and saves an MHTML snapshot for each, then immediately extracts rows into `All_platforms.xlsx`.

### Platform Types

There are three platform types handled in the automation loop:

#### 1. AppTweak (`type: "apptweak"`)
Handled by `AppTweakIntegration`. Fires per-file callbacks (`on_success`, `on_fail`) that update the GUI counters in real time as each file is processed.

#### 2. Universal (`type: "universal"`)
Handled by `execute_universal_flow`. Same callback pattern as AppTweak — `on_success` and `on_fail` update the GUI per file.

#### 3. Normal URL
Standard Selenium flow. For each URL it:
1. Loads the page via `test_url_with_retry()`
2. Checks for human verification (CAPTCHA) — waits for manual resolution if detected
3. Validates the page is usable via `is_page_unusable()`
4. Saves an MHTML snapshot
5. Immediately calls `extract_and_append()` to write rows to `All_platforms.xlsx`

### Per-URL Failure Reasons

| Failure | Logged as |
|---|---|
| Verification timeout | `"Verification timeout"` |
| Page unusable / bad redirect | reason string from `is_page_unusable()` |
| Page load exception | `"Load error: ..."` |
| MHTML save failed | `"MHTML save error: ..."` |

### Resume Support

Already-completed URLs are tracked in `existing_snapshots`. If the automation is restarted, any URL whose `(country, platform, app_platform, category)` key is already in the snapshot folder is skipped automatically.

---

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

### Issue 3: GUI Failed Counter Not Updating

If the failed count in the UI does not increment during a normal URL run, ensure you are using the latest `automation_runner.py`. Earlier versions had a bug where failures that triggered a `continue` (verification timeout, page unusable, load error) skipped the GUI counter update entirely. This is fixed in the current version — see [Changelog](#changelog).

---

## Changelog

### Latest
- **Fixed: GUI failed counter not updating on per-URL failures (normal URL platform)**
  - Verification timeout, page unusable, and load error failures all use `continue` to skip to the next URL. Previously this bypassed the `set_counts()` call, so the GUI failed counter never incremented for those cases.
  - Fix: each of the three failure paths now immediately appends to `all_failed` and calls `set_counts(len(all_successful), len(all_failed))` before the `continue`, so the GUI updates in real time as failures occur.
  - Affected file: `automation_runner.py` — normal URL loop (lines ~382–409)
