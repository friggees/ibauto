import time
import random
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
    print("Error: Could not import selenium_handler or config manager. Ensure PYTHONPATH is set correctly or run from project root.")
    # Define dummy functions to allow script loading, but it won't work
    def find_element_with_wait(driver, by, value, timeout=10): return None
    def click_element(element): return False
    def send_keys_to_element(element, text): return False
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


def select_option_by_value(driver, select_xpath, value):
    """Selects an option from a dropdown by its value attribute."""
    select_element = find_element_with_wait(driver, By.XPATH, select_xpath)
    if not select_element:
        print(f"Error: Could not find select element: {select_xpath}")
        return False
    try:
        select = Select(select_element)
        select.select_by_value(value)
        print(f"Selected option with value '{value}' from {select_xpath}")
        return True
    except NoSuchElementException:
        print(
            f"Error: Option with value '{value}' not found in {select_xpath}")
        return False
    except Exception as e:
        print(f"Error selecting option '{value}' from {select_xpath}: {e}")
        return False


def attempt_registration(driver, username, age, country_code, city):
    """Fills the registration form and clicks start chat."""
    print(
        f"Attempting registration with Username: {username}, Age: {age}, Country: {country_code}, City: {city}")

    # Fill Username
    print("[REG_ATTEMPT_DEBUG] Finding username input field...")  # DEBUG LOG
    username_field = find_element_with_wait(
        driver, By.XPATH, XPATHS_REGISTRATION["username_input"])
    if username_field:
        # Clear the field before sending keys to prevent accumulation on retries
        print("[REG_ATTEMPT_DEBUG] Clearing username input field...")
        username_field.clear()
        # DEBUG LOG
        print(
            f"[REG_ATTEMPT_DEBUG] Found username field. Attempting to send keys: '{username}'")
        if not send_keys_to_element(username_field, username):
            # DEBUG LOG
            print(
                f"[REG_ATTEMPT_DEBUG] send_keys_to_element FAILED for username: '{username}'")
            print("Failed to enter username.")  # Existing message
            return False
        else:
            # DEBUG LOG
            print(
                f"[REG_ATTEMPT_DEBUG] send_keys_to_element SUCCEEDED for username: '{username}'")
    else:
        print("[REG_ATTEMPT_DEBUG] Username input field NOT found.")  # DEBUG LOG
        print("Failed to enter username.")  # Existing message
        return False  # Explicitly return False if field not found

    # Select Age
    if not select_option_by_value(driver, XPATHS_REGISTRATION["age_select"], age):
        print("Failed to select age.")
        return False

    # Select Country
    if not select_option_by_value(driver, XPATHS_REGISTRATION["country_select"], country_code):
        print("Failed to select country.")
        return False

    # Select City - Needs a small delay sometimes for city options to populate based on country
    time.sleep(1)
    if not select_option_by_value(driver, XPATHS_REGISTRATION["city_select"], city):
        print(
            f"Failed to select city '{city}'. It might not be available for country '{country_code}'.")
        # Decide how to handle this - maybe try another city? For now, fail.
        return False

    # Click form area to potentially enable button
    form_area = find_element_with_wait(
        driver, By.XPATH, XPATHS_REGISTRATION["form_area_to_click"], timeout=5)
    click_element(form_area)  # Best effort click
    time.sleep(0.5)

    # Click Start Chat Button (try primary, then backup)
    start_button = find_element_with_wait(
        driver, By.XPATH, XPATHS_REGISTRATION["start_chat_button_primary"], timeout=5)
    if not start_button:
        print("Primary start button not found, trying backup...")
        start_button = find_element_with_wait(
            driver, By.XPATH, XPATHS_REGISTRATION["start_chat_button_backup"], timeout=5)

    if start_button:
        # Scroll the button into view before clicking
        print("Scrolling start chat button into view...")
        driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", start_button)
        time.sleep(0.5)  # Give a moment for scrolling

    if not click_element(start_button):
        print("Failed to click start chat button.")
        return False

    print("Registration form submitted.")
    # Add a small delay to allow page transition or error messages to appear
    time.sleep(2)
    return True


def handle_registration_process(driver, assigned_city: Optional[str] = None, usernames_list: Optional[List[str]] = None):
    """
    Manages the full registration process, attempting usernames from a list first.

    Args:
        driver: The Selenium WebDriver instance.
        assigned_city: The specific city assigned to this bot instance.
        usernames_list: A list of preferred usernames to try first.

    Returns:
        True if registration seems successful (navigated away from registration page), False otherwise.
    """
    config = load_config()
    reg_defaults = config.get("registration_defaults", {})
    age = reg_defaults.get("age", "18")
    country_code = reg_defaults.get("country", "US")
    # Default to New York if not specified
    city_options = reg_defaults.get("city_options", [])

    # --- Försök med namn från listan först ---
    print(f"[REG_DEBUG] Received usernames_list: {usernames_list}")  # LOGGING
    if usernames_list:  # Check if list is not None and not empty
        print(
            f"[REG_DEBUG] Attempting registration with usernames from provided list ({len(usernames_list)} names)...")  # LOGGING
        list_attempt_successful = False  # Flag to track if any list username worked
        for i, username in enumerate(usernames_list):  # Add index for logging
            # LOGGING
            print(
                f"[REG_DEBUG] List attempt {i+1}/{len(usernames_list)}: Trying username '{username}'")
            # Bestäm stad för detta försök
            if assigned_city:
                city = assigned_city
            elif city_options:
                # Välj slumpmässigt FÖR VARJE FÖRSÖK om ingen är tilldelad? Eller håll fast vid en?
                # För enkelhetens skull, välj en slumpmässig här om ingen är tilldelad.
                city = random.choice(city_options)
                print(
                    f"Warning: No city assigned, picking randomly for user '{username}': {city}")
            else:
                print(
                    "Error: No assigned city and no city options in config. Cannot register.")
                return False

            print(
                f"\nTrying username from list: {username} with city: {city}...")
            if attempt_registration(driver, username, age, country_code, city):
                # --- Check for immediate errors on the registration page ---
                try:
                    # Check for username error first
                    error_element = find_element_with_wait(
                        driver, By.XPATH, XPATHS_REGISTRATION["username_error_text"], timeout=2)  # Short wait for immediate feedback
                    if error_element:
                        print(
                            f"Username from list '{username}' failed (restricted/taken). Trying next.")
                        continue  # Try next username in the list

                    # If no username error, check for captcha error
                    try:
                        captcha_error = find_element_with_wait(
                            driver, By.XPATH, "//div[@class='alert alert-danger']", timeout=1)  # Even shorter check
                        if captcha_error and "captcha" in captcha_error.text.lower():
                            print(
                                f"Registration for '{username}' failed due to 'Invalid Captcha' error. Retrying.")
                            continue  # Try next username in the list
                    except TimeoutException:
                        pass  # Captcha error not found quickly, assume okay for now
                    except Exception as cap_err:
                        print(
                            f"Error checking for captcha error for '{username}': {cap_err}. Assuming okay.")

                    # If neither specific error was found quickly, assume submission was accepted
                    print(
                        f"[REG_DEBUG] Registration submission accepted for username from list: {username}. (Final success depends on subsequent checks).")
                    list_attempt_successful = True
                    return True  # Return True indicating submission OK for this username

                except TimeoutException:
                    # Neither error element appeared quickly. Assume submission was accepted.
                    print(
                        f"[REG_DEBUG] No immediate errors detected for '{username}'. Assuming submission accepted. (Final success depends on subsequent checks).")
                    list_attempt_successful = True
                    return True  # Return True indicating submission OK

                except Exception as e:
                    # Error during the error checking itself
                    print(
                        f"Error checking for registration errors for '{username}': {e}. Trying next.")
                    continue  # Try next username

            else:
                # attempt_registration itself returned False (e.g., couldn't find form elements)
                print(
                    f"Attempt_registration function returned False for username '{username}'. Trying next in list.")
                time.sleep(1)  # Liten paus innan nästa försök
                continue  # Försök nästa namn i listan
        # Only print if loop finished without success AND the list was not empty initially
        if usernames_list and not list_attempt_successful:
            # LOGGING
            print(
                "[REG_DEBUG] All usernames from the provided list failed or encountered errors.")

    # --- Fallback: Försök med slumpmässiga namn ---
    # This part only runs if usernames_list was empty/None OR if all list attempts failed
    # LOGGING
    print("[REG_DEBUG] Proceeding to random username generation fallback...")
    max_random_retries = 10
    for attempt in range(max_random_retries):
        username = generate_random_username()

        # Bestäm stad för detta försök (igen)
        if assigned_city:
            city = assigned_city
        elif city_options:
            # Välj slumpmässigt igen om ingen är tilldelad
            city = random.choice(city_options)
            print(
                f"Warning: No city assigned, picking randomly for random user '{username}': {city}")
        else:
            print(
                "Error: No assigned city and no city options in config. Cannot register.")
            return False

        print(
            f"\nRandom Username Attempt {attempt + 1}/{max_random_retries} using city: {city}...")
        if attempt_registration(driver, username, age, country_code, city):
            # --- Check for immediate errors on the registration page ---
            try:
                # Check for username error first
                error_element = find_element_with_wait(
                    driver, By.XPATH, XPATHS_REGISTRATION["username_error_text"], timeout=2)  # Short wait for immediate feedback
                if error_element:
                    print(
                        f"Random username '{username}' failed (restricted/taken). Retrying.")
                    continue  # Try next random username

                # If no username error, check for captcha error
                try:
                    captcha_error = find_element_with_wait(
                        driver, By.XPATH, "//div[@class='alert alert-danger']", timeout=1)  # Even shorter check
                    if captcha_error and "captcha" in captcha_error.text.lower():
                        print(
                            f"Registration for random '{username}' failed due to 'Invalid Captcha' error. Retrying.")
                        continue  # Try next random username
                except TimeoutException:
                    pass  # Captcha error not found quickly, assume okay for now
                except Exception as cap_err:
                    print(
                        f"Error checking for captcha error for random '{username}': {cap_err}. Assuming okay.")

                # If neither specific error was found quickly, assume submission was accepted
                print(
                    f"Registration submission accepted for random username: {username}. (Final success depends on subsequent checks).")
                return True  # Return True indicating submission OK

            except TimeoutException:
                # Neither error element appeared quickly. Assume submission was accepted.
                print(
                    f"No immediate errors detected for random '{username}'. Assuming submission accepted. (Final success depends on subsequent checks).")
                return True  # Return True indicating submission OK

            except Exception as e:
                # Error during the error checking itself
                print(
                    f"Error checking for registration errors for random '{username}': {e}. Retrying.")
                continue  # Try next random username

        else:
            # attempt_registration itself returned False
            print(
                "Attempt_registration function returned False during random username attempt.")
            time.sleep(3)
            continue  # Försök nästa slumpmässiga

    print("Maximum registration retries reached (including list and random). Failed to register.")
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
