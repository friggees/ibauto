import sys  # Add sys import
import multiprocessing
import time
import signal
import os
from typing import List, Dict, Optional  # Re-added Optional for type hint

# Assuming bot_core logic can be run via a target function
try:
    from app.config.manager import load_config
    # We need a function to run within the process, let's assume it's in bot_core
    # It should handle starting the browser and running the chat cycle.
    # We'll define a placeholder `run_bot_instance` function signature here.
    # The actual implementation will likely involve calling selenium_handler.start_adspower_browser
    # and then chat_logic.handle_chat_cycle within the target function.
    # from app.bot_core.main_runner import run_bot_instance # Ideal structure
except ImportError:
    print("Error: Could not import config manager or bot_core runner. Ensure PYTHONPATH.")
    def load_config(): return {"max_concurrent_browsers": 1}
    # Define dummy runner

    def run_bot_instance(profile_id: str, stats_queue: multiprocessing.Queue):
        print(
            f"[Dummy Runner {os.getpid()}] Starting for profile {profile_id}")
        time.sleep(5)
        # Simulate sending a link
        stats_queue.put({"type": "link_sent", "profile_id": profile_id})
        print(
            f"[Dummy Runner {os.getpid()}] Sent link for profile {profile_id}")
        time.sleep(10)
        print(
            f"[Dummy Runner {os.getpid()}] Finishing for profile {profile_id}")


class ConcurrencyManager:
    """Manages multiple bot instances running in separate processes."""

    def __init__(self):
        self.config = load_config()
        self.max_workers = self.config.get("max_concurrent_browsers", 1)
        # Queue for processes to report stats (e.g., link sent)
        self.stats_queue = multiprocessing.Queue()
        self.processes: List[multiprocessing.Process] = []
        self.active_profile_ids: List[str] = []
        self.total_links_sent = 0
        self.is_running = False
        print(
            f"Concurrency Manager initialized. Max workers: {self.max_workers}")

    def start_bots(self, profile_ids: List[str]):
        """Starts bot processes for the given profile IDs, up to max_workers."""
        # Reload config to get the latest settings (including usernames)
        self.config = load_config()
        # Also update max_workers in case it changed
        self.max_workers = self.config.get("max_concurrent_browsers", 1)

        if self.is_running:
            print("Bots are already running.")
            return False

        if not profile_ids:
            print("No profile IDs provided to start.")
            return False

        # Limit to max_workers
        self.active_profile_ids = profile_ids[:self.max_workers]
        print(
            f"Attempting to start bots for profiles: {self.active_profile_ids}")

        # Load city options from config
        city_options = self.config.get(
            "registration_defaults", {}).get("city_options", [])
        # Load usernames list from config
        usernames_list = self.config.get("usernames", [])

        if not city_options:
            print(
                "Warning: No registration city options found in config. Registration might fail if needed.")
        if not usernames_list:
            print(
                "Warning: No usernames found in config. Registration will use random names if needed.")

        self.total_links_sent = 0  # Reset stats on start
        self.processes = []
        self.is_running = True

        for i, profile_id in enumerate(self.active_profile_ids):
            # Assign a city using modulo to cycle through the list
            assigned_city = city_options[i % len(
                city_options)] if city_options else None
            print(f"Assigning city '{assigned_city}' to profile {profile_id}")

            try:
                # Pass profile ID, stats queue, assigned city, AND usernames list to the target function
                process = multiprocessing.Process(
                    target=run_bot_instance,
                    args=(profile_id, self.stats_queue,
                          assigned_city, usernames_list),  # Added usernames_list
                    daemon=True
                )
                self.processes.append(process)
                process.start()
                print(
                    f"Started process PID {process.pid} for profile {profile_id}")
                time.sleep(1)  # Stagger starts slightly
            except Exception as e:
                print(f"Error starting process for profile {profile_id}: {e}")
                # Should we stop others if one fails? For now, continue.

        print(f"All requested bot processes ({len(self.processes)}) started.")
        # Start a separate thread/process to monitor the queue? Or handle in get_stats?
        return True

    def stop_bots(self):
        """Stops all running bot processes."""
        if not self.is_running:
            print("Bots are not currently running.")
            return False

        print(f"Attempting to stop {len(self.processes)} bot processes...")
        self.is_running = False
        self.active_profile_ids = []

        for process in self.processes:
            if process.is_alive():
                try:
                    print(f"Terminating process PID {process.pid}...")
                    # Send SIGTERM first for graceful shutdown (if handled)
                    # process.terminate() # More forceful
                    os.kill(process.pid, signal.SIGTERM)  # Try SIGTERM
                    process.join(timeout=5)  # Wait for graceful exit

                    if process.is_alive():
                        print(
                            f"Process PID {process.pid} did not terminate gracefully, sending SIGKILL.")
                        os.kill(process.pid, signal.SIGKILL)  # Force kill
                        process.join(timeout=2)  # Wait briefly for kill

                except ProcessLookupError:
                    print(f"Process PID {process.pid} already terminated.")
                except Exception as e:
                    print(f"Error stopping process PID {process.pid}: {e}")

        self.processes = []
        print("All bot processes stopped.")
        # Note: Stats queue might still contain items, process them one last time?
        self._process_stats_queue()  # Process any remaining items
        return True

    def _process_stats_queue(self):
        """Processes items from the stats queue."""
        while not self.stats_queue.empty():
            try:
                stat = self.stats_queue.get_nowait()
                if isinstance(stat, dict) and stat.get("type") == "link_sent":
                    self.total_links_sent += 1
                    print(
                        f"Concurrency Manager: Received link_sent event. Total links: {self.total_links_sent}")
                # Add handling for other stat types if needed
            except multiprocessing.queues.Empty:
                break
            except Exception as e:
                print(f"Error processing item from stats queue: {e}")

    def get_stats(self) -> Dict:
        """Processes the queue and returns current statistics."""
        self._process_stats_queue()
        return {
            "is_running": self.is_running,
            "active_processes": len([p for p in self.processes if p.is_alive()]),
            "target_processes": len(self.active_profile_ids),
            "active_profile_ids": self.active_profile_ids,
            "total_links_sent": self.total_links_sent
        }


# --- Placeholder for the actual bot runner function ---
# This should ideally be in a separate file, e.g., app/bot_core/main_runner.py
# It needs to orchestrate starting the browser and running the chat loop.


def run_bot_instance(profile_id: str, stats_queue: multiprocessing.Queue, assigned_city: Optional[str], usernames_list: List[str]):
    """
    The target function for each bot process.
    Handles setup, running the main chat loop, and cleanup for one profile.

    Adds the project root to sys.path to ensure imports work correctly in the subprocess.

    Args:
        profile_id: The AdsPower profile ID for this instance.
        stats_queue: The queue to send statistics (like link sent) back to the manager.
        assigned_city: The specific city assigned for registration purposes for this instance.
        usernames_list: A list of usernames to attempt during registration.
    """
    # --- Add project root to sys.path ---
    # Calculate the path to the project root (two levels up from this file's directory)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        print(f"[Bot Process {os.getpid()}] Added {project_root} to sys.path")
    # --- End path modification ---

    print(f"[Bot Process {os.getpid()}] Starting for profile: {profile_id}")
    driver = None
    try:
        # 1. Import necessary functions within the process context (NOW should work)
        # Selenium imports needed for consent/registration checks
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException

        from app.bot_core.selenium_handler import start_adspower_browser, close_adspower_browser, find_element_with_wait, click_element  # Import helpers
        from app.bot_core.chat_logic import handle_chat_cycle
        # Import registration logic too, as chat_logic might call it
        # This import needs to happen *inside* the process function
        from app.bot_core.registration import handle_registration_process

        # 2. Start the browser
        driver = start_adspower_browser(profile_id)
        if not driver:
            print(
                f"[Bot Process {os.getpid()}] Failed to start browser for profile {profile_id}. Exiting.")
            return  # Exit process if browser fails

        # 3. Navigate to initial page (e.g., login/registration or main chat page)
        #    This might depend on whether registration is needed first.
        #    For now, assume chat_logic handles navigation or registration check.
        print(
            f"[Bot Process {os.getpid()}] Browser started for profile {profile_id}.")

        # --- Navigate to Chatib and close other tabs ---
        try:
            initial_handle = driver.current_window_handle
            print(
                f"[Bot Process {os.getpid()}] Initial handle: {initial_handle}. Navigating to chatib.us...")
            driver.get("https://chatib.us/")
            time.sleep(3)  # Allow page to load

            # Could be same or different if redirect happened
            chatib_handle = driver.current_window_handle
            print(
                f"[Bot Process {os.getpid()}] Current handle after navigation: {chatib_handle}")

            all_handles = driver.window_handles
            if len(all_handles) > 1:
                print(
                    f"[Bot Process {os.getpid()}] Found {len(all_handles)} tabs. Closing extras...")
                for handle in all_handles:
                    if handle != chatib_handle:
                        try:
                            driver.switch_to.window(handle)
                            driver.close()
                            print(
                                f"[Bot Process {os.getpid()}] Closed extra tab: {handle}")
                        except Exception as close_err:
                            print(
                                f"[Bot Process {os.getpid()}] Error closing tab {handle}: {close_err}")
                # Switch back to the main Chatib tab
                driver.switch_to.window(chatib_handle)
                print(
                    f"[Bot Process {os.getpid()}] Switched back to Chatib tab: {chatib_handle}")
            else:
                print(f"[Bot Process {os.getpid()}] Only one tab open.")

        except Exception as nav_err:
            print(
                f"[Bot Process {os.getpid()}] Error during navigation/tab closing for {profile_id}: {nav_err}")
            # Decide if we should exit the process if navigation fails
            raise  # Re-raise to be caught by the main exception handler
        # --- End navigation/tab closing ---

        # --- Check for Ad Overlay Immediately After Load ---
        try:
            if "#google_vignette" in driver.current_url:
                print(
                    f"[Bot Process {os.getpid()}] Detected ad URL fragment immediately after load. Refreshing...")
                driver.refresh()
                # Wait for the body element to be present after refresh, indicating basic page structure loaded
                print(
                    f"[Bot Process {os.getpid()}] Waiting for page body after ad refresh...")
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                print(
                    f"[Bot Process {os.getpid()}] Page body found after ad refresh.")
                time.sleep(2)  # Extra short pause
        except Exception as initial_ad_err:
            print(
                f"[Bot Process {os.getpid()}] Error during initial ad check/refresh: {initial_ad_err}")
            # Continue anyway, maybe the ad wasn't the issue or refresh failed
        # --- End Initial Ad Check ---

        # --- Sequential Startup Check: Consent -> Registration -> Logged In ---
        proceed_to_chat = False
        try:
            # Step 1: Attempt to Accept Consent Popup (Non-blocking)
            print(
                f"[Bot Process {os.getpid()}] Step 1: Checking for consent popup...")
            time.sleep(1)  # Short wait for elements

            def _try_accept_consent(drv):
                # (Using the same potential_xpaths list and logic as before)
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
                        consent_button = WebDriverWait(drv, 2).until(
                            EC.element_to_be_clickable((By.XPATH, xpath)))
                        if consent_button:
                            print(
                                f"[Bot Process {os.getpid()}] Found potential consent button with XPath: {xpath}. Clicking...")
                            try:
                                drv.execute_script(
                                    "arguments[0].click();", consent_button)
                                print(
                                    f"[Bot Process {os.getpid()}] Clicked consent button via JavaScript.")
                                return True
                            except Exception as js_click_err:
                                print(
                                    f"[Bot Process {os.getpid()}] JS click failed ({js_click_err}), trying Selenium click...")
                                if click_element(consent_button):
                                    print(
                                        f"[Bot Process {os.getpid()}] Clicked consent button via Selenium click.")
                                    return True
                                else:
                                    print(
                                        f"[Bot Process {os.getpid()}] Selenium click also failed for XPath: {xpath}")
                                    continue
                    except TimeoutException:
                        continue
                    except Exception as e:
                        print(
                            f"[Bot Process {os.getpid()}] Error trying consent XPath {xpath}: {e}")
                        continue
                return False

            consent_clicked = _try_accept_consent(driver)
            if consent_clicked:
                print(f"[Bot Process {os.getpid()}] Consent handled.")
                time.sleep(1)  # Wait after click
            else:
                print(
                    f"[Bot Process {os.getpid()}] Consent popup not found or not clicked.")

            # Step 2: Check for Registration Page
            print(
                f"[Bot Process {os.getpid()}] Step 2: Checking for registration page...")
            registration_needed = False
            try:
                # Use XPath from Pre-work-info/xpaths_registration.md
                username_field_xpath = "//input[@id='username']"
                username_field = find_element_with_wait(
                    driver, By.XPATH, username_field_xpath, timeout=3)
                if username_field:
                    print(
                        f"[Bot Process {os.getpid()}] Registration page detected.")
                    registration_needed = True
                else:
                    print(
                        f"[Bot Process {os.getpid()}] Registration page not detected.")
            except TimeoutException:
                print(
                    f"[Bot Process {os.getpid()}] Registration page not detected (timeout).")
            except Exception as reg_check_err:
                print(
                    f"[Bot Process {os.getpid()}] Error checking for registration page: {reg_check_err}")
                # Decide if we should exit or continue to check logged-in state

            # Step 3: Perform Registration if Needed
            if registration_needed:
                print(
                    f"[Bot Process {os.getpid()}] Step 3: Attempting registration...")
                registration_result = handle_registration_process(
                    driver, assigned_city, usernames_list)
                if registration_result:
                    print(
                        f"[Bot Process {os.getpid()}] Registration successful.")
                    proceed_to_chat = True  # Registration successful, can proceed
                else:
                    print(
                        f"[Bot Process {os.getpid()}] Registration failed. Exiting process.")
                    return  # Exit if registration fails

            # Step 4: Check for Logged-In State (if registration wasn't needed/performed)
            if not proceed_to_chat and not registration_needed:
                print(
                    f"[Bot Process {os.getpid()}] Step 4: Checking for logged-in state...")
                logged_in = False
                try:
                    # Use interaction XPaths for inbox button or user list
                    inbox_button_xpath = "//li[@onclick='inbox()']"
                    fallback_user_list_xpath = "//div[@class='pills_items pills_items_users']"
                    chat_page_indicator = None
                    try:
                        chat_page_indicator = find_element_with_wait(
                            driver, By.XPATH, inbox_button_xpath, timeout=5)
                        print(
                            f"[Bot Process {os.getpid()}] Logged-in state confirmed (Inbox button found).")
                        logged_in = True
                    except TimeoutException:
                        print(
                            f"[Bot Process {os.getpid()}] Inbox button not found, checking fallback user list...")
                        try:
                            chat_page_indicator = find_element_with_wait(
                                driver, By.XPATH, fallback_user_list_xpath, timeout=3)
                            print(
                                f"[Bot Process {os.getpid()}] Logged-in state confirmed (Fallback user list found).")
                            logged_in = True
                        except TimeoutException:
                            print(
                                f"[Bot Process {os.getpid()}] Fallback user list also not found.")

                    if logged_in:
                        proceed_to_chat = True  # Already logged in, can proceed
                    else:
                        print(
                            f"[Bot Process {os.getpid()}] Neither registration page nor logged-in indicator found. Unknown state.")
                        # Optional: Add refresh and retry logic here?
                        # For now, exit if state is unknown after checks
                        print(
                            f"[Bot Process {os.getpid()}] Exiting due to unknown page state.")
                        return

                except Exception as login_check_err:
                    print(
                        f"[Bot Process {os.getpid()}] Error checking for logged-in state: {login_check_err}")
                    print(
                        f"[Bot Process {os.getpid()}] Exiting due to error during logged-in check.")
                    return

            # Step 5: Accept Chatib Terms if Present (Only if proceeding to chat)
            if proceed_to_chat:
                print(
                    f"[Bot Process {os.getpid()}] Step 5: Checking for Chatib terms popup...")
                try:
                    terms_button_xpath = "//button[@class='btn btn-primary confirm_decline agree']"
                    terms_button = find_element_with_wait(
                        driver, By.XPATH, terms_button_xpath, timeout=5)  # Shorter wait
                    if terms_button:
                        print(
                            f"[Bot Process {os.getpid()}] Found Chatib terms button. Clicking...")
                        if click_element(terms_button):
                            print(
                                f"[Bot Process {os.getpid()}] Clicked Chatib terms button.")
                            time.sleep(1)
                        else:
                            print(
                                f"[Bot Process {os.getpid()}] Failed to click Chatib terms button.")
                    else:
                        print(
                            f"[Bot Process {os.getpid()}] Chatib terms button not found (or timed out).")
                except TimeoutException:
                    print(
                        f"[Bot Process {os.getpid()}] Chatib terms button not found (timeout).")
                except Exception as terms_err:
                    print(
                        f"[Bot Process {os.getpid()}] Error checking/clicking Chatib terms: {terms_err}")
            # --- End Sequential Startup Check ---

        except Exception as startup_err:
            print(
                f"[Bot Process {os.getpid()}] Critical error during startup sequence: {startup_err}. Exiting.")
            return  # Exit on major startup error

        # 4. Run the main chat cycle (only if startup sequence was successful)
        if proceed_to_chat:
            print(
                f"[Bot Process {os.getpid()}] Startup successful. Proceeding to chat cycle for profile {profile_id}.")
            # handle_chat_cycle should run indefinitely until an error occurs
            # or the process is terminated. It should also put stats in the queue.
            # We need to modify handle_chat_cycle to accept the queue and use it. (Already done)
        #    We also need to modify handle_registration_process to accept the assigned city.
        #    The call to handle_registration_process happens *inside* handle_chat_cycle now.
        #    So, we need to pass assigned_city and usernames_list to handle_chat_cycle as well.
        handle_chat_cycle(driver, profile_id, stats_queue,
                          assigned_city, usernames_list)  # Pass assigned_city and usernames_list

    except Exception as e:
        print(
            f"[Bot Process {os.getpid()}] Unhandled exception in run_bot_instance for profile {profile_id}: {e}")
    finally:
        print(
            f"[Bot Process {os.getpid()}] Cleaning up for profile {profile_id}...")
        if driver:
            # Attempt to close the browser via API
            from app.bot_core.selenium_handler import close_adspower_browser
            close_adspower_browser(profile_id)
        print(
            f"[Bot Process {os.getpid()}] Finished for profile {profile_id}.")


if __name__ == '__main__':
    print("Running Concurrency Manager Example...")
    manager = ConcurrencyManager()

    # Example profile IDs (replace with actual IDs from config or user input later)
    test_profile_ids = ["profile1", "profile2", "profile3"]
    # Make sure max_workers in config allows this many, or it will be capped.

    print("\n--- Starting Bots ---")
    # In a real scenario, get profile IDs from config or dashboard input
    # config_profiles = manager.config.get("adspower_profile_ids", []) # Example config key
    manager.start_bots(test_profile_ids)

    print("\n--- Monitoring Stats (Example) ---")
    for i in range(15):  # Monitor for 15 seconds
        stats = manager.get_stats()
        print(f"Time {i+1}s - Stats: {stats}")
        if not stats["is_running"] or stats["active_processes"] == 0:
            if i > 5:  # Avoid stopping too early if startup is slow
                print("No active processes detected. Stopping monitoring.")
                break
        time.sleep(1)

    print("\n--- Stopping Bots ---")
    manager.stop_bots()

    print("\n--- Final Stats ---")
    final_stats = manager.get_stats()
    print(f"Final Stats: {final_stats}")

    print("\nConcurrency Manager Example Finished.")
