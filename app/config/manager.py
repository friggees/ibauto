import json
import os

# Define default paths relative to this file's location
CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
MESSAGES_FILE = os.path.join(CONFIG_DIR, 'messages.txt')

DEFAULT_CONFIG = {
    "adspower_api_key": "YOUR_API_KEY_HERE",
    "adspower_api_host": "http://local.adspower.net:50325",
    "onlyfans_link": "YOUR_ONLYFANS_LINK_HERE",
    "max_concurrent_browsers": 5,
    "usernames": [],  # List of usernames to try
    "registration_defaults": {
        "age": "18",
        "country": "US",
        # Example cities
        "city_options": ["New York", "Los Angeles", "Chicago"]
    }
}


def ensure_data_dir_exists():
    """Ensures the data directory exists."""
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)


def load_config():
    """Loads configuration from config.json. Creates default if not found."""
    ensure_data_dir_exists()
    if not os.path.exists(CONFIG_FILE):
        print(f"Config file not found at {CONFIG_FILE}. Creating default.")
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # Ensure all default keys exist, add if missing
            updated = False
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
                    updated = True
                # Ensure nested defaults exist (e.g., registration_defaults)
                elif isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if sub_key not in config[key]:
                            config[key][sub_key] = sub_value
                            updated = True
            if updated:
                print("Config file updated with default values for missing keys.")
                save_config(config)  # Save the updated config
            return config
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {CONFIG_FILE}. Using default config.")
        return DEFAULT_CONFIG
    except Exception as e:
        print(
            f"Error loading config file {CONFIG_FILE}: {e}. Using default config.")
        return DEFAULT_CONFIG


def save_config(config_data):
    """Saves configuration data to config.json."""
    ensure_data_dir_exists()
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        print(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving config file {CONFIG_FILE}: {e}")


def load_messages():
    """Loads message phases from messages.txt. Returns a list of strings."""
    ensure_data_dir_exists()
    if not os.path.exists(MESSAGES_FILE):
        print(f"Messages file not found at {MESSAGES_FILE}. Creating default.")
        default_messages = [
            "Hi there!",
            "How are you?",
            "Looking for fun?",
            "Check this out: {onlyfans_link}"  # Placeholder for the link
        ]
        try:
            with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
                for msg in default_messages:
                    f.write(msg + '\n')
            print(f"Default messages file created at {MESSAGES_FILE}")
            return default_messages
        except Exception as e:
            print(f"Error creating default messages file {MESSAGES_FILE}: {e}")
            return []

    try:
        with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
            # Read lines, strip whitespace, and filter out empty lines
            messages = [line.strip() for line in f if line.strip()]
        return messages
    except Exception as e:
        print(f"Error loading messages file {MESSAGES_FILE}: {e}")
        return []


if __name__ == '__main__':
    # Example usage when running this script directly
    print("Loading configuration...")
    config = load_config()
    print("Config loaded:", json.dumps(config, indent=2))

    print("\nLoading messages...")
    messages = load_messages()
    print("Messages loaded:", messages)

    # Example of saving updated config
    # config['max_concurrent_browsers'] = 10
    # save_config(config)
