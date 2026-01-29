"""Configuration file parsing for Aura Frame Downloader."""

import configparser
import os
from typing import Dict, List, Optional

from .exceptions import ConfigError


def load_config(config_path: str) -> configparser.ConfigParser:
    """
    Load and validate a configuration file.

    Args:
        config_path: Path to the credentials.ini file

    Returns:
        ConfigParser object with loaded configuration

    Raises:
        ConfigError: If the config file doesn't exist or can't be parsed
    """
    if not os.path.exists(config_path):
        raise ConfigError(f"Config file '{config_path}' not found")

    config = configparser.ConfigParser()
    try:
        config.read(config_path)
    except Exception as e:
        raise ConfigError(f"Error parsing config file '{config_path}': {e}")

    if not config.has_section('login'):
        raise ConfigError(f"No [login] section found in file '{config_path}'")

    return config


def get_login_credentials(config: configparser.ConfigParser) -> Dict[str, str]:
    """
    Extract login credentials from config.

    Args:
        config: ConfigParser object with loaded configuration

    Returns:
        Dictionary with 'email' and 'password' keys

    Raises:
        ConfigError: If credentials are missing
    """
    try:
        return {
            'email': config['login']['email'],
            'password': config['login']['password']
        }
    except KeyError as e:
        raise ConfigError(f"Missing login credential: {e}")


def get_frame_config(config: configparser.ConfigParser, frame_name: str) -> Dict[str, str]:
    """
    Get configuration for a specific frame.

    Args:
        config: ConfigParser object with loaded configuration
        frame_name: Name of the frame section in the config

    Returns:
        Dictionary with 'frame_id' and 'file_path' keys

    Raises:
        ConfigError: If frame section doesn't exist or is missing required fields
    """
    if not config.has_section(frame_name):
        raise ConfigError(f"No frame [{frame_name}] found in config file")

    try:
        return {
            'frame_id': config[frame_name]['frame_id'],
            'file_path': config[frame_name]['file_path']
        }
    except KeyError as e:
        raise ConfigError(f"Missing frame configuration: {e}")


def get_frame_names(config: configparser.ConfigParser) -> List[str]:
    """
    Get list of frame names from config (all sections except 'login').

    Args:
        config: ConfigParser object with loaded configuration

    Returns:
        List of frame section names
    """
    return [section for section in config.sections() if section != 'login']


def get_default_config_path() -> str:
    """
    Get the default configuration file path.

    Returns:
        Default path to credentials.ini
    """
    return os.path.join(os.path.expanduser('~'), 'etc', 'aura', 'credentials.ini')
