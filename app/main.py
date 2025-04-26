import sys
import os
import multiprocessing

# --- Adjust path to find project root for module imports ---
# This assumes main.py is in the 'app' directory
current_dir = os.path.dirname(os.path.abspath(__file__))
# Go up one level from 'app' to the project root
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"[Main Process {os.getpid()}] Added {project_root} to sys.path")
# --- End path modification ---

try:
    # Import the Flask app instance from dashboard.routes
    # Now that project root is in sys.path, 'app' is a package
    from app.dashboard.routes import app, concurrency_manager
except ImportError as e:
    print(f"Error importing Flask app or ConcurrencyManager: {e}")
    print("Ensure app/dashboard/routes.py and app/concurrency/manager.py exist and are importable.")
    sys.exit(1)


def run_server():
    """Runs the Flask development server."""
    # TODO: Consider using a production-ready server like Waitress or Gunicorn
    # For Waitress:
    # from waitress import serve
    # serve(app, host='0.0.0.0', port=5000)
    # For Gunicorn (Linux/macOS):
    # gunicorn -w 4 -b 0.0.0.0:5000 app.main:app
    print("Starting Flask development server on http://127.0.0.1:5000")
    print("Access the dashboard in your browser.")
    print("NOTE: Ensure AdsPower client is running for bot operations.")
    # Setting debug=False is generally recommended for anything beyond basic testing,
    # especially when using multiprocessing. Debug mode can cause issues with child processes.
    # Use host='0.0.0.0' to make it accessible on your local network.
    app.run(host='0.0.0.0', port=5000, debug=False)


if __name__ == '__main__':
    # Required for multiprocessing to work correctly on Windows when freezing apps
    multiprocessing.freeze_support()

    # Ensure the ConcurrencyManager is accessible (it's initialized in routes.py)
    if concurrency_manager is None:
        print("Error: ConcurrencyManager was not initialized correctly.")
        sys.exit(1)

    # Add a handler to stop bots gracefully on exit?
    import atexit
    import signal

    def cleanup():
        print("Shutting down Flask server...")
        if concurrency_manager.is_running:
            print("Stopping running bots...")
            concurrency_manager.stop_bots()

    # Register cleanup function to run on exit
    atexit.register(cleanup)
    # Handle SIGTERM (e.g., from Docker or systemctl stop)
    signal.signal(signal.SIGTERM, lambda signum,
                  frame: cleanup() or sys.exit(0))
    # Handle SIGINT (Ctrl+C)
    # signal.signal(signal.SIGINT, lambda signum, frame: cleanup() or sys.exit(0))
    # Note: Flask's dev server handles Ctrl+C, so overriding SIGINT might interfere.
    # Rely on atexit for Ctrl+C with the dev server.

    run_server()
