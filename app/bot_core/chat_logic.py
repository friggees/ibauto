import time
import re
import random
import os  # Add os import
import multiprocessing  # Add multiprocessing import
from typing import Optional, List  # Added List for type hint
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
# Removed duplicate: import time

# Assuming selenium_handler provides the necessary driver and helper functions
try:
    from .selenium_handler import find_element_with_wait, click_element, send_keys_to_element
    from app.config.manager import load_config, load_messages
    # We might need registration logic if logout occurs
    from .registration import handle_registration_process
except ImportError:
    # Fallback for potential path issues or running script directly
    print("Error: Could not import selenium_handler, config manager, or registration. Ensure PYTHONPATH is set correctly or run from project root.")
    # Define dummy functions/classes
    def find_element_with_wait(driver, by, value, timeout=10): return None
    def click_element(element): return False
    def send_keys_to_element(element, text): return False
    def load_config(): return {}
    def load_messages(): return []
    def handle_registration_process(driver): return False

    class Keys:
        ENTER = '\n'  # Simple mock

# Load XPaths from JSON file
try:
    with open('data/xpaths_interaction.json', 'r') as f:
        XPATHS_INTERACTION = json.load(f)
    print("Successfully loaded XPATHS_INTERACTION from data/xpaths_interaction.json")
except FileNotFoundError:
    print("Error: data/xpaths_interaction.json not found. Using empty dictionary.")
    XPATHS_INTERACTION = {}
except json.JSONDecodeError:
    print("Error: Could not decode JSON from data/xpaths_interaction.json. Using empty dictionary.")
    XPATHS_INTERACTION = {}


# --- Core Chat Logic Functions ---


def go_to_inbox(driver, log_queue: multiprocessing.Queue, profile_id: str):
    """Clicks the inbox button and waits for the inbox to load."""
    # Define _log locally for this function
    def _log(message: str):
        try:
            log_queue.put({'bot_id': profile_id, 'message': message})
        except Exception as log_err:
            print(
                f"[Bot Process {os.getpid()} - LOG QUEUE ERROR for {profile_id}] {log_err}\nFALLBACK LOG: {message}")

    _log("Navigating to inbox...")

    # First scroll to top of page to ensure inbox button is visible
    try:
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)  # Brief pause to let scroll complete
    except Exception as e:
        _log(f"Warning: Failed to scroll to top: {e}")

    # Pass log_queue to find_element_with_wait and click_element
    inbox_button = find_element_with_wait(
        driver,
        By.XPATH,
        XPATHS_INTERACTION["navigation"]["inbox_button"],
        log_queue=log_queue, profile_id=profile_id  # Pass log info
    )
    if not click_element(inbox_button, log_queue=log_queue, profile_id=profile_id):  # Pass log info
        _log("Failed to click inbox button.")
        return False

    # Wait for inbox container to be present
    # Pass log_queue to find_element_with_wait
    inbox_container = find_element_with_wait(
        driver,
        By.XPATH,
        XPATHS_INTERACTION["navigation"]["inbox_container_loaded"],
        timeout=15,
        log_queue=log_queue, profile_id=profile_id  # Pass log info
    )
    if not inbox_container:
        _log("Inbox container did not load after clicking button.")
        return False

    # Highlight the found container
    try:
        driver.execute_script(
            "arguments[0].style.border='3px solid red';", inbox_container)
        _log("Highlighted inbox container.")
    except Exception as highlight_err:
        _log(f"Warning: Could not highlight inbox container: {highlight_err}")

    _log("Inbox loaded.")
    return True


def _find_new_user_in_container(driver, container_xpath, user_xpath, interacted_ids_this_pass: set, container_name: str, log_queue: multiprocessing.Queue, profile_id: str):
    """Helper function to find a new user within a specific container."""
    # Define _log locally for this function
    def _log(message: str):
        try:
            log_queue.put({'bot_id': profile_id, 'message': message})
        except Exception as log_err:
            print(
                f"[Bot Process {os.getpid()} - LOG QUEUE ERROR for {profile_id}] {log_err}\nFALLBACK LOG: {message}")

    try:
        # Pass log_queue
        container = find_element_with_wait(
            driver, By.XPATH, container_xpath, timeout=3, log_queue=log_queue, profile_id=profile_id)
        if container:
            # Highlight the container being searched
            try:
                # Blue for search area
                driver.execute_script(
                    "arguments[0].style.border='3px solid blue';", container)
                _log(f"Highlighted {container_name} for search.")
                time.sleep(0.2)  # Brief pause to see highlight
            except Exception as highlight_err:
                _log(
                    f"Warning: Could not highlight {container_name}: {highlight_err}")

            # Find users *relative* to container
            users = container.find_elements(By.XPATH, user_xpath)

            # Remove highlight after search
            try:
                driver.execute_script(
                    "arguments[0].style.border='';", container)
            except Exception:
                pass  # Ignore errors removing highlight

            if users:
                _log(
                    f"Found {len(users)} potential male users in {container_name}.")
                available_users = []
                for user in users:
                    try:
                        # Attempt to get ID for filtering *before* adding to list
                        user_id = None
                        try:
                            user_id = user.get_attribute('data-id')
                        except StaleElementReferenceException:
                            _log(
                                f"Stale element encountered getting ID in {container_name} filter. Skipping.")
                            continue  # Skip stale element
                        except Exception as id_err:
                            _log(
                                f"Error getting data-id attribute in {container_name} filter: {id_err}. Skipping user.")
                            continue  # Skip if ID cannot be read

                        # --- MODIFIED: Always add user if ID exists, removing 'interacted_ids_this_pass' check ---
                        if user_id:
                            available_users.append(user)
                        # Optional: Log if user_id was None
                        # else:
                        #     _log(f"  - Skipping user element in {container_name} (could not get user_id)")
                        # --- END MODIFICATION ---

                    except StaleElementReferenceException:  # Catch staleness during the loop itself
                        _log(
                            f"Stale element encountered iterating users in {container_name}. Skipping.")
                        continue
                    except Exception as filter_err:
                        _log(
                            f"Generic error filtering {container_name} users: {filter_err}")
                        continue

                if available_users:
                    _log(
                        f"Found {len(available_users)} *new* male users in {container_name}, selecting randomly")
                    selected_user = random.choice(available_users)
                    # Scroll the selected user into view before returning
                    try:
                        driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});", selected_user)
                        time.sleep(0.5)
                    except Exception as scroll_err:
                        _log(
                            f"Warning: Could not scroll selected user into view: {scroll_err}")
                    return selected_user  # Return the specific element
                else:
                    _log(
                        f"All male users found in {container_name} have been interacted with this pass.")
            else:
                _log(
                    f"No male users found in {container_name} using relative XPath: {user_xpath}")
        else:
            _log(f"{container_name} container not found using XPath: {container_xpath}")
    except Exception as e:
        _log(f"Error checking {container_name}: {e}")
    return None  # Return None if no new user found in this container


def find_clickable_male_user(driver, interacted_ids_this_pass: set, log_queue: multiprocessing.Queue, profile_id: str):
    """
    Finds a random, new male user element, searching specified containers in order.
    Handles ad iframes. Logs actions via log_queue.
    Args:
        driver: Selenium WebDriver instance.
        interacted_ids_this_pass: A set of user IDs already interacted with in this pass.
        log_queue: The queue for logging.
        profile_id: The bot's profile ID for logging.
    """
    # Define _log locally for this function
    def _log(message: str):
        try:
            log_queue.put({'bot_id': profile_id, 'message': message})
        except Exception as log_err:
            print(
                f"[Bot Process {os.getpid()} - LOG QUEUE ERROR for {profile_id}] {log_err}\nFALLBACK LOG: {message}")

    _log(
        f"Searching for a *new* clickable male user (excluding {len(interacted_ids_this_pass)} interacted)...")

    # 1. Handle Iframes
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if iframes:
            _log(f"Found {len(iframes)} iframes, attempting to remove...")
            # Use more robust iframe removal script
            driver.execute_script("""
                let iframes = document.querySelectorAll('iframe');
                iframes.forEach(el => {
                    try { el.remove(); } catch (e) { console.warn('Could not remove iframe:', el, e); }
                });
                return iframes.length;
            """)
            time.sleep(1)
    except Exception as e:
        _log(f"Error handling iframes: {e}")

    # Define the relative XPath for male users once
    male_user_relative_xpath = XPATHS_INTERACTION["user_finding"]["male_user_data_attr"]

    # 2. Try Primary Inbox Container (using secondary_container XPath)
    _log("Checking primary inbox container (secondary_container)...")
    user_element = _find_new_user_in_container(
        driver,
        # Your primary inbox XPath
        XPATHS_INTERACTION["user_finding"]["secondary_container"],
        male_user_relative_xpath,
        interacted_ids_this_pass,
        "Primary Inbox (secondary_container)",
        log_queue, profile_id  # Pass log info
    )
    if user_element:
        return user_element  # Found one, return the element

    # 3. Try Fallback Additional Users Container (additional_users_container)
    _log("Checking fallback additional users container (additional_users_container)...")
    user_element = _find_new_user_in_container(
        driver,
        # Your fallback XPath
        XPATHS_INTERACTION["user_finding"]["additional_users_container"],
        male_user_relative_xpath,
        interacted_ids_this_pass,
        "Fallback Additional Users (additional_users_container)",
        log_queue, profile_id  # Pass log info
    )
    if user_element:
        return user_element  # Found one, return the element

    # 4. If no user found in either specified container
    _log("No *new* clickable male users found in the specified containers for this pass.")
    return None


def click_user_and_get_id(driver, user_element, log_queue: multiprocessing.Queue, profile_id: str):
    """
    Attempts to extract user ID from the element, then clicks it.
    Uses WebDriverWait to handle staleness before clicking.
    Returns the user_id string or None if failed. Logs actions via log_queue.

    Args:
        driver: Selenium WebDriver instance.
        user_element: The specific user WebElement to interact with.
        log_queue: The queue for logging.
        profile_id: The bot's profile ID for logging.
    """
    # Define _log locally for this function
    def _log(message: str):
        try:
            log_queue.put({'bot_id': profile_id, 'message': message})
        except Exception as log_err:
            print(
                f"[Bot Process {os.getpid()} - LOG QUEUE ERROR for {profile_id}] {log_err}\nFALLBACK LOG: {message}")

    if not user_element:
        _log("click_user_and_get_id received None element.")
        return None

    # --- Try extracting User ID BEFORE clicking ---
    user_id = None
    pre_click_id_extracted = False
    try:
        # Strategy 1: Get data-id directly from the element
        user_id = user_element.get_attribute('data-id')
        if user_id:
            _log(
                f"[ID_EXTRACT PRE-CLICK] Strategy 1: Extracted user ID from element's data-id: {user_id}")
            pre_click_id_extracted = True
        else:
            # Strategy 2: Get data-id from the element's immediate parent
            _log("[ID_EXTRACT PRE-CLICK] Strategy 1 failed, trying parent...")
            try:
                # Ensure parent finding is robust
                parent_element = user_element.find_element(
                    By.XPATH, "./parent::*")  # More specific parent selection
                user_id = parent_element.get_attribute('data-id')
                if user_id:
                    _log(
                        f"[ID_EXTRACT PRE-CLICK] Strategy 2: Extracted user ID from parent's data-id: {user_id}")
                    pre_click_id_extracted = True
                else:
                    _log(
                        "[ID_EXTRACT PRE-CLICK] Strategy 2: data-id not found on parent.")
            except NoSuchElementException:
                _log(
                    "[ID_EXTRACT PRE-CLICK] Strategy 2: Parent element not found using ./parent::*.")
            except StaleElementReferenceException:
                _log(
                    "[ID_EXTRACT PRE-CLICK] Strategy 2: StaleElementReferenceException getting parent data-id.")
            except Exception as e_parent:
                _log(f"[ID_EXTRACT PRE-CLICK] Strategy 2: Error: {e_parent}")

    except StaleElementReferenceException:
        _log("[ID_EXTRACT PRE-CLICK] Strategy 1: StaleElementReferenceException getting data-id. Cannot proceed.")
        # If stale before we even click, we probably can't proceed reliably
        return None
    except Exception as e_direct:
        _log(
            f"[ID_EXTRACT PRE-CLICK] Strategy 1: Error getting data-id: {e_direct}")
        # Allow proceeding to click even if ID extraction failed, URL fallback might work

    if not pre_click_id_extracted:
        _log("[ID_EXTRACT PRE-CLICK] Failed to extract User ID before clicking. Will rely on post-click URL check if click succeeds.")

    # Imports needed for explicit waits
    from selenium.webdriver.support.ui import WebDriverWait
    # Unused import removed: from selenium.webdriver.support import expected_conditions as EC

    max_retries = 3
    clicked = False

    for attempt in range(max_retries):
        # --- IMPORTANT: Refresh element reference inside retry loop ---
        # This is crucial if the element went stale on a previous attempt
        current_element_reference = user_element
        # -------------------------------------------------------------
        try:
            _log(
                f"Attempt {attempt + 1}/{max_retries}: Attempting to click the specific user element provided.")
            # Scroll into view just before clicking
            try:
                # Use JS scrollIntoView for better reliability
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", current_element_reference)
                time.sleep(0.3)  # Brief pause for scroll to settle
            except Exception as scroll_err:
                _log(
                    f"Warning: Could not scroll element into view before click: {scroll_err}")

            # Wait for the specific element to be clickable before attempting the click
            # We need a way to wait for the *specific element reference*
            # EC.element_to_be_clickable expects a locator tuple (By, value)
            # Workaround: Check if the element is displayed and enabled as a proxy
            WebDriverWait(driver, 5).until(
                lambda d: current_element_reference.is_displayed(
                ) and current_element_reference.is_enabled()
            )
            _log(
                f"Attempt {attempt + 1}: Element confirmed displayed and enabled.")

            # Use the refreshed reference for the click
            # Click the specific element passed in, passing log info
            if click_element(current_element_reference, log_queue=log_queue, profile_id=profile_id):
                clicked = True
                _log(
                    f"Attempt {attempt + 1}: Successfully clicked the specific user element.")
                break  # Exit retry loop on success
            else:
                _log(
                    f"Attempt {attempt + 1}: click_element helper returned False for the specific element.")
                time.sleep(1)  # Small delay before retry

        except StaleElementReferenceException as e:
            _log(
                f"Attempt {attempt + 1}: Element became stale during click attempt: {e}")
            # Element is stale, cannot click it. No point retrying the same reference.
            _log("Aborting click attempts due to stale element.")
            return None  # Indicate failure to click
        except TimeoutException as e:  # Catch timeout from the explicit wait
            _log(
                f"Attempt {attempt + 1}: Timeout waiting for element to be clickable/stable: {e}")
            if attempt < max_retries - 1:
                _log(f"Attempt {attempt + 1}: Retrying click...")
                time.sleep(1)  # Wait before retrying
            else:
                _log(
                    f"Attempt {attempt + 1}: Max retries reached after timeout.")
        except Exception as e:
            # Catch other potential errors during the click process
            _log(
                f"Attempt {attempt + 1}: An unexpected error occurred during click attempt: {type(e).__name__} - {e}")
            if attempt < max_retries - 1:
                _log(f"Attempt {attempt + 1}: Retrying click...")
                time.sleep(1)
            else:
                _log(
                    f"Attempt {attempt + 1}: Max retries reached after unexpected error.")

    if not clicked:
        _log("Failed to click user element after all attempts.")
        return None  # Click failed

    _log("Successfully clicked user element. Waiting for potential navigation/update...")
    time.sleep(1.5)  # Slightly longer wait after click for URL/DOM to update

    # --- Final ID Check (Fallback if pre-click failed) ---
    if pre_click_id_extracted:
        _log(
            f"[ID_EXTRACT POST-CLICK] Returning pre-click extracted ID: {user_id}")
        return user_id  # Return the ID we got before clicking
    else:
        # Fallback to URL check if ID wasn't extracted before click
        _log("[ID_EXTRACT POST-CLICK] Pre-click ID extraction failed. Falling back to URL check...")
        try:
            current_url = driver.current_url
            # Use a more general regex to capture IDs after various path segments
            match = re.search(
                r'(?:/chat/|/profile/|/messages/|/user/|user(?:id)?=|/u/|/p/)(\d+)', current_url, re.IGNORECASE)
            if match:
                url_user_id = match.group(1)
                _log(
                    f"[ID_EXTRACT POST-CLICK] Extracted user ID from URL: {url_user_id}")
                return url_user_id
            else:
                _log(
                    f"[ID_EXTRACT POST-CLICK] No user ID found in URL: {current_url}")
        except Exception as e:
            _log(
                f"[ID_EXTRACT POST-CLICK] Error reading or parsing URL for ID: {e}")

        # If URL check also fails
        _log("[ID_EXTRACT POST-CLICK] Could not extract user ID using any method (pre-click or URL).")
        return None


# --- Message Sending/Handling Functions (Unchanged) ---

def count_messages(driver, incoming=True, log_queue: Optional[multiprocessing.Queue] = None, profile_id: Optional[str] = None):
    """Counts incoming or outgoing messages. Optionally logs actions."""
    # Define _log locally for this function
    def _log(message: str):
        if log_queue and profile_id:
            try:
                log_queue.put({'bot_id': profile_id, 'message': message})
            except Exception as log_err:
                print(
                    f"[Bot Process {os.getpid()} - LOG QUEUE ERROR for {profile_id}] {log_err}\nFALLBACK LOG: {message}")
        else:
            # Fallback print if no queue
            print(f"[COUNT_MESSAGES - NO LOG QUEUE] {message}")

    xpath_key = "incoming_message" if incoming else "outgoing_message"
    xpath = XPATHS_INTERACTION.get("messaging", {}).get(xpath_key)
    if not xpath:
        _log(f"Error: XPath for '{xpath_key}' not found in config.")
        return 0
    try:
        # Use find_elements which returns a list (empty if none found)
        elements = driver.find_elements(By.XPATH, xpath)
        # Check for staleness within the count? Less critical here.
        return len(elements)
    except StaleElementReferenceException:
        _log(
            f"Stale element reference while counting {'incoming' if incoming else 'outgoing'} messages. Returning 0.")
        return 0
    except Exception as e:
        _log(
            f"Error counting {'incoming' if incoming else 'outgoing'} messages: {e}")
        return 0


def find_message_input(driver, log_queue: multiprocessing.Queue, profile_id: str):
    """Finds the message input field using multiple strategies. Logs actions."""
    # Define _log locally for this function
    def _log(message: str):
        try:
            log_queue.put({'bot_id': profile_id, 'message': message})
        except Exception as log_err:
            print(
                f"[Bot Process {os.getpid()} - LOG QUEUE ERROR for {profile_id}] {log_err}\nFALLBACK LOG: {message}")

    messaging_xpaths = XPATHS_INTERACTION.get("messaging", {})
    input_xpath_keys = [
        "input_contenteditable", "input_textarea_id", "input_class_write_msg",
        "input_in_input_msg_write", "input_textarea_general", "input_input_general",
        "input_any_contenteditable", "input_any_textarea", "input_any_text",
    ]
    for key in input_xpath_keys:
        xpath = messaging_xpaths.get(key)
        if not xpath:
            continue  # Skip if key not in config
        # Pass log info
        element = find_element_with_wait(
            driver, By.XPATH, xpath, timeout=1, log_queue=log_queue, profile_id=profile_id)
        if element:
            # Add checks for visibility/enabled state?
            if element.is_displayed() and element.is_enabled():
                _log(f"Found usable message input using XPath key: {key}")
                return element
            else:
                _log(
                    f"Found message input using XPath key: {key}, but it's not displayed/enabled.")
    _log("Could not find a usable message input field.")
    return None


def find_send_button(driver, log_queue: multiprocessing.Queue, profile_id: str):
    """Finds the send button using multiple strategies. Logs actions."""
    # Define _log locally for this function
    def _log(message: str):
        try:
            log_queue.put({'bot_id': profile_id, 'message': message})
        except Exception as log_err:
            print(
                f"[Bot Process {os.getpid()} - LOG QUEUE ERROR for {profile_id}] {log_err}\nFALLBACK LOG: {message}")

    messaging_xpaths = XPATHS_INTERACTION.get("messaging", {})
    button_xpath_keys = [
        "send_button_id", "send_button_class_msg", "send_button_class_send",
        "send_button_div", "send_button_icon_plane", "send_button_icon_send",
        "send_button_onclick_button", "send_button_onclick_link", "send_button_submit",
        "send_button_text_exact", "send_button_text_contains",
    ]
    for key in button_xpath_keys:
        xpath = messaging_xpaths.get(key)
        if not xpath:
            continue  # Skip if key not in config
        # Pass log info
        element = find_element_with_wait(
            driver, By.XPATH, xpath, timeout=1, log_queue=log_queue, profile_id=profile_id)
        if element:
            # Add checks for visibility/enabled state
            if element.is_displayed() and element.is_enabled():
                _log(f"Found usable send button using XPath key: {key}")
                return element
            else:
                _log(
                    f"Found send button using XPath key: {key}, but it's not displayed/enabled.")
    _log("Could not find a usable send button via XPath.")
    return None


def send_message(driver, message_text: str, log_queue: multiprocessing.Queue, profile_id: str):
    """Types a message and attempts to send it. Logs actions."""
    # Define _log locally for this function
    def _log(message: str):
        try:
            log_queue.put({'bot_id': profile_id, 'message': message})
        except Exception as log_err:
            print(
                f"[Bot Process {os.getpid()} - LOG QUEUE ERROR for {profile_id}] {log_err}\nFALLBACK LOG: {message}")

    _log(f"Attempting to send message: '{message_text[:50]}...'")
    # Pass log info
    input_field = find_message_input(driver, log_queue, profile_id)
    if not input_field:
        _log("Send message failed: Could not find input field.")
        return False

    # Clear field before sending keys? Sometimes needed.
    try:
        input_field.clear()
        time.sleep(0.1)
    except Exception as clear_err:
        _log(f"Warning: Could not clear input field: {clear_err}")

    # Pass log info AND driver
    if not send_keys_to_element(driver, input_field, message_text, log_queue=log_queue, profile_id=profile_id):
        _log("Send message failed: send_keys_to_element returned False.")
        return False

    time.sleep(0.5)  # Small delay after typing

    # Try clicking send button first
    # Pass log info
    send_button = find_send_button(driver, log_queue, profile_id)
    try:
        # Check if button exists before clicking
        # Pass log info to click_element
        if send_button and click_element(send_button, log_queue=log_queue, profile_id=profile_id):
            _log("Message sent via button click.")
            return True
        else:
            _log("click_element returned False for send button.")
    except TimeoutException:
        _log("Timeout waiting for send button to be clickable.")
    except AttributeError:  # If send_button is None
        _log("Send button not found, cannot attempt click.")
    except Exception as btn_click_err:
        _log(f"Error clicking send button: {btn_click_err}")

    # If button click fails or button not found, try pressing Enter in the input field
    _log("Send button click failed or button not found/usable, trying Enter key in input field...")
    try:
        # Ensure input field is still valid before sending Enter
        if input_field.is_displayed() and input_field.is_enabled():
            # Pass log info AND driver
            if send_keys_to_element(driver, input_field, Keys.ENTER, log_queue=log_queue, profile_id=profile_id):
                _log("Message sent via Enter key.")
                return True
            else:
                _log("send_keys_to_element returned False for Enter key.")
        else:
            _log("Input field became non-interactable before sending Enter.")
    except StaleElementReferenceException:
        _log("Input field became stale before sending Enter.")
    except Exception as enter_err:
        _log(f"Error sending Enter key: {enter_err}")

    _log("Failed to send message using button or Enter key.")
    return False


# Added user_states_in_memory
def handle_chat_cycle(driver, profile_id, stats_queue, log_queue: multiprocessing.Queue, assigned_city: Optional[str], usernames_list: List[str], user_states_in_memory: dict):
    """
    Main loop for handling chat interactions for one browser instance.
    Sends stats and logs back via the provided queues.
    Uses an in-memory dictionary to track user state for this instance.

    Args:
        driver: The Selenium WebDriver instance.
        profile_id: The AdsPower profile ID for logging.
        stats_queue: The queue for reporting stats (e.g., link sent).
        log_queue: The queue for reporting log messages.
        assigned_city: The city assigned to this bot instance for registration.
        usernames_list: A list of usernames to attempt during registration.
    """
    # --- Helper function for logging within this cycle ---
    def _log(message: str):
        """Sends a formatted log message to the log queue."""
        try:
            log_queue.put({'bot_id': profile_id, 'message': message})
        except Exception as log_err:
            # Fallback to print if queue fails
            print(
                f"[Bot Process {os.getpid()} - LOG QUEUE ERROR for {profile_id}] {log_err}")
            print(
                f"[Bot Process {os.getpid()} - FALLBACK LOG for {profile_id}] {message}")

    local_sent_links_count = 0  # Track locally for logging if needed

    config = load_config()
    messages = load_messages()
    onlyfans_link = config.get("onlyfans_link", "")
    if not messages:
        _log("No messages loaded. Cannot chat.")  # Use _log
        return

    # Replace placeholder in messages
    final_message_index = -1
    for i, msg in enumerate(messages):
        if "{onlyfans_link}" in msg:
            messages[i] = msg.replace("{onlyfans_link}", onlyfans_link)
            final_message_index = i
            break  # Assume only one link message

    if final_message_index == -1:
        # Use _log
        _log("Warning: No message contains the '{onlyfans_link}' placeholder.")
        final_message_index = len(messages) - 1  # Treat last message as final

    # Imports needed for explicit waits (keep here)
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    # --- Main Interaction Loop ---
    cycle_count = 0
    interacted_user_ids_this_pass = set()  # Users interacted with since last reset
    no_new_user_streak = 0  # Track consecutive cycles where no new user is found

    while True:  # Loop indefinitely for this profile
        cycle_count += 1
        # Use _log
        _log(f"\n[Cycle: {cycle_count}] Starting interaction cycle...")

        # --- Calculate phase thresholds ---
        total_phases = len(messages)
        # Start sequential sending at the (N-3)th phase if N >= 5
        sequential_start_phase = total_phases - \
            3 if total_phases >= 5 else -1  # -1 if not applicable
        # --- End phase thresholds ---

        current_user_id = None  # Reset for this cycle
        try:
            # --- Proactive Ad Check ---
            # (Keep existing ad check logic here, replace prints with _log)
            try:
                current_url = driver.current_url
                if "#google_vignette" in current_url:
                    # Use _log
                    _log(
                        f"[Cycle: {cycle_count}] Detected ad URL fragment. Refreshing page...")
                    driver.refresh()
                    # Use _log
                    _log(
                        f"[Cycle: {cycle_count}] Waiting for inbox button after ad refresh...")
                    WebDriverWait(driver, 60).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, XPATHS_INTERACTION["navigation"]["inbox_button"]))
                    )
                    # Use _log
                    _log(
                        f"[Cycle: {cycle_count}] Page refreshed and inbox button found after ad. Attempting to click inbox...")
                    try:
                        inbox_button_element = driver.find_element(
                            By.XPATH, XPATHS_INTERACTION["navigation"]["inbox_button"])
                        # Pass log_queue to click_element
                        if click_element(inbox_button_element, log_queue=log_queue, profile_id=profile_id):
                            # Use _log
                            _log(
                                f"[Cycle: {cycle_count}] Clicked inbox button after ad refresh.")
                            time.sleep(1)
                        else:
                            # Use _log
                            _log(
                                f"[Cycle: {cycle_count}] Failed to click inbox button after ad refresh. Will retry next cycle.")
                    except Exception as click_err:
                        # Use _log
                        _log(
                            f"[Cycle: {cycle_count}] Error clicking inbox button after ad refresh: {click_err}")
                    continue  # Restart cycle after handling ad
            except Exception as ad_check_err:
                # Use _log
                _log(
                    f"[Cycle: {cycle_count}] Error during proactive ad check: {ad_check_err}")
            # --- End Proactive Ad Check ---

            # 1. Go to Inbox (ensure we are in the right view)
            # Pass log_queue and profile_id
            if not go_to_inbox(driver, log_queue, profile_id):
                # Use _log
                _log(
                    f"[Cycle: {cycle_count}] Failed to navigate to inbox. Refreshing...")
                try:
                    driver.refresh()
                    # Use _log
                    _log(
                        f"[Cycle: {cycle_count}] Waiting for inbox button after failed navigation refresh...")
                    WebDriverWait(driver, 60).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, XPATHS_INTERACTION["navigation"]["inbox_button"]))
                    )
                    # Use _log
                    _log(
                        f"[Cycle: {cycle_count}] Page refreshed and inbox button found after failed navigation.")
                except Exception as refresh_err:
                    # Use _log
                    _log(
                        f"[Cycle: {cycle_count}] Failed to refresh/find inbox after error: {refresh_err}. Stopping.")
                    break  # Exit loop if refresh fails badly
                continue  # Retry cycle

            # 2. Find a *new* male user element to interact with using the new function
            # Pass log_queue and profile_id
            user_element = find_clickable_male_user(
                driver, interacted_user_ids_this_pass, log_queue, profile_id)

            if not user_element:
                no_new_user_streak += 1
                # Use _log
                _log(
                    f"[Cycle: {cycle_count}] No *new* suitable user found in specified containers (Streak: {no_new_user_streak}). Resetting pass and waiting...")
                interacted_user_ids_this_pass.clear()  # Reset for the next pass
                # Implement increasing wait time based on streak?
                wait_time = min(15 + (no_new_user_streak * 5), 60)
                # Use _log
                _log(
                    f"Waiting for {wait_time:.1f} seconds before next pass...")
                time.sleep(wait_time)
                continue  # Retry cycle, starting a new pass
            else:
                no_new_user_streak = 0  # Reset streak if a user was found

            # 3. Click user element and get ID using the updated function
            # Pass log_queue and profile_id
            current_user_id = click_user_and_get_id(
                driver, user_element, log_queue, profile_id)

            if not current_user_id:
                # Use _log
                _log(
                    f"[Cycle: {cycle_count}] Failed to click or get ID for the selected user element. Trying next cycle.")
                # Element might be stale or unclickable, don't add to interacted set yet.
                # Go back to inbox view to be safe before next cycle
                # Pass log_queue and profile_id
                go_to_inbox(driver, log_queue, profile_id)
                time.sleep(random.uniform(1, 3))  # Small pause before retry
                continue  # Retry cycle

            # --- Interaction Logic ---
            # Use _log
            _log(
                f"[Cycle: {cycle_count}] Successfully interacted with User ID: {current_user_id}")
            # Add this user to the set of interacted users *after* successful click/ID retrieval
            interacted_user_ids_this_pass.add(current_user_id)

            # 4. Determine message phase and state for this user from in-memory dict
            # Use string keys for consistency
            user_id_str = str(current_user_id)
            user_state = user_states_in_memory.get(user_id_str)

            if user_state is None:
                # Initialize state for a new user directly in the dictionary
                user_state = {
                    "first_contact": time.time(),  # Track first contact time
                    "message_phase": 0,
                    "user_incoming_message_count_at_last_send": -1,
                    "last_interaction": time.time()  # Initialize last interaction
                }
                user_states_in_memory[user_id_str] = user_state
                # Use _log
                _log(
                    f"[Cycle: {cycle_count}] Initialized in-memory state for new User ID: {user_id_str}")

            # Extract current phase and last recorded incoming count from the user state
            current_phase = user_state.get("message_phase", 0)
            last_recorded_incoming = user_state.get(
                "user_incoming_message_count_at_last_send", -1)

            # LOGGING (Use _log)
            _log(f"[Cycle: {cycle_count}] Retrieved in-memory state for User ID: {user_id_str} - Phase: {current_phase}, Last Incoming Count: {last_recorded_incoming}")

            if current_phase > final_message_index:
                # Use _log
                _log(
                    f"[Cycle: {cycle_count}] User {user_id_str} has already received the final message (Phase {current_phase}). Skipping.")
                # State will be lost when process ends, no explicit cleanup needed
                continue  # Find a new user

            # 5. Check if it's time to send the next message
            #    - Check for reply if needed
            #    - Send message
            #    - Update phase and state
            #    - Wait if final message

            # --- Check if reply is needed and received ---
            # Log before check
            _log(
                f"[Cycle: {cycle_count}] Preparing to check reply/send message for User ID: {user_id_str}, Phase: {current_phase}")

            # Determine if a reply check is needed based on the new rules
            reply_check_needed = False
            if total_phases <= 4:
                # For 4 or fewer phases, check reply for phases > 0
                reply_check_needed = 0 < current_phase < total_phases
            elif total_phases >= 5:
                # For 5 or more phases, check reply only for phases before the sequential start
                reply_check_needed = 0 < current_phase < sequential_start_phase

            _log(f"[Cycle: {cycle_count}] Total Phases: {total_phases}, Seq Start Phase: {sequential_start_phase}, Current Phase: {current_phase}, Reply Check Needed: {reply_check_needed}")

            if reply_check_needed:
                # Use _log
                _log(
                    f"[Cycle: {cycle_count}] Reply check needed for phase {current_phase}. Checking incoming messages...")
                # Pass log_queue and profile_id
                # Log before count
                _log(
                    f"[Cycle: {cycle_count}] Calling count_messages (incoming=True)...")
                num_incoming_now = count_messages(
                    driver, incoming=True, log_queue=log_queue, profile_id=profile_id)
                # Log after count
                _log(
                    f"[Cycle: {cycle_count}] count_messages (incoming=True) returned: {num_incoming_now}. Last recorded: {last_recorded_incoming}")

                if num_incoming_now <= last_recorded_incoming:
                    # Use _log
                    _log(
                        f"[Cycle: {cycle_count}] No new incoming message detected from {current_user_id} since last send. Skipping send for this cycle.")
                    # Go back to inbox implicitly by continuing the main loop
                    time.sleep(random.uniform(1, 3))
                    continue  # Skip sending to this user, find next user
                else:
                    # Use _log
                    _log(
                        f"[Cycle: {cycle_count}] New incoming message detected ({num_incoming_now} > {last_recorded_incoming}). Proceeding to send phase {current_phase}.")
            # --- End Reply Check ---

            # --- Send the message ---
            # Ensure current_phase is valid index
            if current_phase >= total_phases:
                _log(
                    f"[Cycle: {cycle_count}] Error: current_phase {current_phase} is out of bounds for messages list (length {total_phases}). Skipping send.")
                continue  # Skip to next cycle if phase is invalid

            message_to_send = messages[current_phase]
            # Use _log
            _log(
                f"[Cycle: {cycle_count}] Preparing to send phase {current_phase} message to {current_user_id}: '{message_to_send[:50]}...'")

            # Pass log_queue and profile_id to send_message
            # Log before send
            _log(f"[Cycle: {cycle_count}] Calling send_message...")
            send_success = send_message(
                driver, message_to_send, log_queue, profile_id)
            # Log after send
            _log(
                f"[Cycle: {cycle_count}] send_message returned: {send_success}")

            if send_success:
                # --- Update State ---
                phase_just_sent = current_phase  # Store before incrementing
                new_phase = current_phase + 1
                # Use _log
                _log(
                    f"[Cycle: {cycle_count}] Updating phase for User ID {current_user_id} from {phase_just_sent} to {new_phase}")

                # Record incoming count *after* sending, so next check compares against this
                # Pass log_queue and profile_id
                num_incoming_after_send = count_messages(
                    driver, incoming=True, log_queue=log_queue, profile_id=profile_id)
                # Use _log
                _log(
                    f"[Cycle: {cycle_count}] Recording incoming count {num_incoming_after_send} for User ID {user_id_str} after sending.")

                # Update state directly in the in-memory dictionary
                user_state["message_phase"] = new_phase
                user_state["user_incoming_message_count_at_last_send"] = num_incoming_after_send
                # Update last interaction time
                user_state["last_interaction"] = time.time()
                # No need to call user_states_in_memory[user_id_str] = user_state again, as user_state is a reference

                # --- Handle Link Sent ---
                if phase_just_sent == final_message_index:
                    local_sent_links_count += 1
                    # Use _log
                    _log(
                        f"[Cycle: {cycle_count}] Final link sent to {current_user_id}! Total sent by this instance: {local_sent_links_count}")
                    try:
                        stats_queue.put(
                            {"type": "link_sent", "profile_id": profile_id})
                    except Exception as q_err:
                        # Use _log
                        _log(f"Error putting item in stats_queue: {q_err}")

                # --- NEW: Report Conversation Started ---
                # Check if this was the *first* message sent (phase 0)
                if phase_just_sent == 0:
                    _log(
                        f"[Cycle: {cycle_count}] First message (phase 0) sent to {current_user_id}. Reporting 'conversation_started'.")
                    try:
                        # Send a specific message type to the stats queue
                        stats_queue.put(
                            {"type": "conversation_started", "profile_id": profile_id})
                    except Exception as q_err:
                        _log(
                            f"Error putting 'conversation_started' in stats_queue: {q_err}")
                # --- END NEW ---

                # --- Post-Send Logic: Phase Update & Sequential Sending ---
                if total_phases >= 5 and phase_just_sent >= sequential_start_phase:
                    # --- Start or continue sequential sending ---
                    _log(
                        f"[Cycle: {cycle_count}] Phase {phase_just_sent} is part of the final sequence (>= {sequential_start_phase}). Starting/Continuing sequential send.")
                    # Loop from the *next* phase up to the last one
                    for sequential_phase in range(phase_just_sent + 1, total_phases):
                        _log(
                            f"[Cycle: {cycle_count}] [SEQ] Attempting to send sequential phase {sequential_phase}...")
                        next_message = messages[sequential_phase]
                        _log(
                            f"[Cycle: {cycle_count}] [SEQ] Message: '{next_message[:50]}...'")

                        # Pass log_queue and profile_id
                        seq_send_success = send_message(
                            driver, next_message, log_queue, profile_id)
                        _log(
                            f"[Cycle: {cycle_count}] [SEQ] send_message for phase {sequential_phase} returned: {seq_send_success}")

                        if seq_send_success:
                            # Update state for the phase just sent sequentially
                            user_state["message_phase"] = sequential_phase + 1
                            num_incoming_after_seq_send = count_messages(
                                driver, incoming=True, log_queue=log_queue, profile_id=profile_id)
                            user_state["user_incoming_message_count_at_last_send"] = num_incoming_after_seq_send
                            user_state["last_interaction"] = time.time()
                            _log(
                                f"[Cycle: {cycle_count}] [SEQ] Updated phase to {sequential_phase + 1}, recorded incoming {num_incoming_after_seq_send}")

                            # Handle link sent stat if this was the final message
                            if sequential_phase == final_message_index:  # final_message_index is the index of the link message
                                local_sent_links_count += 1
                                _log(
                                    f"[Cycle: {cycle_count}] [SEQ] Final link (phase {sequential_phase}) sent sequentially to {current_user_id}! Total sent: {local_sent_links_count}")
                                try:
                                    stats_queue.put(
                                        {"type": "link_sent", "profile_id": profile_id})
                                except Exception as q_err:
                                    _log(
                                        f"Error putting 'link_sent' in stats_queue: {q_err}")

                            # Pause 5 seconds *unless* it was the very last message
                            if sequential_phase < total_phases - 1:
                                _log(
                                    f"[Cycle: {cycle_count}] [SEQ] Pausing 5 seconds after sending phase {sequential_phase}...")
                                time.sleep(5)
                        else:
                            _log(
                                f"[Cycle: {cycle_count}] [SEQ] Failed to send sequential phase {sequential_phase}. Breaking sequence for user {current_user_id}.")
                            break  # Stop sequential sending for this user if one fails
                    # After the loop (or break), the main loop will continue to the next cycle
                else:
                    # --- Normal phase update (not in sequential block or total_phases < 5) ---
                    # State was already updated before this block for the initial send_success
                    _log(
                        f"[Cycle: {cycle_count}] Phase {phase_just_sent} sent. Not starting/continuing sequential send.")
                    # No extra wait needed here, loop continues naturally

            else:
                # Handle failed send (Original logic)
                # Use _log
                _log(
                    f"[Cycle: {cycle_count}] Failed to send message for phase {current_phase} to {current_user_id}.")
                time.sleep(5)
                continue  # Continue to next cycle attempt

            # The loop naturally continues, which will lead back to go_to_inbox()

        except Exception as e:
            _log(
                f"[Cycle: {cycle_count}] An error occurred: {type(e).__name__} - {e}")

            # --- First Recovery Attempt: Refresh & Continue ---
            _log(
                f"[Cycle: {cycle_count}] Attempting initial recovery: Refresh page...")
            try:
                driver.refresh()
                _log("Waiting for inbox button after initial error refresh...")
                WebDriverWait(driver, 60).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, XPATHS_INTERACTION["navigation"]["inbox_button"]))
                )
                _log("Page refreshed and inbox button found. Continuing to next cycle...")
                continue  # Try the next cycle from the start after refresh

            except Exception as refresh_err:
                _log(
                    f"Failed during initial refresh/wait: {refresh_err}. Proceeding to full recovery...")
                # Fall through to full recovery if refresh fails

            # --- Second Recovery Attempt: Full Sequence ---
            _log(
                f"[Cycle: {cycle_count}] Initial refresh failed or didn't prevent error. Initiating full recovery sequence...")
            # Pass all necessary arguments
            recovery_successful = _handle_full_recovery_sequence(
                driver, log_queue, profile_id, assigned_city, usernames_list
            )

            if recovery_successful:
                _log(
                    f"[Cycle: {cycle_count}] Full recovery sequence successful. Continuing next cycle.")
                continue  # Continue to the next cycle attempt
            else:
                _log(
                    f"[Cycle: {cycle_count}] Full recovery sequence failed or triggered re-registration. Stopping interaction.")
                break  # Exit the loop for this profile


# --- Recovery Helper Function ---

def _handle_full_recovery_sequence(driver, log_queue: multiprocessing.Queue, profile_id: str, assigned_city: Optional[str], usernames_list: List[str]):
    """
    Handles the full error recovery sequence after an initial refresh+retry failed.
    Checks for popups, tries inbox, checks registration, refreshes again, etc.

    Returns:
        True if recovery was successful (e.g., back in inbox),
        False if recovery failed or triggered re-registration.
    """
    def _log(message: str):
        """Local logger for recovery sequence."""
        try:
            log_queue.put(
                {'bot_id': profile_id, 'message': f"[RECOVERY] {message}"})
        except Exception as log_err:
            print(
                f"[Bot Process {os.getpid()} - LOG QUEUE ERROR for {profile_id}] {log_err}\nFALLBACK LOG: [RECOVERY] {message}")

    _log("Starting full recovery sequence...")

    # --- Step 3a & 3b: Check for Popup and Click OK ---
    try:
        _log("Checking for 'Something went wrong' popup...")
        # Use short timeout as popup might not be there
        popup_text = find_element_with_wait(
            driver, By.XPATH, "//*[contains(text(), 'Something went wrong.')]", timeout=2, log_queue=log_queue, profile_id=profile_id)
        ok_button = find_element_with_wait(
            driver, By.XPATH, "//button[normalize-space(.)='OK']", timeout=2, log_queue=log_queue, profile_id=profile_id)

        if popup_text or ok_button:
            _log("Popup detected. Attempting to click OK button...")
            if ok_button:
                # Pass log info
                clicked_ok = click_element(
                    ok_button, log_queue=log_queue, profile_id=profile_id)
                _log(f"Click OK button attempt result: {clicked_ok}")
            else:
                _log("OK button element not found, cannot click.")
            time.sleep(1)  # Pause after potential click
        else:
            _log("Popup text/button not found.")

    except Exception as popup_err:
        _log(f"Error during popup check/click: {popup_err}")

    # --- Step 3c: Recovery Attempt 1: Try Inbox ---
    _log("Recovery Attempt 1: Trying to navigate to Inbox...")
    # Pass log info
    if go_to_inbox(driver, log_queue, profile_id):
        _log("Recovery Attempt 1: Successfully navigated to Inbox. Recovery successful.")
        return True  # Recovered to a known state

    # --- Step 3d: Recovery Attempt 2: Check Registration Page & Second Refresh ---
    _log("Recovery Attempt 1 (Inbox) failed.")
    _log("Recovery Attempt 2: Checking for registration page...")
    try:
        # Use the registration XPath for username input
        # Assuming this is correct from registration.py
        username_input_xpath = "//input[@id='username']"
        # Pass log info
        username_field = find_element_with_wait(
            driver, By.XPATH, username_input_xpath, timeout=3, log_queue=log_queue, profile_id=profile_id)
        if username_field:
            _log("Recovery Attempt 2: Registration page detected (username field found). Triggering re-registration...")
            # Pass log info
            if handle_registration_process(driver, assigned_city, usernames_list, log_queue, profile_id):
                _log("Re-registration successful during recovery.")
            else:
                _log("Re-registration failed during recovery.")
            return False  # Re-registration attempted, stop current cycle flow
        else:
            # Username field NOT found
            _log(
                "Recovery Attempt 2: Not on registration page. Performing second refresh...")
            try:
                driver.refresh()
                _log("Waiting for inbox button after second refresh...")
                WebDriverWait(driver, 60).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, XPATHS_INTERACTION["navigation"]["inbox_button"]))
                )
                _log("Page refreshed and inbox button found after second refresh.")

                # --- Repeat Step 3c (Try Inbox again) ---
                _log("Recovery Attempt 2: Trying Inbox again after second refresh...")
                # Pass log info
                if go_to_inbox(driver, log_queue, profile_id):
                    _log(
                        "Recovery Attempt 2: Successfully navigated to Inbox after second refresh. Recovery successful.")
                    return True  # Recovered
            except Exception as refresh_err:
                _log(
                    f"Error during second refresh or waiting for inbox: {refresh_err}")
                # Proceed to next check even if refresh fails
    except Exception as check_reg_err:
        _log(f"Error checking for registration page: {check_reg_err}")
        # Proceed to next check

    # --- Step 3e: Recovery Attempt 3: Check Registration Page Again ---
    _log("Recovery Attempt 2 (Inbox after second refresh) failed.")
    _log("Recovery Attempt 3: Checking for registration page again...")
    try:
        username_input_xpath = "//input[@id='username']"
        # Pass log info
        username_field = find_element_with_wait(
            driver, By.XPATH, username_input_xpath, timeout=3, log_queue=log_queue, profile_id=profile_id)
        if username_field:
            _log(
                "Recovery Attempt 3: Registration page detected. Triggering re-registration...")
            # Pass log info
            if handle_registration_process(driver, assigned_city, usernames_list, log_queue, profile_id):
                _log("Re-registration successful during recovery (attempt 3).")
            else:
                _log("Re-registration failed during recovery (attempt 3).")
            return False  # Re-registration attempted
    except Exception as check_reg_err_2:
        _log(
            f"Error checking for registration page (attempt 3): {check_reg_err_2}")

    # --- Step 3f: Final Fallback: Clear Cookies & Restart ---
    _log("Recovery Attempt 3 failed or registration page not found.")
    _log("Final Fallback: Clearing cookies and attempting re-registration...")
    try:
        driver.delete_all_cookies()
        _log("Cookies cleared.")
        # Navigate to base URL - get from config? Or hardcode?
        base_url = "https://chatib.us/"  # Assuming base URL
        _log(f"Navigating to base URL: {base_url}")
        driver.get(base_url)
        time.sleep(3)  # Wait for page load

        _log("Triggering re-registration after clearing cookies...")
        # Pass log info
        if handle_registration_process(driver, assigned_city, usernames_list, log_queue, profile_id):
            _log("Re-registration successful after clearing cookies.")
        else:
            _log("Re-registration failed after clearing cookies.")
        return False  # Re-registration attempted, stop current flow
    except Exception as final_fallback_err:
        _log(
            f"Error during final fallback (clear cookies/re-register): {final_fallback_err}")
        return False  # Final recovery failed

    _log("Full recovery sequence completed, but failed to recover to a usable state.")
    return False  # Indicate recovery failure
