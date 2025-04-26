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
        # Pass log info
        if not send_keys_to_element(username_field, username, log_queue=log_queue, profile_id=profile_id):
            _log(
                f"[REG_ATTEMPT_DEBUG] send_keys_to_element FAILED for username: '{username}'")
            _log("Failed to enter username.")
            return False
        else:
            _log(
                f"[REG_ATTEMPT_DEBUG] send_keys_to_element SUCCEEDED for username: '{username}'")
    else:
        _log("[REG_ATTEMPT_DEBUG] Username input field NOT found.")
        _log("Failed to enter username.")
        return False  # Explicitly return False if field not found

    # Select Age
    # Updated call with log_queue and profile_id
    if not select_option_by_value(driver, XPATHS_REGISTRATION["age_select"], age, log_queue=log_queue, profile_id=profile_id):
        _log("Failed to select age.")
        return False

    # Select Country
    # Updated call with log_queue and profile_id
    if not select_option_by_value(driver, XPATHS_REGISTRATION["country_select"], country_code, log_queue=log_queue, profile_id=profile_id):
        _log("Failed to select country.")
        return False

    # Select City - Needs a small delay sometimes for city options to populate based on country
    time.sleep(1)
    # Updated call with log_queue and profile_id
    if not select_option_by_value(driver, XPATHS_REGISTRATION["city_select"], city, log_queue=log_queue, profile_id=profile_id):
        _log(
            f"Failed to select city '{city}'. It might not be available for country '{country_code}'.")
        # Decide how to handle this - maybe try another city? For now, fail.
        return False

    # Click form area to potentially enable button
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
        _log("Failed to click start chat button.")
        return False

    _log("Registration form submitted.")
    # Add a small delay to allow page transition or error messages to appear
    time.sleep(2)
    return True


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
            if attempt_registration(driver, username, age, country_code, city, log_queue=log_queue, profile_id=profile_id):
                # --- Check for immediate errors on the registration page ---
                try:
                    # Check for username error first
                    # Updated call with log_queue and profile_id
                    error_element = find_element_with_wait(
                        driver, By.XPATH, XPATHS_REGISTRATION["username_error_text"], timeout=2, log_queue=log_queue, profile_id=profile_id)
                    if error_element:
                        _log(
                            f"Username from list '{username}' failed (restricted/taken). Trying next.")
                        continue  # Try next username in the list

                    # If no username error, check for captcha error
                    try:
                        # Updated call with log_queue and profile_id
                        captcha_error = find_element_with_wait(
                            driver, By.XPATH, "//div[@class='alert alert-danger']", timeout=1, log_queue=log_queue, profile_id=profile_id)
                        if captcha_error and "captcha" in captcha_error.text.lower():
                            _log(
                                f"Registration for '{username}' failed due to 'Invalid Captcha' error. Retrying.")
                            continue  # Try next username in the list
                    except TimeoutException:
                        pass  # Captcha error not found quickly, assume okay for now
                    except Exception as cap_err:
                        _log(
                            f"Error checking for captcha error for '{username}': {cap_err}. Assuming okay.")

                    # If neither specific error was found quickly, assume submission was accepted
                    _log(
                        f"[REG_DEBUG] Registration submission accepted for username from list: {username}. (Final success depends on subsequent checks).")
                    list_attempt_successful = True
                    return True  # Return True indicating submission OK for this username

                except TimeoutException:
                    # Neither error element appeared quickly. Assume submission was accepted.
                    _log(
                        f"[REG_DEBUG] No immediate errors detected for '{username}'. Assuming submission accepted. (Final success depends on subsequent checks).")
                    list_attempt_successful = True
                    return True  # Return True indicating submission OK

                except Exception as e:
                    # Error during the error checking itself
                    _log(
                        f"Error checking for registration errors for '{username}': {e}. Trying next.")
                    continue  # Try next username

            else:
                # attempt_registration itself returned False (e.g., couldn't find form elements)
                _log(
                    f"Attempt_registration function returned False for username '{username}'. Trying next in list.")
                time.sleep(1)  # Liten paus innan nästa försök
                continue  # Försök nästa namn i listan
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
        if attempt_registration(driver, username, age, country_code, city, log_queue=log_queue, profile_id=profile_id):
            # --- Check for immediate errors on the registration page ---
            try:
                # Check for username error first
                # Updated call with log_queue and profile_id
                error_element = find_element_with_wait(
                    driver, By.XPATH, XPATHS_REGISTRATION["username_error_text"], timeout=2, log_queue=log_queue, profile_id=profile_id)
                if error_element:
                    _log(
                        f"Random username '{username}' failed (restricted/taken). Retrying.")
                    continue  # Try next random username

                # If no username error, check for captcha error
                try:
                    # Updated call with log_queue and profile_id
                    captcha_error = find_element_with_wait(
                        driver, By.XPATH, "//div[@class='alert alert-danger']", timeout=1, log_queue=log_queue, profile_id=profile_id)
                    if captcha_error and "captcha" in captcha_error.text.lower():
                        _log(
                            f"Registration for random '{username}' failed due to 'Invalid Captcha' error. Retrying.")
                        continue  # Try next random username
                except TimeoutException:
                    pass  # Captcha error not found quickly, assume okay for now
                except Exception as cap_err:
                    _log(
                        f"Error checking for captcha error for random '{username}': {cap_err}. Assuming okay.")

                # If neither specific error was found quickly, assume submission was accepted
                _log(
                    f"Registration submission accepted for random username: {username}. (Final success depends on subsequent checks).")
                return True  # Return True indicating submission OK

            except TimeoutException:
                # Neither error element appeared quickly. Assume submission was accepted.
                _log(
                    f"No immediate errors detected for random '{username}'. Assuming submission accepted. (Final success depends on subsequent checks).")
                return True  # Return True indicating submission OK

            except Exception as e:
                # Error during the error checking itself
                _log(
                    f"Error checking for registration errors for random '{username}': {e}. Retrying.")
                continue  # Try next random username

        else:
            # attempt_registration itself returned False
            _log(
                "Attempt_registration function returned False during random username attempt.")
            time.sleep(3)
            continue  # Försök nästa slumpmässiga

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
