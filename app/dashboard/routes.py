from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import os
import sys
# import threading # Removed unused import

# --- Adjust path to import from parent directories ---
# This assumes routes.py is in app/dashboard/
PACKAGE_PARENT = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(PACKAGE_PARENT)

try:
    from config.manager import load_config, save_config, load_messages, DEFAULT_CONFIG
    from concurrency.manager import ConcurrencyManager
    from data import user_tracker  # Import user_tracker
except ImportError as e:
    print(f"Error importing necessary modules in routes.py: {e}")
    print("Ensure the script is run with the project root in PYTHONPATH or use a proper package structure.")
    # Define dummy classes/functions if import fails, so Flask can at least load
    def load_config(): return DEFAULT_CONFIG
    def save_config(data): print("Dummy save_config called")
    def load_messages(): return ["Dummy message 1", "Dummy message 2"]
    DEFAULT_CONFIG = {}

    class ConcurrencyManager:
        # Removed semicolons from dummy class definition
        def __init__(self):
            self.total_links_sent = 0
            self.is_running = False

        def start_bots(self, ids):
            print("Dummy start_bots called")
            self.is_running = True
            return True

        def stop_bots(self):
            print("Dummy stop_bots called")
            self.is_running = False
            return True
        def get_stats(self): return {"is_running": self.is_running, "active_processes": 0,
                                     "target_processes": 0, "active_profile_ids": [], "total_links_sent": self.total_links_sent}

    # Define dummy user_tracker functions
    class user_tracker:
        @staticmethod
        def reset_user_tracker():
            print("Dummy reset_user_tracker called")

# --- Flask App Setup ---
# Determine template and static folder paths relative to this file
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
static_dir = os.path.join(os.path.dirname(__file__), 'static')

# Check if directories exist, create if not (optional, Flask might handle this)
if not os.path.exists(template_dir):
    os.makedirs(template_dir)
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = os.urandom(24)  # Needed for flashing messages

# --- Global Concurrency Manager Instance ---
# Initialize it once when the Flask app starts
concurrency_manager = ConcurrencyManager()

# --- Routes ---


@app.route('/')
def index():
    """Renders the main dashboard page."""
    config = load_config()
    # Join messages with newline for textarea
    messages = "\n".join(load_messages())
    stats = concurrency_manager.get_stats()
    return render_template('index.html', config=config, messages=messages, stats=stats)


@app.route('/save_config', methods=['POST'])
def save_config_route():
    """Handles saving the configuration from the form."""
    try:
        current_config = load_config()

        # Update simple fields
        current_config['adspower_api_key'] = request.form.get(
            'adspower_api_key', current_config.get('adspower_api_key'))
        current_config['adspower_api_host'] = request.form.get(
            'adspower_api_host', current_config.get('adspower_api_host'))
        current_config['onlyfans_link'] = request.form.get(
            'onlyfans_link', current_config.get('onlyfans_link'))
        try:
            current_config['max_concurrent_browsers'] = int(request.form.get(
                'max_concurrent_browsers', current_config.get('max_concurrent_browsers')))
        except ValueError:
            flash(
                "Invalid number for Max Concurrent Browsers. Keeping previous value.", "warning")

        # Handle the headless checkbox (present in form means True, absent means False)
        current_config['run_headless'] = 'run_headless' in request.form

        # Update registration defaults (nested dict)
        if 'registration_defaults' not in current_config:
            current_config['registration_defaults'] = {}
        current_config['registration_defaults']['age'] = request.form.get(
            'reg_age', current_config.get('registration_defaults', {}).get('age'))
        current_config['registration_defaults']['country'] = request.form.get(
            'reg_country', current_config.get('registration_defaults', {}).get('country'))
        # Handle city options - split by newline, strip whitespace, remove empty
        city_text = request.form.get(
            'reg_city_options', '')  # Read from the textarea
        current_config['registration_defaults']['city_options'] = [
            city.strip() for city in city_text.splitlines() if city.strip()]

        # --- Handle Profile IDs ---
        profile_ids_text = request.form.get(
            'adspower_profile_ids', '')  # Read from the new textarea
        current_config['adspower_profile_ids'] = [
            pid.strip() for pid in profile_ids_text.splitlines() if pid.strip()]

        # --- Handle Usernames ---
        usernames_text = request.form.get(
            'usernames', '')  # Read from the new textarea
        current_config['usernames'] = [
            uname.strip() for uname in usernames_text.splitlines() if uname.strip()]

        # --- Save main config.json ---
        save_config(current_config)

        # --- Save messages.txt ---
        messages_text = request.form.get('messages', '')
        messages_list = [line.strip()
                         for line in messages_text.splitlines() if line.strip()]
        messages_file_path = os.path.join(load_config().get(
            "CONFIG_DIR", "data"), 'messages.txt')  # Get path dynamically if possible
        if not messages_file_path:  # Fallback path
            messages_file_path = os.path.join(
                PACKAGE_PARENT, '..', 'data', 'messages.txt')

        try:
            # Ensure data directory exists (config manager might do this, but double check)
            data_dir = os.path.dirname(messages_file_path)
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
            with open(messages_file_path, 'w', encoding='utf-8') as f:
                for msg in messages_list:
                    f.write(msg + '\n')
            flash("Configuration and messages saved successfully!", "success")
        except Exception as e:
            flash(
                f"Configuration saved, but failed to save messages.txt: {e}", "error")

    except Exception as e:
        flash(f"Error saving configuration: {e}", "error")

    return redirect(url_for('index'))


@app.route('/start_bots', methods=['POST'])
def start_bots_route():
    """Starts the bot processes."""
    if concurrency_manager.is_running:
        flash("Bots are already running.", "warning")
    else:
        # TODO: Get profile IDs to run. How should the user specify these?
        # Option 1: Hardcode in config.json (e.g., "adspower_profile_ids": ["id1", "id2"])
        # Option 2: Input field on the dashboard?
        # Option 3: Automatically detect running/available profiles via AdsPower API? (More complex)

        # Read profile IDs directly from the updated config
        config = load_config()
        # Use the key we just saved
        profile_ids = config.get("adspower_profile_ids", [])
        if not profile_ids:
            flash(
                "No AdsPower Profile IDs entered in the configuration. Cannot start bots.", "error")
        # Pass the list of IDs
        elif concurrency_manager.start_bots(profile_ids):
            flash("Bots started successfully!", "success")
        else:
            flash("Failed to start bots.", "error")

    return redirect(url_for('index'))


@app.route('/stop_bots', methods=['POST'])
def stop_bots_route():
    """Stops the bot processes."""
    if not concurrency_manager.is_running:
        flash("Bots are not running.", "warning")
    elif concurrency_manager.stop_bots():
        flash("Bots stopped successfully!", "success")
    else:
        # Might still be stopped forcefully
        flash("Failed to stop bots cleanly.", "error")
    return redirect(url_for('index'))


@app.route('/get_stats')
def get_stats_route():
    """API endpoint to fetch current stats for AJAX updates."""
    stats = concurrency_manager.get_stats()
    return jsonify(stats)


@app.route('/logs/<bot_id>')
def get_logs_route(bot_id):
    """API endpoint to fetch logs for a specific bot ID."""
    if not concurrency_manager:
        return jsonify({"error": "Concurrency manager not initialized"}), 500
    try:
        logs = concurrency_manager.get_logs(bot_id)
        # Ensure logs are returned as a list of strings, even if empty or error message
        if not isinstance(logs, list):
            # Convert to list if it's not already (e.g., error string)
            logs = [str(logs)]
        return jsonify({"logs": logs})
    except Exception as e:
        # Log the error server-side for debugging
        print(f"Error fetching logs for bot_id {bot_id}: {e}")
        # Return a generic error to the client
        return jsonify({"error": f"Failed to retrieve logs for bot {bot_id}"}), 500


@app.route('/stop_bot/<profile_id>', methods=['POST'])
def stop_single_bot_route(profile_id):
    """Stops a single bot process by its profile ID."""
    if not concurrency_manager:
        flash("Concurrency manager not initialized.", "error")
    elif concurrency_manager.stop_bot(profile_id):
        flash(f"Attempted to stop bot {profile_id}.", "success")
    else:
        flash(
            f"Failed to stop bot {profile_id} (it might not have been running).", "warning")
    return redirect(url_for('index'))


@app.route('/reset_tracker', methods=['POST'])
def reset_tracker_route():
    """Handles resetting the user tracker data."""
    try:
        user_tracker.reset_user_tracker()
        flash("User tracker data has been reset.", "success")
    except Exception as e:
        flash(f"Error resetting user tracker data: {e}", "error")
    return redirect(url_for('index'))


# --- Main execution ---
# This part is usually in a separate run.py or main.py file
# def run_server():
#     # Consider using Waitress or Gunicorn for production instead of Flask dev server
#     print("Starting Flask development server...")
#     app.run(debug=True, host='0.0.0.0', port=5000) # Accessible on local network
#
# if __name__ == '__main__':
#     run_server()
