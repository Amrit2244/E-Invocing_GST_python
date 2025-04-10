# config_manager.py

import os
import configparser
from utils import get_current_time_utc

def load_config():
    """Load configuration from config.ini file."""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    
    # Default values
    default_config = {
        'TALLY': {
            'Port': '9000',
            'Mode': 'Production'
        },
        'USER': {
            'Login': 'Amrit2244',
            'LastSync': get_current_time_utc()
        }
    }
    
    # Load existing config or create new with defaults
    if os.path.exists(config_path):
        config.read(config_path)
    else:
        config.update(default_config)
        save_config(config)
        
    return config

def save_config(config):
    """Save configuration to config.ini file."""
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    with open(config_path, 'w') as configfile:
        config.write(configfile)
    print("Settings (Port, Mode) saved to config.ini")

def get_current_user():
    """Get current user's login."""
    config = load_config()
    return config.get('USER', 'Login', fallback='Amrit2244')

def update_last_sync():
    """Update last sync time in config."""
    config = load_config()
    if 'USER' not in config:
        config.add_section('USER')
    config['USER']['LastSync'] = get_current_time_utc()
    save_config(config)