import time
import random
import os  # Add os import
import multiprocessing  # Add multiprocessing import
from typing import Optional, List  # Added List for type hint
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# Assuming selenium_handler provides the necessary driver and helper functions
try:
    from .selenium_handler import find_element_with_wait, click_element, send_keys_to_element
    from app.config.manager import load_config
except ImportError:
    # Fallback for potential path issues or running script directly
    # Use print here as logging might not be set up yet
    print("Error: Could not import selenium_handler or config manager. Ensure PYTHONPATH is set correctly or run from project root.")
    # Define dummy functions to allow script loading, but it won't work
    # Add log_queue and profile_id to dummy functions for signature consistency if needed elsewhere
    def find_element_with_wait(
        driver, by, value, timeout=10, log_queue=None, profile_id=None): return None

    def click_element(element, log_queue=None, profile_id=None): return False
    def send_keys_to_element(
        element, text, log_queue=None, profile_id=None): return False

    def load_config(): return {}


# XPaths from xpaths_registration.md (consider loading these dynamically later)
XPATHS_REGISTRATION = {
    "username_input": "//input[@id='username']",
    "age_select": "//select[@id='age']",
    "country_select": "//select[@id='login_country']",
    "city_select": "//select[@id='city']",
    "form_area_to_click": "//div[@class='chatib-form guest-loginbox-shadow']",
    "start_chat_button_primary": "//input[@data-action='submit']",
    "start_chat_button_backup": "//input[@class='btn start-chat-btn btn-block start-chat-main username_check g-recaptcha']",
    "username_error_text": "//*[contains(text(), 'Username contains restricted words. Available alternatives:')]"
}


def generate_random_username(base_length=8):
    """Generates a simple random username."""
    # Very basic generator, can be improved
    import string
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(base_length))


def select_option_by_value(driver, select_xpath, value, log_queue: multiprocessing.Queue, profile_id: str):
    """Selects an option from a dropdown by its value attribute. Logs actions."""
    # Define _log locally for this function
    def _log(message: str):
        try:
            log_queue.put({'bot_id': profile_id, 'message': message})
        except Exception as log_err:
            print(
                f"[Bot Process {os.getpid()} - LOG QUEUE ERROR for {profile_id}] {log_err}\nFALLBACK LOG: {message}")

    # Pass log info
    select_element = find_element_with_wait(
        driver, By.XPATH, select_xpath, log_queue=log_queue, profile_id=profile_id)
    if not select_element:
        _log(f"Error: Could not find select element: {select_xpath}")
        return False
    try:
        select = Select(select_element)
        select.select_by_value(value)
        _log(f"Selected option with value '{value}' from {select_xpath}")
        return True
    except NoSuchElementException:
        _log(f"Error: Option with value '{value}' not found in {select_xpath}")
        return False
    except Exception as e:
        _log(f"Error selecting option '{value}' from {select_xpath}: {e}")
        return False


def attempt_registration(driver, username, age, country_code, city, log_queue: multiprocessing.Queue, profile_id: str):
    """Fills the registration form and clicks start chat. Logs actions."""
    # Define _log locally for this function
    def _log(message: str):
        try:
            log_queue.put({'bot_id': profile_id, 'message': message})
        except Exception as log_err:
            print(
                f"[Bot Process {os.getpid()} - LOG QUEUE ERROR for {profile_id}] {log_err}\nFALLBACK LOG: {message}")

    _log(
        f"Attempting registration with Username: {username}, Age: {age}, Country: {country_code}, City: {city}")

    # Fill Username
    _log("[REG_ATTEMPT_DEBUG] Finding username input field...")
    # Pass log info
    username_field = find_element_with_wait(
        driver, By.XPATH, XPATHS_REGISTRATION["username_input"], log_queue=log_queue, profile_id=profile_id)
    if username_field:
        # Clear the field before sending keys to prevent accumulation on retries
        _log("[REG_ATTEMPT_DEBUG] Clearing username input field...")
        try:
            username_field.clear()
        except Exception as clear_err:
            _log(f"Warning: Failed to clear username field: {clear_err}")
        _log(
            f"[REG_ATTEMPT_DEBUG] Found username field. Attempting to send keys: '{username}'")
        # Pass log info AND driver instance
        if not send_keys_to_element(driver, username_field, username, log_queue=log_queue, profile_id=profile_id):
            _log(
                f"[REG_ATTEMPT_DEBUG] send_keys_to_element FAILED for username: '{username}'")
            _log("[REG_ERROR] Failed to enter username.")
            return False
        else:
            _log(
                f"[REG_ATTEMPT_DEBUG] send_keys_to_element SUCCEEDED for username: '{username}'")
    else:
        _log("[REG_ATTEMPT_DEBUG] Username input field NOT found.")
        _log("Failed to enter username.")
        return False  # Explicitly return False if field not found

    # Select Age
    _log("[REG_ATTEMPT_DEBUG] Attempting to select age...")
    age_selected = select_option_by_value(
        driver, XPATHS_REGISTRATION["age_select"], age, log_queue=log_queue, profile_id=profile_id)
    _log(
        f"[REG_ATTEMPT_DEBUG] select_option_by_value (Age) returned: {age_selected}")
    if not age_selected:
        # Log warning but DO NOT return False
        _log("[REG_WARN] Failed to select age. Continuing attempt...")
    else:
        _log("[REG_ATTEMPT_DEBUG] Age selected successfully.")

    # Select Country
    _log("[REG_ATTEMPT_DEBUG] Attempting to select country...")
    country_selected = select_option_by_value(
        driver, XPATHS_REGISTRATION["country_select"], country_code, log_queue=log_queue, profile_id=profile_id)
    _log(
        f"[REG_ATTEMPT_DEBUG] select_option_by_value (Country) returned: {country_selected}")
    if not country_selected:
        # Log warning but DO NOT return False
        _log("[REG_WARN] Failed to select country. Continuing attempt...")
    else:
        _log("[REG_ATTEMPT_DEBUG] Country selected successfully.")

    # Select City - Needs a small delay sometimes for city options to populate based on country
    _log("[REG_ATTEMPT_DEBUG] Waiting 1s before selecting city...")
    time.sleep(1)
    _log(f"[REG_ATTEMPT_DEBUG] Attempting to select city '{city}'...")
    city_selected = select_option_by_value(
        driver, XPATHS_REGISTRATION["city_select"], city, log_queue=log_queue, profile_id=profile_id)
    _log(
        f"[REG_ATTEMPT_DEBUG] select_option_by_value (City) returned: {city_selected}")
    if not city_selected:
        # Log warning but DO NOT return False
        _log(
            f"[REG_WARN] Failed to select city '{city}'. It might not be available for country '{country_code}'. Continuing attempt...")
    # else: # No need for else log here, just continue

    # Click form area to potentially enable button (Continue regardless of dropdown success)
    _log("[REG_ATTEMPT_DEBUG] Attempting to click form area...")
    # Pass log info
    form_area = find_element_with_wait(
        driver, By.XPATH, XPATHS_REGISTRATION["form_area_to_click"], timeout=5, log_queue=log_queue, profile_id=profile_id)
    # Pass log info
    click_element(form_area, log_queue=log_queue,
                  profile_id=profile_id)  # Best effort click
    time.sleep(0.5)

    # Click Start Chat Button (try primary, then backup)
    # Pass log info
    start_button = find_element_with_wait(
        driver, By.XPATH, XPATHS_REGISTRATION["start_chat_button_primary"], timeout=5, log_queue=log_queue, profile_id=profile_id)
    if not start_button:
        _log("Primary start button not found, trying backup...")
        # Pass log info
        start_button = find_element_with_wait(
            driver, By.XPATH, XPATHS_REGISTRATION["start_chat_button_backup"], timeout=5, log_queue=log_queue, profile_id=profile_id)

    if start_button:
        # Scroll the button into view before clicking
        _log("Scrolling start chat button into view...")
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", start_button)
            time.sleep(0.5)  # Give a moment for scrolling
        except Exception as scroll_err:
            _log(f"Warning: Failed to scroll start button: {scroll_err}")

    # Pass log info
    if not click_element(start_button, log_queue=log_queue, profile_id=profile_id):
        _log("[REG_ERROR] Failed to click start chat button.")
        return False

    _log("Registration form submitted (Start Chat Now clicked).")
    # Verification moved to handle_registration_process
    return True  # Indicate the click attempt itself was successful


def handle_registration_process(driver, assigned_city: Optional[str] = None, usernames_list: Optional[List[str]] = None, log_queue: Optional[multiprocessing.Queue] = None, profile_id: Optional[str] = None):
    """
    Manages the full registration process, attempting usernames from a list first. Logs actions.

    Args:
        driver: The Selenium WebDriver instance.
        assigned_city: The specific city assigned to this bot instance.
        usernames_list: A list of preferred usernames to try first.
        log_queue: The queue for logging.
        profile_id: The bot's profile ID for logging.

    Returns:
        True if registration seems successful (navigated away from registration page), False otherwise.
    """
    # Define _log locally for this function
    def _log(message: str):
        if log_queue and profile_id:
            try:
                log_queue.put({'bot_id': profile_id, 'message': message})
            except Exception as log_err:
                print(
                    f"[Bot Process {os.getpid()} - LOG QUEUE ERROR for {profile_id}] {log_err}\nFALLBACK LOG: {message}")
        else:
            # Fallback print if no queue or profile_id provided
            # Use _log which handles the None case internally now
            # Keep print here as _log needs queue/id
            print(f"[REGISTRATION - {profile_id or 'NO_PROFILE'}] {message}")

    config = load_config()
    reg_defaults = config.get("registration_defaults", {})
    age = reg_defaults.get("age", "18")
    country_code = reg_defaults.get("country", "US")
    # Default to New York if not specified
    city_options = reg_defaults.get("city_options", [])

    # --- Försök med namn från listan först ---
    _log(f"[REG_DEBUG] Received usernames_list: {usernames_list}")
    if usernames_list:  # Check if list is not None and not empty
        _log(
            f"[REG_DEBUG] Attempting registration with usernames from provided list ({len(usernames_list)} names)...")
        list_attempt_successful = False  # Flag to track if any list username worked
        for i, username in enumerate(usernames_list):  # Add index for logging
            _log(
                f"[REG_DEBUG] List attempt {i+1}/{len(usernames_list)}: Trying username '{username}'")
            # Bestäm stad för detta försök
            if assigned_city:
                city = assigned_city
            elif city_options:
                # Välj slumpmässigt FÖR VARJE FÖRSÖK om ingen är tilldelad? Eller håll fast vid en?
                # För enkelhetens skull, välj en slumpmässig här om ingen är tilldelad.
                city = random.choice(city_options)
                _log(
                    f"Warning: No city assigned, picking randomly for user '{username}': {city}")
            else:
                _log(
                    "Error: No assigned city and no city options in config. Cannot register.")
                return False

            _log(
                f"\nTrying username from list: {username} with city: {city}...")
            # Updated call with keyword args for log_queue and profile_id
            # attempt_registration now only returns True if the click was successful
            if attempt_registration(driver, username, age, country_code, city, log_queue=log_queue, profile_id=profile_id):
                _log(
                    f"Registration attempt submitted for '{username}'. Verifying navigation...")
                # --- NEW Verification Logic ---
                inbox_xpath = "//li[@onclick='inbox()']"
                try:
                    # Wait generously for the inbox button to appear
                    _log(
                        f"Waiting up to 20s for Inbox button ({inbox_xpath})...")
                    inbox_button = find_element_with_wait(
                        driver, By.XPATH, inbox_xpath, timeout=20, log_queue=log_queue, profile_id=profile_id)
                    if inbox_button:
                        _log(
                            f"[REG_SUCCESS] Inbox button found for username '{username}'. Registration successful.")

                        # --- NEW: Check for Ad URL Fragment ---
                        try:
                            current_url = driver.current_url
                            _log(
                                f"Checking current URL for ad fragment: {current_url}")
                            if "#google_vignette" in current_url:
                                _log(
                                    "Detected ad URL fragment (#google_vignette) immediately after registration success. Refreshing...")
                                driver.refresh()
                                _log(
                                    "Waiting for Inbox button again after ad refresh (up to 30s)...")
                                # Need WebDriverWait and EC here (import might be needed if not already global)
                                from selenium.webdriver.support.ui import WebDriverWait
                                from selenium.webdriver.support import expected_conditions as EC
                                try:
                                    WebDriverWait(driver, 30).until(
                                        # Use inbox_xpath defined earlier
                                        EC.element_to_be_clickable(
                                            (By.XPATH, inbox_xpath))
                                    )
                                    _log("Inbox button found after ad refresh.")
                                except TimeoutException:
                                    _log(
                                        "[REG_ERROR] Inbox button did NOT reappear after ad refresh. Registration might be compromised.")
                                    # Returning False here will cause the loop to try the next username, which might be okay.
                                    continue  # Try next username if refresh fails to restore state
                                except Exception as ad_refresh_wait_err:
                                    _log(
                                        f"[REG_ERROR] Error waiting for inbox after ad refresh: {ad_refresh_wait_err}")
                                    continue  # Try next username if refresh fails
                            else:
                                _log(
                                    "No ad URL fragment detected after registration.")
                        except Exception as ad_check_err:
                            _log(
                                f"[REG_WARN] Error checking for ad URL fragment after registration: {ad_check_err}")
                        # --- END Ad Check ---

                        list_attempt_successful = True  # Mark success for the list loop logic
                        return True  # Exit handle_registration_process successfully
                    else:
                        # This case should not happen if find_element_with_wait works correctly (throws TimeoutException)
                        _log(
                            f"[REG_WARN] Inbox button check returned non-None but falsey? Assuming not found for '{username}'.")
                        # Proceed to check if back on registration page

                except TimeoutException:
                    _log(
                        f"[REG_INFO] Inbox button not found within 20s for '{username}'. Checking if back on registration page...")
                    # Check if we are back on the registration page
                    try:
                        username_field_check = find_element_with_wait(
                            driver, By.XPATH, XPATHS_REGISTRATION["username_input"], timeout=3, log_queue=log_queue, profile_id=profile_id)
                        if username_field_check:
                            # Simplified: If username field is found, assume failure and retry.
                            _log(
                                f"[REG_FAIL] Returned to registration page for username '{username}'. Retrying next username.")
                            continue  # Try next username in the list
                        else:
                            # Username field check returned falsey (shouldn't happen with find_element_with_wait)
                            # Treat as uncertain state, proceed to final inbox check below.
                            _log(
                                f"[REG_WARN] Username field check returned non-None but falsey? Assuming not on reg page for '{username}'. Proceeding to final check.")
                            # Fall through to the TimeoutException block which handles the final check

                    except TimeoutException:
                        # Username field NOT found after waiting 3s. This means we are NOT on the registration page.
                        # Since the initial Inbox check also timed out, we are in an uncertain state.
                        _log(
                            f"[REG_UNCERTAIN] Not on registration page, but Inbox not found for '{username}'. Trying final Inbox check (5s)...")
                        try:
                            final_inbox_check = find_element_with_wait(
                                driver, By.XPATH, inbox_xpath, timeout=5, log_queue=log_queue, profile_id=profile_id)
                            if final_inbox_check:
                                _log(
                                    f"[REG_SUCCESS] Inbox button found on final check for '{username}'. Registration successful.")

                                # --- NEW: Check for Ad URL Fragment (also after final check success) ---
                                try:
                                    current_url = driver.current_url
                                    _log(
                                        f"Checking current URL for ad fragment (final check): {current_url}")
                                    if "#google_vignette" in current_url:
                                        _log(
                                            "Detected ad URL fragment (#google_vignette) after final registration check success. Refreshing...")
                                        driver.refresh()
                                        _log(
                                            "Waiting for Inbox button again after ad refresh (up to 30s)...")
                                        from selenium.webdriver.support.ui import WebDriverWait
                                        from selenium.webdriver.support import expected_conditions as EC
                                        try:
                                            WebDriverWait(driver, 30).until(
                                                EC.element_to_be_clickable(
                                                    (By.XPATH, inbox_xpath))
                                            )
                                            _log(
                                                "Inbox button found after ad refresh (final check).")
                                        except TimeoutException:
                                            _log(
                                                "[REG_ERROR] Inbox button did NOT reappear after ad refresh (final check).")
                                            continue  # Try next username
                                        except Exception as ad_refresh_wait_err:
                                            _log(
                                                f"[REG_ERROR] Error waiting for inbox after ad refresh (final check): {ad_refresh_wait_err}")
                                            continue  # Try next username
                                    else:
                                        _log(
                                            "No ad URL fragment detected after final registration check.")
                                except Exception as ad_check_err:
                                    _log(
                                        f"[REG_WARN] Error checking for ad URL fragment after final registration check: {ad_check_err}")
                                # --- END Ad Check ---

                                list_attempt_successful = True
                                return True
                            else:
                                # Final check returned falsey (shouldn't happen)
                                _log(
                                    f"[REG_FAIL] Final Inbox check failed (returned falsey) for '{username}'. Retrying next username.")
                                continue  # Try next username
                        except TimeoutException:
                            # Final check timed out
                            _log(
                                f"[REG_FAIL] Final Inbox check timed out for '{username}'. Retrying next username.")
                            continue  # Try next username
                        except Exception as e_final:
                            # Error during final check
                            _log(
                                f"[REG_ERROR] Error during final Inbox check for '{username}': {e_final}. Retrying next username.")
                            continue  # Try next username

                    except Exception as e_user_check:  # Catch errors during the username field check itself
                        _log(
                            f"[REG_ERROR] Error checking for username input field for '{username}': {e_user_check}. Retrying next username.")
                        continue  # Try next username

                except Exception as e_inbox_check:  # Catch errors during the initial inbox check
                    _log(
                        f"[REG_ERROR] Unexpected error during initial Inbox check for '{username}': {e_inbox_check}")
                    continue  # Try next username

            else:
                # attempt_registration itself returned False (e.g., couldn't click button)
                _log(
                    f"Attempt_registration function returned False for username '{username}'. Trying next in list.")
                time.sleep(1)  # Small pause before next attempt
                continue  # Try next username in the list
        # Only print if loop finished without success AND the list was not empty initially
        if usernames_list and not list_attempt_successful:
            _log(
                "[REG_DEBUG] All usernames from the provided list failed or encountered errors.")

    # --- Fallback: Försök med slumpmässiga namn ---
    # This part only runs if usernames_list was empty/None OR if all list attempts failed
    _log("[REG_DEBUG] Proceeding to random username generation fallback...")
    max_random_retries = 10
    for attempt in range(max_random_retries):
        username = generate_random_username()

        # Bestäm stad för detta försök (igen)
        if assigned_city:
            city = assigned_city
        elif city_options:
            # Välj slumpmässigt igen om ingen är tilldelad
            city = random.choice(city_options)
            _log(
                f"Warning: No city assigned, picking randomly for random user '{username}': {city}")
        else:
            _log("Error: No assigned city and no city options in config. Cannot register.")
            return False

        _log(
            f"\nRandom Username Attempt {attempt + 1}/{max_random_retries} using city: {city}...")
        # Updated call with keyword args for log_queue and profile_id
        # attempt_registration now only returns True if the click was successful
        if attempt_registration(driver, username, age, country_code, city, log_queue=log_queue, profile_id=profile_id):
            _log(
                f"Registration attempt submitted for random '{username}'. Verifying navigation...")
            # --- NEW Verification Logic ---
            inbox_xpath = "//li[@onclick='inbox()']"
            try:
                # Wait generously for the inbox button to appear
                _log(f"Waiting up to 20s for Inbox button ({inbox_xpath})...")
                inbox_button = find_element_with_wait(
                    driver, By.XPATH, inbox_xpath, timeout=20, log_queue=log_queue, profile_id=profile_id)
                if inbox_button:
                    _log(
                        f"[REG_SUCCESS] Inbox button found for random username '{username}'. Registration successful.")

                    # --- NEW: Check for Ad URL Fragment (Random Username Loop) ---
                    try:
                        current_url = driver.current_url
                        _log(
                            f"Checking current URL for ad fragment (random): {current_url}")
                        if "#google_vignette" in current_url:
                            _log(
                                "Detected ad URL fragment (#google_vignette) immediately after random registration success. Refreshing...")
                            driver.refresh()
                            _log(
                                "Waiting for Inbox button again after ad refresh (up to 30s)...")
                            from selenium.webdriver.support.ui import WebDriverWait
                            from selenium.webdriver.support import expected_conditions as EC
                            try:
                                WebDriverWait(driver, 30).until(
                                    EC.element_to_be_clickable(
                                        (By.XPATH, inbox_xpath))
                                )
                                _log("Inbox button found after ad refresh (random).")
                            except TimeoutException:
                                _log(
                                    "[REG_ERROR] Inbox button did NOT reappear after ad refresh (random).")
                                continue  # Try next random username
                            except Exception as ad_refresh_wait_err:
                                _log(
                                    f"[REG_ERROR] Error waiting for inbox after ad refresh (random): {ad_refresh_wait_err}")
                                continue  # Try next random username
                        else:
                            _log(
                                "No ad URL fragment detected after random registration.")
                    except Exception as ad_check_err:
                        _log(
                            f"[REG_WARN] Error checking for ad URL fragment after random registration: {ad_check_err}")
                    # --- END Ad Check ---

                    return True  # Exit handle_registration_process successfully
                else:
                    # This case should not happen if find_element_with_wait works correctly (throws TimeoutException)
                    _log(
                        f"[REG_WARN] Inbox button check returned non-None but falsey? Assuming not found for random '{username}'.")
                    # Proceed to check if back on registration page

            except TimeoutException:
                _log(
                    f"[REG_INFO] Inbox button not found within 20s for random '{username}'. Checking if back on registration page...")
                # Check if we are back on the registration page
                try:
                    username_field_check = find_element_with_wait(
                        driver, By.XPATH, XPATHS_REGISTRATION["username_input"], timeout=3, log_queue=log_queue, profile_id=profile_id)
                    if username_field_check:
                        # Simplified: If username field is found, assume failure and retry.
                        _log(
                            f"[REG_FAIL] Returned to registration page for random username '{username}'. Retrying next username.")
                        continue  # Try next random username
                    else:
                        # Username field check returned falsey (shouldn't happen with find_element_with_wait)
                        # Treat as uncertain state, proceed to final inbox check below.
                        _log(
                            f"[REG_WARN] Username field check returned non-None but falsey? Assuming not on reg page for random '{username}'. Proceeding to final check.")
                        # Fall through to the TimeoutException block which handles the final check

                except TimeoutException:
                    # Username field NOT found after waiting 3s. This means we are NOT on the registration page.
                    # Since the initial Inbox check also timed out, we are in an uncertain state.
                    _log(
                        f"[REG_UNCERTAIN] Not on registration page, but Inbox not found for random '{username}'. Trying final Inbox check (5s)...")
                    try:
                        final_inbox_check = find_element_with_wait(
                            driver, By.XPATH, inbox_xpath, timeout=5, log_queue=log_queue, profile_id=profile_id)
                        if final_inbox_check:
                            _log(
                                f"[REG_SUCCESS] Inbox button found on final check for random '{username}'. Registration successful.")

                            # --- NEW: Check for Ad URL Fragment (Random Username, Final Check) ---
                            try:
                                current_url = driver.current_url
                                _log(
                                    f"Checking current URL for ad fragment (random, final): {current_url}")
                                if "#google_vignette" in current_url:
                                    _log(
                                        "Detected ad URL fragment (#google_vignette) after final random registration check success. Refreshing...")
                                    driver.refresh()
                                    _log(
                                        "Waiting for Inbox button again after ad refresh (up to 30s)...")
                                    from selenium.webdriver.support.ui import WebDriverWait
                                    from selenium.webdriver.support import expected_conditions as EC
                                    try:
                                        WebDriverWait(driver, 30).until(
                                            EC.element_to_be_clickable(
                                                (By.XPATH, inbox_xpath))
                                        )
                                        _log(
                                            "Inbox button found after ad refresh (random, final).")
                                    except TimeoutException:
                                        _log(
                                            "[REG_ERROR] Inbox button did NOT reappear after ad refresh (random, final).")
                                        continue  # Try next random username
                                    except Exception as ad_refresh_wait_err:
                                        _log(
                                            f"[REG_ERROR] Error waiting for inbox after ad refresh (random, final): {ad_refresh_wait_err}")
                                        continue  # Try next random username
                                else:
                                    _log(
                                        "No ad URL fragment detected after final random registration check.")
                            except Exception as ad_check_err:
                                _log(
                                    f"[REG_WARN] Error checking for ad URL fragment after final random registration check: {ad_check_err}")
                            # --- END Ad Check ---

                            return True
                        else:
                            # Final check returned falsey (shouldn't happen)
                            _log(
                                f"[REG_FAIL] Final Inbox check failed (returned falsey) for random '{username}'. Retrying next username.")
                            continue  # Try next random username
                    except TimeoutException:
                        # Final check timed out
                        _log(
                            f"[REG_FAIL] Final Inbox check timed out for random '{username}'. Retrying next username.")
                        continue  # Try next random username
                    except Exception as e_final:
                        # Error during final check
                        _log(
                            f"[REG_ERROR] Error during final Inbox check for random '{username}': {e_final}. Retrying next username.")
                        continue  # Try next random username

                except Exception as e_user_check:  # Catch errors during the username field check itself
                    _log(
                        f"[REG_ERROR] Error checking for username input field for random '{username}': {e_user_check}. Retrying next username.")
                    continue  # Try next random username

            except Exception as e_inbox_check:  # Catch errors during the initial inbox check
                _log(
                    f"[REG_ERROR] Unexpected error during initial Inbox check for random '{username}': {e_inbox_check}")
                continue  # Try next random username

        else:
            # attempt_registration itself returned False (e.g., couldn't click button)
            _log(
                "Attempt_registration function returned False during random username attempt.")
            time.sleep(3)  # Wait a bit longer if the click itself failed
            continue  # Try next random username

    _log("Maximum registration retries reached (including list and random). Failed to register.")
    return False


if __name__ == '__main__':
    # Example Usage (Requires a running AdsPower browser instance started via selenium_handler)
    print("Running Registration Example...")
    # This example requires manual setup:
    # 1. Ensure AdsPower is running.
    # 2. Update config.json with a valid profile ID.
    # 3. Manually start the browser using selenium_handler.py or similar.
    # 4. Pass the driver instance to handle_registration_process.

    # --- Dummy Example ---
    class MockDriver:
        def find_element(self, by, value):
            print(f"Mock Find: {by}='{value}'")
            if value == XPATHS_REGISTRATION["username_error_text"]:
                # Simulate error on first try
                if not hasattr(self, 'attempt_count'):
                    self.attempt_count = 0
                self.attempt_count += 1
                if self.attempt_count <= 1:
                    print("Mock: Simulating username error.")
                    return True  # Simulate finding error element
                else:
                    print("Mock: Simulating NO username error.")
                    raise TimeoutException  # Simulate error not found
            return MockElement()

        def get(self, url): print(f"Mock Navigate: {url}")
        def quit(self): print("Mock Quit")

    class MockElement:
        def send_keys(self, text): print(f"Mock SendKeys: '{text}'")
        def click(self): print("Mock Click")
        def select_by_value(self, value): print(
            f"Mock SelectByValue: '{value}'")  # Needs Select wrapper

    print("\n--- Running Mock Registration ---")
    # Need to mock Select properly if testing select_option_by_value directly
    # For handle_registration_process, mocking find_element is often enough
    mock_driver = MockDriver()
    # We need to mock the helper functions too if not importing properly
    find_element_with_wait = mock_driver.find_element  # Simple mock
    def click_element(el): return print("Mock Click Helper") or True

    def send_keys_to_element(el, txt): return print(
        f"Mock SendKeys Helper: '{txt}'") or True

    def select_option_by_value(drv, sel, val): return print(
        f"Mock Select Helper: {sel}='{val}'") or True

    success = handle_registration_process(mock_driver)
    print(f"Mock Registration Successful: {success}")
    print("--- Mock Registration Finished ---")

    # To run for real:
    # from app.bot_core.selenium_handler import start_adspower_browser, close_adspower_browser
    # config = load_config()
    # profile_id = "YOUR_REAL_PROFILE_ID" # Get from config or elsewhere
    # driver = start_adspower_browser(profile_id)
    # if driver:
    #     try:
    #         driver.get("https://chatib.us/auth/login") # Or the registration page URL
    #         time.sleep(3)
    #         registration_successful = handle_registration_process(driver)
    #         print(f"Actual Registration Result: {registration_successful}")
    #         time.sleep(5) # Keep browser open for a bit
    #     finally:
    #         close_adspower_browser(profile_id)
    # else:
    #     print("Failed to start browser for actual test.")
