# config_manager.py (Updated to use .env)

import configparser
import keyring
import os
from dotenv import load_dotenv # Import the library

# --- Load .env file ---
# Call this early, before accessing environment variables
# It loads variables from .env into os.environ
# It doesn't override existing environment variables by default.
dotenv_path = os.path.join(os.path.dirname(__file__), '.env') # Assume .env is in the same dir or project root
if os.path.exists(dotenv_path):
    print(f"Loading environment variables from: {dotenv_path}")
    load_dotenv(dotenv_path=dotenv_path, verbose=True)
else:
    print("'.env' file not found. Relying on config.ini and keyring.")


CONFIG_FILE = 'config.ini'
SERVICE_NAME = 'TallyEInvoiceAppIRP' # Keyring service name

# IRP URLs (remain the same)
IRP_SANDBOX_URL = "https://einv-apisandbox.nic.in"
IRP_PRODUCTION_URL = "https://einvoice1.gst.gov.in"

def load_config():
    """
    Loads configuration, prioritizing .env variables for specific keys,
    then falling back to config.ini, and finally using defaults.
    """
    config = configparser.ConfigParser()

    # Define the default structure and values (these are the ultimate fallbacks)
    default_config = {
        'TALLY': {
            'Port': '9000'
            },
        'IRP_API': {
            'Mode': 'SANDBOX',
            'AuthPath': '/ewaybillapi/v1.04/auth',
            'GeneratePath': '/ewaybillapi/v1.04/invoice',
            'CancelPath': '/ewaybillapi/v1.04/invoice/cancel',
            'GetIrnDetailsPath': '/ewaybillapi/v1.04/invoice/irn',
            'GetGstinDetailsPath': '/ewaybillapi/v1.04/master/gstin',
            'UserGstin': '' # Default is empty
        },
        'APP': {
            'DefaultFromDateOffset': '7'
        }
    }

    # --- Read config.ini ---
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    else:
        # If config.ini doesn't exist, start with defaults
         print(f"Config file '{CONFIG_FILE}' not found. Using defaults.")
         config.read_dict(default_config)
         # No need to save yet, will happen after potentially overriding with env vars

    # --- Override specific config values with .env variables if they exist ---
    config_changed_by_env = False

    # Tally Port (Example of overriding a non-secret)
    env_tally_port = os.getenv('TALLY_PORT')
    if env_tally_port:
        if not config.has_section('TALLY'): config.add_section('TALLY')
        if config.get('TALLY', 'Port', fallback=None) != env_tally_port:
            print(f"Overriding Tally Port from .env: {env_tally_port}")
            config.set('TALLY', 'Port', env_tally_port)
            config_changed_by_env = True

    # IRP Mode
    env_irp_mode = os.getenv('IRP_MODE')
    if env_irp_mode and env_irp_mode.upper() in ['SANDBOX', 'PRODUCTION']:
        if not config.has_section('IRP_API'): config.add_section('IRP_API')
        if config.get('IRP_API', 'Mode', fallback=None) != env_irp_mode.upper():
            print(f"Overriding IRP Mode from .env: {env_irp_mode.upper()}")
            config.set('IRP_API', 'Mode', env_irp_mode.upper())
            config_changed_by_env = True

    # User GSTIN
    env_user_gstin = os.getenv('USER_GSTIN')
    if env_user_gstin:
         if not config.has_section('IRP_API'): config.add_section('IRP_API')
         if config.get('IRP_API', 'UserGstin', fallback=None) != env_user_gstin:
            print(f"Overriding User GSTIN from .env: {'*' * (len(env_user_gstin)-4)}{env_user_gstin[-4:]}") # Mask slightly
            config.set('IRP_API', 'UserGstin', env_user_gstin)
            config_changed_by_env = True

    # --- Ensure structure and apply defaults for missing items (AFTER reading ini and .env overrides) ---
    config_changed_by_defaults = False
    for section, default_keys in default_config.items():
        if not config.has_section(section):
            print(f"Adding missing section [{section}] with defaults.")
            config[section] = default_keys
            config_changed_by_defaults = True
        else:
            for key, default_value in default_keys.items():
                if not config.has_option(section, key):
                    print(f"Adding missing key '{key}' = '{default_value}' to section [{section}].")
                    config.set(section, key, default_value)
                    config_changed_by_defaults = True

    # --- Save config.ini ONLY if it was missing or structure changed ---
    # We don't save changes purely from .env overrides into config.ini
    if not os.path.exists(CONFIG_FILE) or config_changed_by_defaults:
        print(f"Saving configuration file '{CONFIG_FILE}'...")
        save_config(config)

    # The returned config object reflects the final merged state (.env > config.ini > defaults)
    return config

def save_config(config):
    """Saves the current configuration object to config.ini."""
    try:
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
    except IOError as e:
        print(f"Error saving configuration file '{CONFIG_FILE}': {e}")

def get_api_credentials():
    """
    Retrieves IRP API Username and Password.
    Priority:
    1. Environment Variables (from .env file or system env).
    2. OS Keyring.
    Returns (username, password) tuple. Returns (None, None) if not found anywhere.
    """
    # 1. Try Environment Variables first
    env_username = os.getenv('IRP_API_USERNAME')
    env_password = os.getenv('IRP_API_PASSWORD')

    if env_username is not None and env_password is not None:
        # print("Using API credentials from environment variables (.env).") # Optional: logging source
        return env_username, env_password

    # 2. If not found in env, try Keyring
    # print("API credentials not found in environment. Trying keyring...") # Optional: logging source
    try:
        keyring_username = keyring.get_password(SERVICE_NAME, "api_username")
        keyring_password = keyring.get_password(SERVICE_NAME, "api_password")
        if keyring_username is not None and keyring_password is not None:
            # print("Using API credentials from keyring.") # Optional: logging source
            return keyring_username, keyring_password
    except Exception as e:
        print(f"Error retrieving credentials from keyring: {e}")
        # Fall through if keyring fails

    # 3. Not found anywhere
    print("API credentials not found in .env or keyring.")
    return None, None


def set_api_credentials(username, password):
    """
    Stores IRP API Username and Password securely using the OS keyring.
    This function DOES NOT write to the .env file.
    Use this if you want the GUI 'Settings' to save to keyring as a fallback
    or alternative to using a .env file.
    Returns True on success, False on failure.
    """
    if not username:
        print("Error: API Username cannot be empty when setting credentials in keyring.")
        return False

    try:
        print(f"Storing credentials for user '{username}' in OS Keyring...")
        keyring.set_password(SERVICE_NAME, "api_username", username)
        keyring.set_password(SERVICE_NAME, "api_password", str(password) if password is not None else "")
        print(f"Credentials for user '{username}' stored successfully in Keyring.")
        return True
    except Exception as e:
        print(f"Error saving credentials using keyring: {e}")
        return False

# --- Example Usage / Standalone Test ---
if __name__ == "__main__":
    print("--- Testing config_manager.py with .env support ---")

    # Ensure .env is loaded if it exists
    # load_dotenv() is called at the top level

    # 1. Load config (merges .env > config.ini > defaults)
    print("\n[Loading Configuration]")
    cfg = load_config()
    if cfg:
        print("Effective configuration loaded successfully:")
        # Print values reflecting the merged config
        print(f"  Tally Port: {cfg.get('TALLY', 'Port', fallback='Not Set')}")
        print(f"  IRP Mode: {cfg.get('IRP_API', 'Mode', fallback='Not Set')}")
        print(f"  User GSTIN: {cfg.get('IRP_API', 'UserGstin', fallback='Not Set')}")
        print(f"  Auth Path: {cfg.get('IRP_API', 'AuthPath', fallback='Not Set')}")
    else:
        print("Failed to load configuration.")

    # 2. Test Credential Retrieval (Prioritizes .env)
    print("\n[Testing Credential Retrieval (Priority: .env > Keyring)]")
    retrieved_user, retrieved_pass = get_api_credentials()
    if retrieved_user:
        source = ".env/Environment" if os.getenv('IRP_API_USERNAME') else "Keyring"
        print(f"  Retrieved Username: {retrieved_user} (Source: {source})")
        print(f"  Password retrieved: {'Yes' if retrieved_pass is not None else 'No (or empty)'}")
    else:
        print("  Credentials not found in .env or keyring.")


    # 3. Test Setting Credentials (Writes ONLY to Keyring)
    # print("\n[Testing Credential Storage (Writes ONLY to Keyring)]")
    # test_user_keyring = "keyring_user_example"
    # test_pass_keyring = "keyring_password_123"
    # print(f"Attempting to set credentials for user '{test_user_keyring}' ONLY in Keyring...")
    # if set_api_credentials(test_user_keyring, test_pass_keyring):
    #      print("Credentials set successfully in Keyring.")
    #      # Verify by getting again - it should still prefer .env if set there
    #      # but if .env wasn't set, it would now find these keyring ones.
    # else:
    #      print("Failed to set credentials in Keyring.")

    print("\n--- Test Complete ---")