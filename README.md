# Chatib Automated Bot

## Description

This project is a Python-based bot designed to automate interactions on the Chatib platform. It utilizes Selenium for browser automation, integrates with the AdsPower local API for managing browser profiles, and provides a Flask-based web dashboard for configuration, control, and monitoring.

## Features

*   **Multi-Instance Operation:** Runs multiple bot instances concurrently using Python's `multiprocessing`.
*   **AdsPower Integration:** Leverages the AdsPower local API to start, stop, and connect to specific browser profiles, aiding in anti-detection and account management.
*   **Automated Registration:** Handles the Chatib registration process, including dealing with taken usernames and Captcha errors (by retrying).
*   **Chat Interaction Logic:** Navigates the Chatib interface, finds users, sends pre-defined message sequences in phases, detects replies, and handles potential logouts.
*   **Web Dashboard (Flask):**
    *   View bot status (running/stopped, active processes).
    *   Start and stop all bot instances globally.
    *   Start and stop individual bot instances.
    *   View aggregated statistics (links sent, conversations started).
    *   View live logs for individual bot instances.
    *   Configure bot settings (`config.json`) and message sequences (`messages.txt`).
    *   Toggle Headless Mode (requires AdsPower API support).
*   **Configuration:** Centralized configuration via `data/config.json` and `data/messages.txt`.
*   **Robustness:** Includes error handling for common issues like popups, ads, page refreshes, and Selenium exceptions.

## Requirements

*   **Python 3.x**
*   **AdsPower:** The AdsPower application must be installed and running locally.
*   **Required Python Packages:** Listed in `requirements.txt` (Flask, Selenium, requests).

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd Chatib-Automated # Or your project directory name
    ```
2.  **Run the setup script:** This will create a Python virtual environment (`venv`) and install the required packages from `requirements.txt`.
    ```bash
    setup.bat
    ```
    *(On Linux/macOS, you might need to adapt this script or run the commands manually: `python -m venv venv`, `source venv/bin/activate` or `venv\Scripts\activate`, `pip install -r requirements.txt`)*

## Configuration

Before running the bot, configure the necessary settings in the `data/` directory:

1.  **`data/config.json`:**
    *   `adspower_api_key`: Your AdsPower API key (if required by your AdsPower version/settings).
    *   `adspower_api_host`: The local API endpoint for AdsPower (usually `http://local.adspower.net:50325`).
    *   `onlyfans_link`: The link to be included in messages (used where `{onlyfans_link}` placeholder exists).
    *   `max_concurrent_browsers`: Maximum number of bot instances to run simultaneously.
    *   `run_headless`: `true` or `false`. Set to `true` to attempt launching AdsPower profiles headlessly (requires AdsPower API support).
    *   `registration_defaults`: Default age, country code, and city options for registration.
    *   `usernames`: A list of usernames the bot should try during registration (one per line). If empty or exhausted, random usernames might be generated.
    *   `adspower_profile_ids`: A list of AdsPower Profile IDs (one per line) that the bot will use to launch instances.
2.  **`data/messages.txt`:**
    *   Enter the sequence of messages the bot should send, one message per line.
    *   Use the placeholder `{onlyfans_link}` where you want the configured link to be inserted.
    *   Note: The last 3 messages are sent in quick succession after a delay.

## Running the Bot

1.  **Ensure AdsPower is running.**
2.  **Activate the virtual environment:**
    ```bash
    venv\Scripts\activate
    ```
    *(Or `source venv/bin/activate` on Linux/macOS)*
3.  **Start the dashboard and bot manager:**
    ```bash
    start_dashboard.bat
    ```
    *(This script likely runs `python app/main.py`. On Linux/macOS, you might run `python app/main.py` directly).*
4.  **Access the Dashboard:** Open your web browser and navigate to `http://127.0.0.1:5000` (or the address shown in the terminal).
5.  **Use the Dashboard:**
    *   Review and save configuration settings.
    *   Click "Start Bots" to launch the configured AdsPower profiles and begin automation.
    *   Monitor status, statistics, and logs.
    *   Click "Stop Bots" to terminate all running bot instances.
    *   Use individual "Stop" buttons next to active bot IDs to stop specific instances.

## Notes

*   The bot's functionality is heavily dependent on the Chatib website structure and AdsPower API behavior. Changes to either may require code updates.
*   Headless mode functionality depends on the AdsPower API supporting the `headless=1` parameter.
*   Ensure the AdsPower Profile IDs listed in `config.json` are valid and accessible in your AdsPower application.
