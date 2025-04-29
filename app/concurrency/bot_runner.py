import sys
import os
import time
import multiprocessing
from typing import List, Optional

# --- Placeholder for the actual bot runner function ---
# Moved from manager.py to address potential Windows multiprocessing issues.


def run_bot_instance(profile_id: str, stats_queue: multiprocessing.Queue, log_queue: multiprocessing.Queue, assigned_city: Optional[str], usernames_list: List[str]):
    """
    The target function for each bot process.
    Handles setup, running the main chat loop, and cleanup for one profile.

    Adds the project root to sys.path to ensure imports work correctly in the subprocess.

    Args:
        profile_id: The AdsPower profile ID for this instance.
        stats_queue: The queue to send statistics back to the manager.
        log_queue: The queue to send log messages back to the manager.
        assigned_city: The specific city assigned for registration purposes for this instance.
        usernames_list: A list of usernames to attempt during registration.
    """
    # --- Helper function for logging within the bot process ---
    def _log(message: str):
        """Sends a formatted log message to the log queue."""
        # Original, simpler fallback logic
        try:
            log_queue.put({'bot_id': profile_id, 'message': message})
        except Exception as log_err:
            # Fallback to print if queue fails
            print(
                f"[Bot Process {os.getpid()} - LOG QUEUE ERROR for {profile_id}] {log_err}")
            print(
                f"[Bot Process {os.getpid()} - FALLBACK LOG for {profile_id}] {message}")

    # --- ORIGINAL CODE --- # Removed "RESTORED"
    # --- Add project root to sys.path ---
    # Calculate the path to the project root (two levels up from this file's directory)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        _log(f"Added {project_root} to sys.path")
    _log("sys.path modification complete.")
    # --- End path modification ---

    _log(f"Starting process for profile: {profile_id}")
    driver = None
    # Dictionary to hold user states in memory for this specific bot instance
    user_states_in_memory = {}
    try:
        # 1. Import necessary functions within the process context
        _log("Attempting internal imports...")
        # Selenium imports needed for consent/registration checks
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        # Removed NoSuchElementException
        from selenium.common.exceptions import TimeoutException

        # Import core logic - ensure these paths are correct relative to project_root
        from app.bot_core.selenium_handler import start_adspower_browser, close_adspower_browser, find_element_with_wait, click_element  # Import helpers
        from app.bot_core.chat_logic import handle_chat_cycle
        # Import registration logic too, as chat_logic might call it
        # This import needs to happen *inside* the process function
        from app.bot_core.registration import handle_registration_process
        _log("Internal imports successful.")

        # 2. Start the browser
        _log(
            f"Attempting to start AdsPower browser for profile {profile_id}...")
        # Pass log_queue to selenium handler functions if they need logging
        driver = start_adspower_browser(
            profile_id, log_queue)  # Pass log_queue

        if driver:
            _log(
                f"start_adspower_browser returned a driver object for {profile_id}.")
        else:
            _log(
                f"start_adspower_browser returned None for {profile_id}. Exiting process.")
            return  # Exit process if browser fails to start

        # 3. Navigate to initial page
        _log(
            f"Browser start sequence seemingly complete for profile {profile_id}.")

        # --- Navigate to Chatib and close other tabs ---
        try:
            initial_handle = driver.current_window_handle
            _log(
                f"Initial handle: {initial_handle}. Navigating to chatib.us...")
            driver.get("https://chatib.us/")
            time.sleep(3)  # Allow page to load

            chatib_handle = driver.current_window_handle
            _log(f"Current handle after navigation: {chatib_handle}")

            all_handles = driver.window_handles
            if len(all_handles) > 1:
                _log(f"Found {len(all_handles)} tabs. Closing extras...")
                for handle in all_handles:
                    if handle != chatib_handle:
                        try:
                            driver.switch_to.window(handle)
                            driver.close()
                            _log(f"Closed extra tab: {handle}")
                        except Exception as close_err:
                            _log(f"Error closing tab {handle}: {close_err}")
                driver.switch_to.window(chatib_handle)
                _log(f"Switched back to Chatib tab: {chatib_handle}")
            else:
                _log("Only one tab open.")

        except Exception as nav_err:
            _log(
                f"Error during navigation/tab closing for {profile_id}: {nav_err}")
            raise
        # --- End navigation/tab closing ---

        # --- Check for Ad Overlay Immediately After Load ---
        try:
            if "#google_vignette" in driver.current_url:
                _log("Detected ad URL fragment immediately after load. Refreshing...")
                driver.refresh()
                _log("Waiting for page body after ad refresh...")
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                _log("Page body found after ad refresh.")
                time.sleep(2)
        except Exception as initial_ad_err:
            _log(f"Error during initial ad check/refresh: {initial_ad_err}")
        # --- End Initial Ad Check ---

        # --- Sequential Startup Check: Consent -> Registration -> Logged In ---
        proceed_to_chat = False
        try:
            # Step 1: Attempt to Accept Consent Popup (Non-blocking)
            _log("Step 1: Checking for consent popup...")
            time.sleep(1)

            def _try_accept_consent(drv):
                potential_xpaths = [
                    "//button[@class=' css-47sehv']", "//button[@mode='primary']",
                    "//button[@jsname='LgbsSe']", "(//div[contains(@class, 'modal-footer') or contains(@class, 'button-container') or @class='qc-cmp2-summary-buttons']//button)[2]",
                    "//button[contains(@class, 'accept') or contains(@class, 'confirm') or contains(@class, 'primary') or contains(@class, 'agree')]",
                    "//button[contains(translate(., 'ACCEPTERGODKÄNNAGREE', 'acceptergodkännagree'), 'accept') or contains(translate(., 'ACCEPTERGODKÄNNAGREE', 'acceptergodkännagree'), 'godkänn') or contains(translate(., 'ACCEPTERGODKÄNNAGREE', 'acceptergodkännagree'), 'agree')]",
                    "//button[contains(translate(., 'GOT IT', 'got it'), 'got it')]", "//button[contains(translate(., 'UNDERSTAND', 'understand'), 'understand')]",
                    "//a[contains(translate(., 'ACCEPTERGODKÄNNAGREE', 'acceptergodkännagree'), 'accept') or contains(translate(., 'ACCEPTERGODKÄNNAGREE', 'acceptergodkännagree'), 'godkänn') or contains(translate(., 'ACCEPTERGODKÄNNAGREE', 'acceptergodkännagree'), 'agree')]",
                    "//div[@role='button' and (contains(translate(., 'ACCEPTERGODKÄNNAGREE', 'acceptergodkännagree'), 'accept') or contains(translate(., 'ACCEPTERGODKÄNNAGREE', 'acceptergodkännagree'), 'godkänn') or contains(translate(., 'ACCEPTERGODKÄNNAGREE', 'acceptergodkännagree'), 'agree'))]",
                ]
                for xpath in potential_xpaths:
                    try:
                        # Change timeout from 2 to 1 second per XPath attempt
                        consent_button = WebDriverWait(drv, 1).until(
                            EC.element_to_be_clickable((By.XPATH, xpath)))
                        if consent_button:
                            _log(
                                f"Found potential consent button with XPath: {xpath}. Clicking...")
                            try:
                                drv.execute_script(
                                    "arguments[0].click();", consent_button)
                                _log("Clicked consent button via JavaScript.")
                                return True
                            except Exception as js_click_err:
                                _log(
                                    f"JS click failed ({js_click_err}), trying Selenium click...")
                                # Pass log_queue here too
                                if click_element(consent_button, log_queue):
                                    _log(
                                        "Clicked consent button via Selenium click.")
                                    return True
                                else:
                                    _log(
                                        f"Selenium click also failed for XPath: {xpath}")
                                    continue
                    except TimeoutException:
                        continue
                    except Exception as e:
                        _log(f"Error trying consent XPath {xpath}: {e}")
                        continue
                return False

            consent_clicked = _try_accept_consent(driver)
            if consent_clicked:
                _log("Consent handled.")
                time.sleep(1)
            else:
                _log("Consent popup not found or not clicked.")

            # Step 2: Check for Registration Page
            _log("Step 2: Checking for registration page...")
            registration_needed = False
            try:
                username_field_xpath = "//input[@id='username']"
                username_field = find_element_with_wait(
                    driver, By.XPATH, username_field_xpath, timeout=3, log_queue=log_queue)  # Pass log_queue
                if username_field:
                    _log("Registration page detected.")
                    registration_needed = True
                else:
                    _log("Registration page not detected.")
            except TimeoutException:
                _log("Registration page not detected (timeout).")
            except Exception as reg_check_err:
                _log(f"Error checking for registration page: {reg_check_err}")

            # Step 3: Perform Registration if Needed
            if registration_needed:
                _log("Step 3: Attempting registration...")
                registration_result = handle_registration_process(
                    driver, assigned_city, usernames_list, log_queue)  # Pass log_queue
                if registration_result:
                    _log("Registration successful.")
                    proceed_to_chat = True
                else:
                    _log("Registration failed. Exiting process.")
                    return

            # Step 4: Check for Logged-In State (if registration wasn't needed/performed)
            if not proceed_to_chat and not registration_needed:
                _log("Step 4: Checking for logged-in state...")
                logged_in = False
                try:
                    inbox_button_xpath = "//li[@onclick='inbox()']"
                    fallback_user_list_xpath = "//div[@class='pills_items pills_items_users']"
                    try:
                        find_element_with_wait(
                            driver, By.XPATH, inbox_button_xpath, timeout=5, log_queue=log_queue)  # Pass log_queue
                        _log("Logged-in state confirmed (Inbox button found).")
                        logged_in = True
                    except TimeoutException:
                        _log("Inbox button not found, checking fallback user list...")
                        try:
                            find_element_with_wait(
                                driver, By.XPATH, fallback_user_list_xpath, timeout=3, log_queue=log_queue)  # Pass log_queue
                            _log(
                                "Logged-in state confirmed (Fallback user list found).")
                            logged_in = True
                        except TimeoutException:
                            _log("Fallback user list also not found.")

                    if logged_in:
                        proceed_to_chat = True
                    else:
                        _log(
                            "Neither registration page nor logged-in indicator found. Unknown state.")
                        _log("Exiting due to unknown page state.")
                        return

                except Exception as login_check_err:
                    _log(
                        f"Error checking for logged-in state: {login_check_err}")
                    _log("Exiting due to error during logged-in check.")
                    return

            # Step 5: Accept Chatib Terms if Present (Only if proceeding to chat)
            if proceed_to_chat:
                _log("Step 5: Checking for Chatib terms popup...")
                try:
                    terms_button_xpath = "//button[@class='btn btn-primary confirm_decline agree']"
                    terms_button = find_element_with_wait(
                        driver, By.XPATH, terms_button_xpath, timeout=5, log_queue=log_queue)  # Pass log_queue
                    if terms_button:
                        _log("Found Chatib terms button. Clicking...")
                        if click_element(terms_button, log_queue):  # Pass log_queue
                            _log("Clicked Chatib terms button.")
                            time.sleep(1)
                        else:
                            _log("Failed to click Chatib terms button.")
                    else:
                        _log("Chatib terms button not found (or timed out).")
                except TimeoutException:
                    _log("Chatib terms button not found (timeout).")
                except Exception as terms_err:
                    _log(f"Error checking/clicking Chatib terms: {terms_err}")
            # --- End Sequential Startup Check ---

        except Exception as startup_err:
            print(
                f"[Bot Process {os.getpid()}] Critical error during startup sequence: {startup_err}. Exiting.", file=sys.stderr)
            _log(
                f"Critical error during startup sequence: {startup_err}. Exiting.")
            return

        # 4. Run the main chat cycle (only if startup sequence was successful)
        if proceed_to_chat:
            _log(
                f"Startup successful. Proceeding to chat cycle for profile {profile_id}.")
            # Pass the in-memory state dictionary to the chat cycle handler
            handle_chat_cycle(driver, profile_id, stats_queue, log_queue,
                              assigned_city, usernames_list, user_states_in_memory)  # Added user_states_in_memory

    except Exception as e:
        print(
            f"[Bot Process {os.getpid()}] Unhandled exception in run_bot_instance for profile {profile_id}: {e}", file=sys.stderr)
        _log(f"Unhandled exception in run_bot_instance: {e}")
    finally:
        _log(f"Cleaning up for profile {profile_id}...")
        if driver:
            try:
                # Ensure close_adspower_browser is imported if not already
                from app.bot_core.selenium_handler import close_adspower_browser
                close_adspower_browser(profile_id, log_queue)  # Pass log_queue
            except ImportError:
                _log("Could not import close_adspower_browser for cleanup.")
            except Exception as cleanup_err:
                _log(
                    f"Error during close_adspower_browser call: {cleanup_err}")

        _log(f"Finished process for profile {profile_id}.")
