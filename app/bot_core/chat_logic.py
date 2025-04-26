import time
import re
import random
from typing import Optional, List  # Added List for type hint
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.keys import Keys
import json  # Added json import

# Import the new user_tracker module
from app.data import user_tracker

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


def go_to_inbox(driver):
    """Clicks the inbox button and waits for the inbox to load."""
    print("Navigating to inbox...")

    # First scroll to top of page to ensure inbox button is visible
    try:
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)  # Brief pause to let scroll complete
    except Exception as e:
        print(f"Warning: Failed to scroll to top: {e}")

    inbox_button = find_element_with_wait(
        driver,
        By.XPATH,
        XPATHS_INTERACTION["navigation"]["inbox_button"]
    )
    if not click_element(inbox_button):
        print("Failed to click inbox button.")
        return False

    # Wait for inbox container to be present
    inbox_container = find_element_with_wait(
        driver,
        By.XPATH,
        XPATHS_INTERACTION["navigation"]["inbox_container_loaded"],
        timeout=15
    )
    if not inbox_container:
        print("Inbox container did not load after clicking button.")
        return False

    # Highlight the found container
    try:
        driver.execute_script(
            "arguments[0].style.border='3px solid red';", inbox_container)
        print("Highlighted inbox container.")
    except Exception as highlight_err:
        print(f"Warning: Could not highlight inbox container: {highlight_err}")

    print("Inbox loaded.")
    return True


def _find_new_user_in_container(driver, container_xpath, user_xpath, interacted_ids_this_pass: set, container_name: str):
    """Helper function to find a new user within a specific container."""
    try:
        container = find_element_with_wait(
            driver, By.XPATH, container_xpath, timeout=3)
        if container:
            # Highlight the container being searched
            try:
                # Blue for search area
                driver.execute_script(
                    "arguments[0].style.border='3px solid blue';", container)
                print(f"Highlighted {container_name} for search.")
                time.sleep(0.2)  # Brief pause to see highlight
            except Exception as highlight_err:
                print(
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
                print(
                    f"Found {len(users)} potential male users in {container_name}.")
                available_users = []
                for user in users:
                    try:
                        # Attempt to get ID for filtering *before* adding to list
                        user_id = None
                        try:
                            user_id = user.get_attribute('data-id')
                        except StaleElementReferenceException:
                            print(
                                f"Stale element encountered getting ID in {container_name} filter. Skipping.")
                            continue  # Skip stale element
                        except Exception as id_err:
                            print(
                                f"Error getting data-id attribute in {container_name} filter: {id_err}. Skipping user.")
                            continue  # Skip if ID cannot be read

                        # --- MODIFIED: Always add user if ID exists, removing 'interacted_ids_this_pass' check ---
                        if user_id:
                            available_users.append(user)
                        # Optional: Log if user_id was None (though the try/except above should catch most issues)
                        # else:
                        #     print(f"  - Skipping user element in {container_name} (could not get user_id)")
                        # --- END MODIFICATION ---

                    except StaleElementReferenceException:  # Catch staleness during the loop itself
                        print(
                            f"Stale element encountered iterating users in {container_name}. Skipping.")
                        continue
                    except Exception as filter_err:
                        print(
                            f"Generic error filtering {container_name} users: {filter_err}")
                        continue

                if available_users:
                    print(
                        f"Found {len(available_users)} *new* male users in {container_name}, selecting randomly")
                    selected_user = random.choice(available_users)
                    # Scroll the selected user into view before returning
                    try:
                        driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});", selected_user)
                        time.sleep(0.5)
                    except Exception as scroll_err:
                        print(
                            f"Warning: Could not scroll selected user into view: {scroll_err}")
                    return selected_user  # Return the specific element
                else:
                    print(
                        f"All male users found in {container_name} have been interacted with this pass.")
            else:
                print(
                    f"No male users found in {container_name} using relative XPath: {user_xpath}")
        else:
            print(
                f"{container_name} container not found using XPath: {container_xpath}")
    except Exception as e:
        print(f"Error checking {container_name}: {e}")
    return None  # Return None if no new user found in this container


def find_clickable_male_user(driver, interacted_ids_this_pass: set):
    """
    Finds a random, new male user element, searching specified containers in order.
    Handles ad iframes.

    Args:
        driver: Selenium WebDriver instance.
        interacted_ids_this_pass: A set of user IDs already interacted with in this pass.
    """
    print(
        f"Searching for a *new* clickable male user (excluding {len(interacted_ids_this_pass)} interacted)...")

    # 1. Handle Iframes
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if iframes:
            print(f"Found {len(iframes)} iframes, attempting to remove...")
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
        print(f"Error handling iframes: {e}")

    # Define the relative XPath for male users once
    male_user_relative_xpath = XPATHS_INTERACTION["user_finding"]["male_user_data_attr"]

    # 2. Try Primary Inbox Container (using secondary_container XPath)
    print("Checking primary inbox container (secondary_container)...")
    user_element = _find_new_user_in_container(
        driver,
        # Your primary inbox XPath
        XPATHS_INTERACTION["user_finding"]["secondary_container"],
        male_user_relative_xpath,
        interacted_ids_this_pass,
        "Primary Inbox (secondary_container)"
    )
    if user_element:
        return user_element  # Found one, return the element

    # 3. Try Fallback Additional Users Container (additional_users_container)
    print("Checking fallback additional users container (additional_users_container)...")
    user_element = _find_new_user_in_container(
        driver,
        # Your fallback XPath
        XPATHS_INTERACTION["user_finding"]["additional_users_container"],
        male_user_relative_xpath,
        interacted_ids_this_pass,
        "Fallback Additional Users (additional_users_container)"
    )
    if user_element:
        return user_element  # Found one, return the element

    # 4. If no user found in either specified container
    print("No *new* clickable male users found in the specified containers for this pass.")
    return None


def click_user_and_get_id(driver, user_element):
    """
    Attempts to extract user ID from the element, then clicks it.
    Uses WebDriverWait to handle staleness before clicking.
    Returns the user_id string or None if failed.

    Args:
        driver: Selenium WebDriver instance.
        user_element: The specific user WebElement to interact with.
    """
    if not user_element:
        print("click_user_and_get_id received None element.")
        return None

    # --- Try extracting User ID BEFORE clicking ---
    user_id = None
    pre_click_id_extracted = False
    try:
        # Strategy 1: Get data-id directly from the element
        user_id = user_element.get_attribute('data-id')
        if user_id:
            print(
                f"[ID_EXTRACT PRE-CLICK] Strategy 1: Extracted user ID from element's data-id: {user_id}")
            pre_click_id_extracted = True
        else:
            # Strategy 2: Get data-id from the element's immediate parent
            print("[ID_EXTRACT PRE-CLICK] Strategy 1 failed, trying parent...")
            try:
                # Ensure parent finding is robust
                parent_element = user_element.find_element(
                    By.XPATH, "./parent::*")  # More specific parent selection
                user_id = parent_element.get_attribute('data-id')
                if user_id:
                    print(
                        f"[ID_EXTRACT PRE-CLICK] Strategy 2: Extracted user ID from parent's data-id: {user_id}")
                    pre_click_id_extracted = True
                else:
                    print(
                        "[ID_EXTRACT PRE-CLICK] Strategy 2: data-id not found on parent.")
            except NoSuchElementException:
                print(
                    "[ID_EXTRACT PRE-CLICK] Strategy 2: Parent element not found using ./parent::*.")
            except StaleElementReferenceException:
                print(
                    "[ID_EXTRACT PRE-CLICK] Strategy 2: StaleElementReferenceException getting parent data-id.")
            except Exception as e_parent:
                print(f"[ID_EXTRACT PRE-CLICK] Strategy 2: Error: {e_parent}")

    except StaleElementReferenceException:
        print("[ID_EXTRACT PRE-CLICK] Strategy 1: StaleElementReferenceException getting data-id. Cannot proceed.")
        # If stale before we even click, we probably can't proceed reliably
        return None
    except Exception as e_direct:
        print(
            f"[ID_EXTRACT PRE-CLICK] Strategy 1: Error getting data-id: {e_direct}")
        # Allow proceeding to click even if ID extraction failed, URL fallback might work

    if not pre_click_id_extracted:
        print("[ID_EXTRACT PRE-CLICK] Failed to extract User ID before clicking. Will rely on post-click URL check if click succeeds.")

    # Imports needed for explicit waits
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    max_retries = 3
    clicked = False

    for attempt in range(max_retries):
        # --- IMPORTANT: Refresh element reference inside retry loop ---
        # This is crucial if the element went stale on a previous attempt
        current_element_reference = user_element
        # -------------------------------------------------------------
        try:
            print(
                f"Attempt {attempt + 1}/{max_retries}: Attempting to click the specific user element provided.")
            # Scroll into view just before clicking
            try:
                # Use JS scrollIntoView for better reliability
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", current_element_reference)
                time.sleep(0.3)  # Brief pause for scroll to settle
            except Exception as scroll_err:
                print(
                    f"Warning: Could not scroll element into view before click: {scroll_err}")

            # Wait for the specific element to be clickable before attempting the click
            # We need a way to wait for the *specific element reference*
            # EC.element_to_be_clickable expects a locator tuple (By, value)
            # Workaround: Check if the element is displayed and enabled as a proxy
            WebDriverWait(driver, 5).until(
                lambda d: current_element_reference.is_displayed(
                ) and current_element_reference.is_enabled()
            )
            print(
                f"Attempt {attempt + 1}: Element confirmed displayed and enabled.")

            # Use the refreshed reference for the click
            # Click the specific element passed in
            if click_element(current_element_reference):
                clicked = True
                print(
                    f"Attempt {attempt + 1}: Successfully clicked the specific user element.")
                break  # Exit retry loop on success
            else:
                print(
                    f"Attempt {attempt + 1}: click_element helper returned False for the specific element.")
                time.sleep(1)  # Small delay before retry

        except StaleElementReferenceException as e:
            print(
                f"Attempt {attempt + 1}: Element became stale during click attempt: {e}")
            # Element is stale, cannot click it. No point retrying the same reference.
            # We already tried to extract the ID before clicking.
            print("Aborting click attempts due to stale element.")
            return None  # Indicate failure to click
        except TimeoutException as e:  # Catch timeout from the explicit wait
            print(
                f"Attempt {attempt + 1}: Timeout waiting for element to be clickable/stable: {e}")
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1}: Retrying click...")
                time.sleep(1)  # Wait before retrying
            else:
                print(
                    f"Attempt {attempt + 1}: Max retries reached after timeout.")
        except Exception as e:
            # Catch other potential errors during the click process
            print(
                f"Attempt {attempt + 1}: An unexpected error occurred during click attempt: {type(e).__name__} - {e}")
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1}: Retrying click...")
                time.sleep(1)
            else:
                print(
                    f"Attempt {attempt + 1}: Max retries reached after unexpected error.")

    if not clicked:
        print("Failed to click user element after all attempts.")
        return None  # Click failed

    print("Successfully clicked user element. Waiting for potential navigation/update...")
    time.sleep(1.5)  # Slightly longer wait after click for URL/DOM to update

    # --- Final ID Check (Fallback if pre-click failed) ---
    if pre_click_id_extracted:
        print(
            f"[ID_EXTRACT POST-CLICK] Returning pre-click extracted ID: {user_id}")
        return user_id  # Return the ID we got before clicking
    else:
        # Fallback to URL check if ID wasn't extracted before click
        print(
            "[ID_EXTRACT POST-CLICK] Pre-click ID extraction failed. Falling back to URL check...")
        try:
            current_url = driver.current_url
            # Use a more general regex to capture IDs after various path segments
            match = re.search(
                r'(?:/chat/|/profile/|/messages/|/user/|user(?:id)?=|/u/|/p/)(\d+)', current_url, re.IGNORECASE)
            if match:
                url_user_id = match.group(1)
                print(
                    f"[ID_EXTRACT POST-CLICK] Extracted user ID from URL: {url_user_id}")
                return url_user_id
            else:
                print(
                    f"[ID_EXTRACT POST-CLICK] No user ID found in URL: {current_url}")
        except Exception as e:
            print(
                f"[ID_EXTRACT POST-CLICK] Error reading or parsing URL for ID: {e}")

        # If URL check also fails
        print(
            "[ID_EXTRACT POST-CLICK] Could not extract user ID using any method (pre-click or URL).")
        return None


# --- Message Sending/Handling Functions (Unchanged) ---

def count_messages(driver, incoming=True):
    """Counts incoming or outgoing messages."""
    xpath_key = "incoming_message" if incoming else "outgoing_message"
    xpath = XPATHS_INTERACTION.get("messaging", {}).get(xpath_key)
    if not xpath:
        print(f"Error: XPath for '{xpath_key}' not found in config.")
        return 0
    try:
        # Use find_elements which returns a list (empty if none found)
        elements = driver.find_elements(By.XPATH, xpath)
        # Check for staleness within the count? Less critical here.
        return len(elements)
    except StaleElementReferenceException:
        print(
            f"Stale element reference while counting {'incoming' if incoming else 'outgoing'} messages. Returning 0.")
        return 0
    except Exception as e:
        print(
            f"Error counting {'incoming' if incoming else 'outgoing'} messages: {e}")
        return 0


def find_message_input(driver):
    """Finds the message input field using multiple strategies."""
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
        element = find_element_with_wait(
            driver, By.XPATH, xpath, timeout=1)  # Quick check
        if element:
            # Add checks for visibility/enabled state?
            if element.is_displayed() and element.is_enabled():
                print(f"Found usable message input using XPath key: {key}")
                return element
            else:
                print(
                    f"Found message input using XPath key: {key}, but it's not displayed/enabled.")
    print("Could not find a usable message input field.")
    return None


def find_send_button(driver):
    """Finds the send button using multiple strategies."""
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
        element = find_element_with_wait(
            driver, By.XPATH, xpath, timeout=1)  # Quick check
        if element:
            # Add checks for visibility/enabled state
            if element.is_displayed() and element.is_enabled():
                print(f"Found usable send button using XPath key: {key}")
                return element
            else:
                print(
                    f"Found send button using XPath key: {key}, but it's not displayed/enabled.")
    print("Could not find a usable send button via XPath.")
    return None


def send_message(driver, message_text: str):
    """Types a message and attempts to send it."""
    # Imports needed for explicit waits within this function
    # from selenium.webdriver.support.ui import WebDriverWait # Removed as it's not directly used here anymore
    # EC is not actually used here, only WebDriverWait for element_to_be_clickable on the button

    print(
        f"Attempting to send message: '{message_text[:50]}...'")  # Log truncated message
    input_field = find_message_input(driver)
    if not input_field:
        print("Send message failed: Could not find input field.")
        return False

    # Clear field before sending keys? Sometimes needed.
    try:
        input_field.clear()
        time.sleep(0.1)
    except Exception as clear_err:
        print(f"Warning: Could not clear input field: {clear_err}")

    if not send_keys_to_element(input_field, message_text):
        print("Send message failed: send_keys_to_element returned False.")
        return False

    time.sleep(0.5)  # Small delay after typing

    # Try clicking send button first
    send_button = find_send_button(driver)
    # Use WebDriverWait for the button click as well
    try:
        # Wait for button to be clickable - EC.element_to_be_clickable requires a locator tuple,
        # but we have the element. We can wait for visibility/enabled instead, or trust click_element.
        # Let's simplify and rely on click_element's internal checks/waits if it has them,
        # or add a simple visibility wait if needed. Assuming click_element handles it for now.
        # If issues arise, we can add: WebDriverWait(driver, 5).until(lambda d: send_button and send_button.is_displayed() and send_button.is_enabled())
        # Check if button exists before clicking
        if send_button and click_element(send_button):
            print("Message sent via button click.")
            return True
        else:
            print("click_element returned False for send button.")
    except TimeoutException:
        print("Timeout waiting for send button to be clickable.")
    except AttributeError:  # If send_button is None
        print("Send button not found, cannot attempt click.")
    except Exception as btn_click_err:
        print(f"Error clicking send button: {btn_click_err}")

    # If button click fails or button not found, try pressing Enter in the input field
    print("Send button click failed or button not found/usable, trying Enter key in input field...")
    try:
        # Ensure input field is still valid before sending Enter
        if input_field.is_displayed() and input_field.is_enabled():
            if send_keys_to_element(input_field, Keys.ENTER):
                print("Message sent via Enter key.")
                return True
            else:
                print("send_keys_to_element returned False for Enter key.")
        else:
            print("Input field became non-interactable before sending Enter.")
    except StaleElementReferenceException:
        print("Input field became stale before sending Enter.")
    except Exception as enter_err:
        print(f"Error sending Enter key: {enter_err}")

    print("Failed to send message using button or Enter key.")
    return False


def handle_chat_cycle(driver, profile_id, stats_queue, assigned_city: Optional[str], usernames_list: List[str]):
    """
    Main loop for handling chat interactions for one browser instance.
    Sends stats back via the provided queue.

    Args:
        driver: The Selenium WebDriver instance.
        profile_id: The AdsPower profile ID for logging.
        stats_queue: The queue for reporting stats (e.g., link sent).
        assigned_city: The city assigned to this bot instance for registration.
        usernames_list: A list of usernames to attempt during registration.
    """
    local_sent_links_count = 0  # Track locally for logging if needed

    config = load_config()
    messages = load_messages()
    onlyfans_link = config.get("onlyfans_link", "")
    if not messages:
        print(f"[{profile_id}] No messages loaded. Cannot chat.")
        return

    # Replace placeholder in messages
    final_message_index = -1
    for i, msg in enumerate(messages):
        if "{onlyfans_link}" in msg:
            messages[i] = msg.replace("{onlyfans_link}", onlyfans_link)
            final_message_index = i
            break  # Assume only one link message

    if final_message_index == -1:
        print(
            f"[{profile_id}] Warning: No message contains the '{{onlyfans_link}}' placeholder.")
        final_message_index = len(messages) - 1  # Treat last message as final

    # Imports needed for explicit waits
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    # --- Main Interaction Loop ---
    cycle_count = 0
    interacted_user_ids_this_pass = set()  # Users interacted with since last reset
    no_new_user_streak = 0  # Track consecutive cycles where no new user is found

    while True:  # Loop indefinitely for this profile
        cycle_count += 1
        print(
            f"\n[{profile_id} Cycle: {cycle_count}] Starting interaction cycle...")

        current_user_id = None  # Reset for this cycle
        try:
            # --- Proactive Ad Check ---
            # (Keep existing ad check logic here)
            try:
                current_url = driver.current_url
                if "#google_vignette" in current_url:
                    print(
                        f"[{profile_id} Cycle: {cycle_count}] Detected ad URL fragment. Refreshing page...")
                    driver.refresh()
                    print(
                        f"[{profile_id} Cycle: {cycle_count}] Waiting for inbox button after ad refresh...")
                    WebDriverWait(driver, 60).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, XPATHS_INTERACTION["navigation"]["inbox_button"]))
                    )
                    print(
                        f"[{profile_id} Cycle: {cycle_count}] Page refreshed and inbox button found after ad. Attempting to click inbox...")
                    try:
                        inbox_button_element = driver.find_element(
                            By.XPATH, XPATHS_INTERACTION["navigation"]["inbox_button"])
                        if click_element(inbox_button_element):
                            print(
                                f"[{profile_id} Cycle: {cycle_count}] Clicked inbox button after ad refresh.")
                            time.sleep(1)
                        else:
                            print(
                                f"[{profile_id} Cycle: {cycle_count}] Failed to click inbox button after ad refresh. Will retry next cycle.")
                    except Exception as click_err:
                        print(
                            f"[{profile_id} Cycle: {cycle_count}] Error clicking inbox button after ad refresh: {click_err}")
                    continue  # Restart cycle after handling ad
            except Exception as ad_check_err:
                print(
                    f"[{profile_id} Cycle: {cycle_count}] Error during proactive ad check: {ad_check_err}")
            # --- End Proactive Ad Check ---

            # 1. Go to Inbox (ensure we are in the right view)
            if not go_to_inbox(driver):
                print(
                    f"[{profile_id} Cycle: {cycle_count}] Failed to navigate to inbox. Refreshing...")
                try:
                    driver.refresh()
                    print(
                        f"[{profile_id} Cycle: {cycle_count}] Waiting for inbox button after failed navigation refresh...")
                    WebDriverWait(driver, 60).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, XPATHS_INTERACTION["navigation"]["inbox_button"]))
                    )
                    print(
                        f"[{profile_id} Cycle: {cycle_count}] Page refreshed and inbox button found after failed navigation.")
                except Exception as refresh_err:
                    print(
                        f"[{profile_id} Cycle: {cycle_count}] Failed to refresh/find inbox after error: {refresh_err}. Stopping.")
                    break  # Exit loop if refresh fails badly
                continue  # Retry cycle

            # 2. Find a *new* male user element to interact with using the new function
            user_element = find_clickable_male_user(
                driver, interacted_user_ids_this_pass)

            if not user_element:
                no_new_user_streak += 1
                print(f"[{profile_id}] No *new* suitable user found in specified containers (Streak: {no_new_user_streak}). Resetting pass and waiting...")
                interacted_user_ids_this_pass.clear()  # Reset for the next pass
                # Implement increasing wait time based on streak?
                # e.g., 15, 20, 25... up to 60s
                wait_time = min(15 + (no_new_user_streak * 5), 60)
                print(
                    f"Waiting for {wait_time:.1f} seconds before next pass...")
                time.sleep(wait_time)
                continue  # Retry cycle, starting a new pass
            else:
                no_new_user_streak = 0  # Reset streak if a user was found

            # 3. Click user element and get ID using the updated function
            current_user_id = click_user_and_get_id(
                driver, user_element)  # Pass only the element

            if not current_user_id:
                print(
                    f"[{profile_id} Cycle: {cycle_count}] Failed to click or get ID for the selected user element. Trying next cycle.")
                # Element might be stale or unclickable, don't add to interacted set yet.
                # Go back to inbox view to be safe before next cycle
                go_to_inbox(driver)
                time.sleep(random.uniform(1, 3))  # Small pause before retry
                continue  # Retry cycle

            # --- Interaction Logic ---
            print(
                f"[{profile_id}] Successfully interacted with User ID: {current_user_id}")
            # Add this user to the set of interacted users *after* successful click/ID retrieval
            interacted_user_ids_this_pass.add(current_user_id)

            # 4. Determine message phase and state for this user
            user_state = user_tracker.get_user_state(current_user_id)

            if user_state is None:
                # Initialize state for a new user if not found in tracker
                user_tracker.update_user_state(current_user_id, {
                    "message_phase": 0,
                    "user_incoming_message_count_at_last_send": -1
                })
                # Retrieve the newly created state to work with
                user_state = user_tracker.get_user_state(current_user_id)
                print(
                    f"[{profile_id} Cycle: {cycle_count}] Initialized state for new User ID: {current_user_id}")

            # Extract current phase and last recorded incoming count from the user state
            current_phase = user_state.get("message_phase", 0)
            last_recorded_incoming = user_state.get(
                "user_incoming_message_count_at_last_send", -1)

            # LOGGING
            print(
                f"[{profile_id} Cycle: {cycle_count}] Retrieved state for User ID: {current_user_id} - Phase: {current_phase}, Last Incoming Count: {last_recorded_incoming}")

            if current_phase > final_message_index:
                print(
                    f"[{profile_id} Cycle: {cycle_count}] User {current_user_id} has already received the final message (Phase {current_phase}). Skipping.")  # LOGGING
                # No need to remove from state here, cleanup_old_users handles it periodically
                continue  # Find a new user

            # 5. Check if it's time to send the next message
            #    - Check for reply if needed
            #    - Send message
            #    - Update phase and state
            #    - Wait if final message

            # --- Check if reply is needed and received ---
            should_check_reply = 0 < current_phase <= (
                final_message_index - 3)  # Check reply for intermediate phases

            if should_check_reply:
                print(
                    f"[{profile_id}] Checking for reply from {current_user_id} (currently phase {current_phase})...")
                num_incoming_now = count_messages(driver, incoming=True)

                if num_incoming_now <= last_recorded_incoming:
                    print(f"[{profile_id}] No new incoming message detected from {current_user_id} since last send (current: {num_incoming_now}, last recorded: {last_recorded_incoming}). Skipping send for this cycle.")
                    # Go back to inbox implicitly by continuing the main loop
                    # Small delay before next cycle iteration
                    time.sleep(random.uniform(1, 3))
                    continue  # Skip sending to this user, find next user
                else:
                    print(
                        f"[{profile_id}] New incoming message detected ({num_incoming_now} > {last_recorded_incoming}). Proceeding to send phase {current_phase}.")

            # --- Send the message ---
            message_to_send = messages[current_phase]
            print(
                f"[{profile_id}] Sending phase {current_phase} message to {current_user_id}: '{message_to_send[:50]}...'")

            if send_message(driver, message_to_send):
                # --- Update State ---
                phase_just_sent = current_phase  # Store before incrementing
                new_phase = current_phase + 1  # LOGGING
                # LOGGING
                print(
                    f"[{profile_id} Cycle: {cycle_count}] Updating phase for User ID {current_user_id} from {phase_just_sent} to {new_phase}")

                # Record incoming count *after* sending, so next check compares against this
                num_incoming_after_send = count_messages(driver, incoming=True)
                # LOGGING
                print(f"[{profile_id} Cycle: {cycle_count}] Recording incoming count {num_incoming_after_send} for User ID {current_user_id} after sending.")

                # Update state using user_tracker
                user_tracker.update_user_state(current_user_id, {
                    "message_phase": new_phase,
                    "user_incoming_message_count_at_last_send": num_incoming_after_send
                })

                # --- Handle Link Sent ---
                if phase_just_sent == final_message_index:
                    local_sent_links_count += 1
                    print(
                        f"[{profile_id}] Final link sent to {current_user_id}! Total sent by this instance: {local_sent_links_count}")
                    try:
                        stats_queue.put(
                            {"type": "link_sent", "profile_id": profile_id})
                    except Exception as q_err:
                        print(
                            f"[{profile_id}] Error putting item in stats_queue: {q_err}")

                # --- Conditional Wait for Final Messages ---
                # Check if the phase *just sent* was one of the last three
                if phase_just_sent >= final_message_index - 2:
                    print(
                        f"[{profile_id}] Sent final phase message ({phase_just_sent}). Waiting 10 seconds...")
                    time.sleep(10)
                # else: # Optional: Add a smaller random delay for non-final messages?
                #     time.sleep(random.uniform(1, 3)) # Example small delay

            else:
                # Handle failed send
                print(
                    f"[{profile_id}] Failed to send message for phase {current_phase} to {current_user_id}.")
                time.sleep(5)
                continue  # Continue to next cycle attempt

            # The loop naturally continues, which will lead back to go_to_inbox()

        except Exception as e:  # Changed bare except to except Exception
            print(f"[{profile_id}] An error occurred in the chat cycle: {e}")
            # Basic error handling: Refresh page and try again
            # More specific handling needed for logout detection -> trigger registration
            # Check if registration elements are visible?
            is_logged_out = False
            try:
                # Quick check for a registration element
                if find_element_with_wait(driver, By.XPATH, "//input[@id='username']", timeout=2):
                    is_logged_out = True
            except Exception:  # Changed bare except to except Exception
                pass  # Ignore errors here, just checking for element

            if is_logged_out:
                print(
                    f"[{profile_id}] Detected logout. Attempting re-registration...")
                # Pass the assigned city and username list to the registration process
                if handle_registration_process(driver, assigned_city, usernames_list):
                    print(f"[{profile_id}] Re-registration successful.")
                    # Clear state for this profile? Maybe not needed if process restarts state.
                else:
                    print(
                        f"[{profile_id}] Re-registration failed. Stopping interaction for this profile.")
                    # Signal failure to concurrency manager?
                    break  # Exit the loop for this profile
            else:
                print(
                    f"[{profile_id} Cycle: {cycle_count}] Refreshing page due to error: {e}")
                # More specific handling needed for logout detection -> trigger registration
                try:
                    driver.refresh()
                    # Wait explicitly after refresh
                    print(
                        f"[{profile_id} Cycle: {cycle_count}] Waiting for inbox button after error refresh...")
                    WebDriverWait(driver, 60).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, XPATHS_INTERACTION["navigation"]["inbox_button"]))
                    )
                    print(
                        f"[{profile_id} Cycle: {cycle_count}] Page refreshed and inbox button found after error.")
                except Exception as refresh_err:
                    print(
                        f"[{profile_id} Cycle: {cycle_count}] Failed to refresh page after error: {refresh_err}. Stopping interaction.")
                    break  # Exit loop

            continue  # Continue to next cycle attempt
