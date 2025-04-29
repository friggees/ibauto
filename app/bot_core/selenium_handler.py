import requests
import time
import json
import os
import multiprocessing  # Add multiprocessing import
from typing import Optional  # Add Optional import
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# Added StaleElementReferenceException
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

# Import config loading function
# Assuming the script is run from the project root or the 'app' directory structure is in PYTHONPATH
try:
    from app.config.manager import load_config
except ImportError:
    # Fallback for running script directly or potential path issues
    import sys
    # Add project root to path if necessary (adjust based on actual structure)
    PACKAGE_PARENT = '..'
    SCRIPT_DIR = os.path.dirname(os.path.realpath(
        os.path.join(os.getcwd(), os.path.expanduser(__file__))))
    sys.path.append(os.path.normpath(os.path.join(
        SCRIPT_DIR, PACKAGE_PARENT, PACKAGE_PARENT)))
    from app.config.manager import load_config


def start_adspower_browser(profile_id: str, log_queue: Optional[multiprocessing.Queue] = None):
    """
    Starts an AdsPower browser profile via the local API and returns a Selenium WebDriver instance.
    Optionally logs actions via log_queue.

    Args:
        profile_id: The AdsPower profile ID to open.
        log_queue: Optional queue for logging.

    Returns:
        A Selenium WebDriver instance connected to the browser, or None if failed.
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
            # Fallback print
            print(f"[SELENIUM_HANDLER - NO LOG QUEUE] {message}")

    config = load_config()
    api_host = config.get("adspower_api_host",
                          "http://local.adspower.net:50325")

    # open_tabs=0 prevents opening default tabs
    start_url_base = f"{api_host}/api/v1/browser/start?user_id={profile_id}&open_tabs=0"

    # Check config for headless mode
    run_headless = config.get("run_headless", False)
    start_url = start_url_base
    if run_headless:
        start_url += "&headless=1"
        _log(f"Headless mode requested for profile {profile_id}.")
    else:
        _log(f"Headless mode NOT requested for profile {profile_id}.")

    _log(
        f"Attempting to start AdsPower profile: {profile_id} via API: {start_url}")

    try:
        # Increased timeout for potentially slow starts
        response = requests.get(start_url, timeout=60)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()

        if data.get("code") != 0 or "data" not in data:
            _log(
                f"Error starting AdsPower profile {profile_id}: {data.get('msg', 'Unknown error')}")
            return None

        selenium_port = data["data"].get("ws", {}).get("selenium")
        webdriver_path = data["data"].get("webdriver")

        if not selenium_port or not webdriver_path:
            _log(
                f"Error: Could not retrieve Selenium port or WebDriver path from AdsPower API response for profile {profile_id}.")
            _log(f"API Response Data: {data.get('data')}")
            # Attempt to close the potentially opened browser if port/path missing
            # Pass log_queue
            close_adspower_browser(profile_id, log_queue)
            return None

        _log(
            f"Successfully started profile {profile_id}. WebDriver path: {webdriver_path}, Debugger Address: {selenium_port}")

        chrome_options = Options()
        # Set page load strategy to 'eager'
        chrome_options.page_load_strategy = 'eager'
        _log("Set page load strategy to eager.")
        # Pass the selenium_port directly, assuming it contains host:port from the API
        chrome_options.add_experimental_option(
            "debuggerAddress", selenium_port)

        # Check if webdriver_path exists
        if not os.path.exists(webdriver_path):
            _log(
                f"Error: WebDriver executable not found at path: {webdriver_path}")
            # Attempt to close browser
            # Pass log_queue
            close_adspower_browser(profile_id, log_queue)
            return None

        service = Service(executable_path=webdriver_path)

        try:
            driver = webdriver.Chrome(service=service, options=chrome_options)
            _log(f"WebDriver successfully connected to profile {profile_id}")
            # Maximize window regardless of headless mode
            try:
                _log(
                    f"Attempting to maximize browser window for profile {profile_id}...")
                driver.maximize_window()
                _log(f"Browser window maximized for profile {profile_id}.")
            except Exception as max_err:
                _log(
                    f"Warning: Could not maximize window for profile {profile_id}: {max_err}")
            return driver
        except Exception as e:
            _log(
                f"Error connecting WebDriver to browser for profile {profile_id}: {e}")
            # Attempt to close browser if connection fails
            # Pass log_queue
            close_adspower_browser(profile_id, log_queue)
            return None

    except requests.exceptions.RequestException as e:
        _log(
            f"Error making API request to AdsPower for profile {profile_id}: {e}")
        return None
    except json.JSONDecodeError:
        _log(
            f"Error decoding JSON response from AdsPower API for profile {profile_id}.")
        return None
    except Exception as e:
        _log(
            f"An unexpected error occurred during AdsPower browser start for profile {profile_id}: {e}")
        return None


def close_adspower_browser(profile_id: str, log_queue: Optional[multiprocessing.Queue] = None):
    """
    Closes an AdsPower browser profile via the local API. Optionally logs actions.
    Args:
        profile_id: The AdsPower profile ID to close.
        log_queue: Optional queue for logging.

    Returns:
        True if the API call was successful (or profile already closed), False otherwise.
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
            # Fallback print
            print(f"[SELENIUM_HANDLER - NO LOG QUEUE] {message}")

    config = load_config()
    api_host = config.get("adspower_api_host",
                          "http://local.adspower.net:50325")
    stop_url = f"{api_host}/api/v1/browser/stop?user_id={profile_id}"

    _log(
        f"Attempting to close AdsPower profile: {profile_id} via API: {stop_url}")
    try:
        response = requests.get(stop_url, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("code") == 0:
            _log(f"Successfully closed AdsPower profile {profile_id}.")
            return True
        else:
            # Handle cases where it might already be closed or other errors
            msg = data.get('msg', 'Unknown error')
            _log(f"API call to close profile {profile_id} reported: {msg}")
            # Consider it potentially successful if message indicates it wasn't running
            if "process not found" in msg.lower() or "not running" in msg.lower():
                _log(f"Profile {profile_id} was likely already closed.")
                return True
            return False
    except requests.exceptions.RequestException as e:
        _log(
            f"Error making API request to close AdsPower profile {profile_id}: {e}")
        return False
    except Exception as e:
        _log(
            f"An unexpected error occurred during AdsPower browser close for profile {profile_id}: {e}")
        return False


# --- Selenium Helper Functions ---

def find_element_with_wait(driver, by: By, value: str, timeout: int = 10, log_queue: Optional[multiprocessing.Queue] = None, profile_id: Optional[str] = None):
    """Finds an element with an explicit wait. Optionally logs actions."""
    # Define _log locally for this function
    def _log(message: str):
        if log_queue and profile_id:
            try:
                log_queue.put({'bot_id': profile_id, 'message': message})
            except Exception as log_err:
                print(
                    f"[Bot Process {os.getpid()} - LOG QUEUE ERROR for {profile_id}] {log_err}\nFALLBACK LOG: {message}")
        else:
            # Fallback print
            print(f"[SELENIUM_HANDLER - NO LOG QUEUE] {message}")
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return element
    except TimeoutException:
        _log(f"Timeout waiting for element: {by}='{value}'")
        return None
    except Exception as e:
        _log(f"Error finding element {by}='{value}': {e}")
        return None


def click_element(element, log_queue: Optional[multiprocessing.Queue] = None, profile_id: Optional[str] = None):
    """Clicks a Selenium element, handling potential exceptions. Optionally logs actions."""
    # Define _log locally for this function
    def _log(message: str):
        if log_queue and profile_id:
            try:
                log_queue.put({'bot_id': profile_id, 'message': message})
            except Exception as log_err:
                print(
                    f"[Bot Process {os.getpid()} - LOG QUEUE ERROR for {profile_id}] {log_err}\nFALLBACK LOG: {message}")
        else:
            # Fallback print
            print(f"[SELENIUM_HANDLER - NO LOG QUEUE] {message}")

    if not element:
        _log("Cannot click None element.")
        return False
    try:
        # Add a small wait for the element to be clickable before clicking
        # This requires the driver instance, which we don't have here directly.
        # Consider passing driver or adding wait logic if needed.
        # For now, rely on the element being ready.
        element.click()
        # _log(f"Clicked element: {element.tag_name} (details might be limited)") # Optional detailed log
        return True
    except StaleElementReferenceException:
        _log("Error clicking element: StaleElementReferenceException")
        return False
    except Exception as e:
        _log(f"Error clicking element: {e}")
        return False


# Add 'driver' parameter
def send_keys_to_element(driver, element, text: str, log_queue: Optional[multiprocessing.Queue] = None, profile_id: Optional[str] = None):
    """
    Sends keys to a Selenium element, handling potential exceptions.
    Tries standard send_keys first, then falls back to JavaScript if needed.
    Optionally logs actions.
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
            # Fallback print
            print(f"[SELENIUM_HANDLER - NO LOG QUEUE] {message}")

    if not element:
        _log("Cannot send keys to None element.")
        return False

    # Attempt 1: Standard send_keys
    try:
        element.send_keys(text)
        _log(f"Successfully sent keys '{text[:20]}...' using standard method.")
        return True
    except StaleElementReferenceException:
        _log(
            f"Standard send_keys failed for '{text[:20]}...': StaleElementReferenceException. Trying JS fallback.")
    except Exception as e:
        _log(
            f"Standard send_keys failed for '{text[:20]}...': {e}. Trying JS fallback.")

    # Attempt 2: JavaScript fallback
    _log(f"Attempting JavaScript fallback to set value for '{text[:20]}...'")
    try:
        # Ensure driver is available
        if not driver:
            _log("JavaScript fallback failed: Driver instance not provided.")
            return False
        driver.execute_script(
            "arguments[0].value = arguments[1];", element, text)
        # Trigger input event if needed (sometimes required for frameworks like React/Vue)
        # driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
        _log(f"Successfully set value '{text[:20]}...' using JavaScript.")
        return True
    except Exception as js_e:
        _log(f"JavaScript fallback also failed for '{text[:20]}...': {js_e}")
        return False


if __name__ == '__main__':
    # Example Usage (Requires AdsPower running and a valid profile ID in config)
    print("Running Selenium Handler Example...")
    config = load_config()
    # Use a dummy profile ID for testing structure, replace with a real one for actual test
    # Replace with a valid ID from your AdsPower
    test_profile_id = "YOUR_TEST_PROFILE_ID"

    if test_profile_id == "YOUR_TEST_PROFILE_ID":
        print("\nPlease replace 'YOUR_TEST_PROFILE_ID' in selenium_handler.py with a real AdsPower profile ID to run the example.")
    else:
        driver = start_adspower_browser(test_profile_id)

        if driver:
            print("\nBrowser started. Attempting to navigate and find title...")
            try:
                driver.get("https://example.com")
                time.sleep(2)  # Simple wait
                print(f"Page Title: {driver.title}")

                # Example using helper
                # body_element = find_element_with_wait(driver, By.TAG_NAME, "body")
                # if body_element:
                #     print("Body element found.")

            except Exception as e:
                print(f"Error during browser interaction: {e}")
            finally:
                print("\nClosing browser...")
                # driver.quit() # Important: Don't use driver.quit() with AdsPower debugger connection
                closed = close_adspower_browser(test_profile_id)
                print(f"Browser close attempt via API successful: {closed}")
        else:
            print("\nFailed to start browser.")

    print("\nSelenium Handler Example Finished.")
