import multiprocessing
import time
import signal
import os
from typing import List, Dict  # Removed Optional as it's unused here
from collections import deque  # For limiting log history
from .bot_runner import run_bot_instance  # Import the moved function

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
        # Queue for processes to send log messages
        self.log_queue = multiprocessing.Queue()
        # Change processes to a dictionary: profile_id -> Process object
        self.processes: Dict[str, multiprocessing.Process] = {}
        # Keep this list to track intended profiles
        self.active_profile_ids: List[str] = []
        self.total_links_sent = 0
        self.conversations_started = 0  # NEW: Counter for started conversations
        # Store logs per bot_id, using deque for efficient limited history
        self.bot_logs: Dict[str, deque] = {}
        self.max_log_entries_per_bot = 150  # Configurable limit for logs per bot
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
        self.processes = {}  # Initialize as empty dictionary
        self.is_running = True

        for i, profile_id in enumerate(self.active_profile_ids):
            # Assign a city using modulo to cycle through the list
            assigned_city = city_options[i % len(
                city_options)] if city_options else None
            print(f"Assigning city '{assigned_city}' to profile {profile_id}")

            try:
                # Pass profile ID, stats queue, LOG QUEUE, assigned city, AND usernames list to the target function
                process = multiprocessing.Process(
                    target=run_bot_instance,
                    args=(profile_id, self.stats_queue, self.log_queue,  # Added log_queue
                          assigned_city, usernames_list),
                    daemon=True
                )
                # Store process in dictionary with profile_id as key
                self.processes[profile_id] = process
                # Initialize log storage for this bot
                if profile_id not in self.bot_logs:
                    self.bot_logs[profile_id] = deque(
                        maxlen=self.max_log_entries_per_bot)
                process.start()
                print(
                    f"Started process PID {process.pid} for profile {profile_id}")
                # --- ADD DELAY ---
                print("Waiting 2 seconds before starting next bot...")
                time.sleep(2)  # Add a delay to avoid API rate limits
                # --- END DELAY ---
            except Exception as e:
                print(f"Error starting process for profile {profile_id}: {e}")
                # Should we stop others if one fails? For now, continue.

        # Remove the debug print
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
        # Keep active_profile_ids until processes are confirmed stopped? Or clear here? Clear here for now.
        self.active_profile_ids = []

        # Iterate over the process objects stored in the dictionary values
        # Use list() to avoid RuntimeError during iteration
        for profile_id, process in list(self.processes.items()):
            if process.is_alive():
                try:
                    # Log which profile ID is being stopped
                    print(
                        f"Terminating process PID {process.pid} for profile {profile_id}...")
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
                    print(
                        f"Error stopping process PID {process.pid} (Profile: {profile_id}): {e}")
            # Remove from dictionary after attempting stop
            del self.processes[profile_id]

        # Clear the dictionary after attempting to stop all
        self.processes = {}
        print("All bot processes stopped.")
        # Process any remaining items from both queues
        self._process_queues()
        return True

    def stop_bot(self, profile_id: str) -> bool:
        """Stops a single running bot process by its profile ID."""
        if profile_id not in self.processes:
            print(
                f"Warning: Cannot stop bot. Profile ID {profile_id} not found in running processes.")
            return False

        process = self.processes[profile_id]
        print(
            f"Attempting to stop bot for profile {profile_id} (PID: {process.pid})...")

        if process.is_alive():
            try:
                print(
                    f"Terminating process PID {process.pid} for profile {profile_id}...")
                os.kill(process.pid, signal.SIGTERM)
                process.join(timeout=5)

                if process.is_alive():
                    print(
                        f"Process PID {process.pid} did not terminate gracefully, sending SIGKILL.")
                    os.kill(process.pid, signal.SIGKILL)
                    process.join(timeout=2)

            except ProcessLookupError:
                print(
                    f"Process PID {process.pid} (Profile: {profile_id}) already terminated.")
            except Exception as e:
                print(
                    f"Error stopping process PID {process.pid} (Profile: {profile_id}): {e}")
                # Keep the process in the dict if stopping failed? Or remove anyway? Remove for now.
        else:
            print(f"Process for profile {profile_id} was not alive.")

        # Remove the process from the dictionary regardless of termination success/failure
        del self.processes[profile_id]
        print(f"Removed profile {profile_id} from active process tracking.")

        # Also remove from the list of IDs we intended to start, if present
        if profile_id in self.active_profile_ids:
            self.active_profile_ids.remove(profile_id)
            print(
                f"Removed profile {profile_id} from active_profile_ids list.")

        # Update overall running state if no processes are left
        if not any(p.is_alive() for p in self.processes.values()):
            self.is_running = False
            print("All bot processes seem to have stopped. Setting is_running to False.")

        # Process queues after potential stop
        self._process_queues()
        return True

    def _process_queues(self):
        """Processes items from both the stats and log queues."""
        # Process Stats Queue
        while not self.stats_queue.empty():
            try:
                stat = self.stats_queue.get_nowait()
                if isinstance(stat, dict):
                    stat_type = stat.get("type")
                    # Assuming stats include profile_id
                    profile_id = stat.get("profile_id")
                    if stat_type == "link_sent":
                        self.total_links_sent += 1
                        print(
                            f"Concurrency Manager: Received link_sent event for {profile_id}. Total links: {self.total_links_sent}")
                    # Add handling for other stat types if needed (e.g., conversations started)
                    elif stat_type == "conversation_started":
                        self.conversations_started += 1  # Increment the new counter
                        print(
                            f"Concurrency Manager: Received conversation_started event for {profile_id}. Total started: {self.conversations_started}")

            except multiprocessing.queues.Empty:
                break
            except Exception as e:
                print(f"Error processing item from stats queue: {e}")

        # Process Log Queue
        while not self.log_queue.empty():
            try:
                log_entry = self.log_queue.get_nowait()
                # Expecting format: {'bot_id': profile_id, 'message': 'log message'}
                if isinstance(log_entry, dict) and 'bot_id' in log_entry and 'message' in log_entry:
                    bot_id = log_entry['bot_id']
                    message = log_entry['message']
                    timestamp = time.strftime(
                        "%Y-%m-%d %H:%M:%S")  # Add timestamp
                    formatted_log = f"[{timestamp}] {message}"

                    if bot_id not in self.bot_logs:
                        # Initialize deque if process started but manager hasn't seen logs yet
                        self.bot_logs[bot_id] = deque(
                            maxlen=self.max_log_entries_per_bot)
                    self.bot_logs[bot_id].append(formatted_log)
                    # Optional: print to manager console as well?
                    # print(f"[LOG - {bot_id}] {message}")
                else:
                    print(
                        f"Warning: Received malformed log entry: {log_entry}")
            except multiprocessing.queues.Empty:
                break
            except Exception as e:
                print(f"Error processing item from log queue: {e}")

    def get_stats(self) -> Dict:
        """Processes the queues and returns current statistics."""
        self._process_queues()  # Process both queues before returning stats
        # Get active bot IDs from the logs dictionary keys as well, in case a process died
        # but we still have its logs. Combine with active_profile_ids for a complete list.
        logged_bot_ids = list(self.bot_logs.keys())
        # Combine lists, create a set to remove duplicates, convert back to list,
        # filter out None values, then sort.
        combined_ids = list(set(self.active_profile_ids + logged_bot_ids))
        filtered_ids = [
            bot_id for bot_id in combined_ids if bot_id is not None]
        all_known_bot_ids = sorted(filtered_ids)

        # Check which processes in our dictionary are actually alive
        active_count = 0
        for process in self.processes.values():
            if process.is_alive():
                active_count += 1

        return {
            "is_running": self.is_running,
            "active_processes": active_count,  # Use the count of live processes from dict
            # Still based on the list of IDs we tried to start
            "target_processes": len(self.active_profile_ids),
            # IDs we tried to start
            "active_profile_ids": self.active_profile_ids,
            # IDs we have stats or logs for
            "all_known_bot_ids": all_known_bot_ids,
            "total_links_sent": self.total_links_sent,
            "conversations_started": self.conversations_started  # Add the new stat
        }

    def get_logs(self, bot_id: str) -> List[str]:
        """Returns the stored log messages for a specific bot ID."""
        self._process_queues()  # Ensure logs are up-to-date
        if bot_id in self.bot_logs:
            return list(self.bot_logs[bot_id])  # Return as a list
        else:
            return ["No logs found for this bot ID."]


# --- run_bot_instance function has been moved to app/concurrency/bot_runner.py ---


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
