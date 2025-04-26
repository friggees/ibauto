import json
import os
import time

# Path to store user IDs and state
# Assuming this file is located in app/data/
USER_TRACKER_PATH = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "user_ids.json")


def load_tracked_users():
    """Load the dictionary of tracked user states from the JSON file."""
    if os.path.exists(USER_TRACKER_PATH):
        try:
            with open(USER_TRACKER_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            print(
                f"Error loading user tracker data from {USER_TRACKER_PATH}: {e}")
            # Return empty data if file is corrupt or read fails
            return {}
    else:
        # Return empty data if file does not exist
        return {}


def save_tracked_users(data):
    """Save the dictionary of tracked user states to the JSON file."""
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(USER_TRACKER_PATH), exist_ok=True)
        with open(USER_TRACKER_PATH, "w") as f:
            json.dump(data, f, indent=4)
        # print(f"User tracker data saved to {USER_TRACKER_PATH}") # Optional: Add logging
    except Exception as e:
        print(f"Error saving user tracker data to {USER_TRACKER_PATH}: {e}")


def get_user_state(user_id):
    """
    Retrieve the state for a specific user.
    Returns a dictionary with state or None if user is not tracked.
    """
    data = load_tracked_users()
    return data.get(str(user_id))  # Ensure user_id is treated as string key


def update_user_state(user_id, state_updates):
    """
    Update the state for a user and save the file.
    Adds/updates 'last_interaction' timestamp.
    state_updates should be a dictionary of key-value pairs to update.
    """
    data = load_tracked_users()
    user_id_str = str(user_id)  # Ensure user_id is treated as string key

    if user_id_str not in data:
        data[user_id_str] = {
            "first_contact": time.time(),
            "message_phase": 0,  # Start at phase 0 for new users
            "user_incoming_message_count_at_last_send": -1  # Initialize incoming count
        }
        print(f"Initialized state for new user ID: {user_id_str}")

    # Apply updates
    data[user_id_str].update(state_updates)
    # Always update last interaction time on any state update
    data[user_id_str]['last_interaction'] = time.time()

    save_tracked_users(data)
    # print(f"Updated state for user ID: {user_id_str} with updates: {state_updates}") # Optional: Add logging


def cleanup_old_users(timeout_seconds=1800):  # Default to 30 minutes
    """
    Remove users from the tracker whose last interaction is older than timeout_seconds.
    """
    data = load_tracked_users()
    current_time = time.time()
    initial_count = len(data)

    # Create a new dictionary with only recent users
    cleaned_data = {
        user_id: state for user_id, state in data.items()
        if 'last_interaction' in state and (current_time - state['last_interaction']) < timeout_seconds
    }

    removed_count = initial_count - len(cleaned_data)

    if removed_count > 0:
        print(
            f"Cleaning up {removed_count} old user(s) from tracker (inactive for > {timeout_seconds}s)")
        save_tracked_users(cleaned_data)
    # else: # Optional: Add logging if no users were cleaned
        # print("No old users to clean up from tracker.")

    return removed_count


def reset_user_tracker():
    """
    Reset the user tracker by clearing the user_ids.json file.
    """
    try:
        save_tracked_users({})  # Save an empty dictionary to clear the file
        print(f"User tracker data in {USER_TRACKER_PATH} has been reset.")
    except Exception as e:
        print(f"Error resetting user tracker data: {e}")
