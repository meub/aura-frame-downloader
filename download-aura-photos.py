#!/usr/bin/env python3
"""Aura Frame Downloader - CLI Entry Point."""

import argparse
import logging
import os
import sys

from aura.config import get_default_config_path, get_frame_config, get_login_credentials, load_config
from aura.core import download_photos_from_aura
from aura.exceptions import AuraError, ConfigError, DownloadCancelledError, LoginError, NoAssetsError

LOGGER = logging.getLogger(__name__)


def parse_command_line():
    """
    Parse the command line options.

    Returns:
        The parsed command line args
    """
    parser = argparse.ArgumentParser(
        description="Download photos from an Aura digital picture frame"
    )
    parser.add_argument(
        "--config",
        help="configuration file",
        default=get_default_config_path(),
        required=False,
    )
    parser.add_argument(
        "--debug",
        help="debug log output",
        action="store_true",
        default=False,
        required=False,
    )
    parser.add_argument(
        "--years",
        help="save pictures folder by year",
        action="store_true",
        default=False,
        required=False,
    )
    parser.add_argument(
        "--count",
        help="show count of photos then exit",
        action="store_true",
        default=False,
        required=False,
    )
    parser.add_argument('frame', nargs='?')
    args = parser.parse_args()
    return args


def setup_logger(log_debug=False):
    """
    Set up default logging options.

    Args:
        log_debug: True sets logging.DEBUG, False sets logging.INFO
    """
    logging_level = logging.DEBUG if log_debug else logging.INFO
    logging.basicConfig(
        stream=sys.stdout,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        datefmt="%H:%M:%S",
        level=logging_level,
    )
    LOGGER.debug("Debug logging enabled.")


def app():
    """Main CLI application entry point."""
    args = parse_command_line()
    setup_logger(args.debug)

    # Validate arguments
    if not args.frame:
        LOGGER.error("No frame name supplied on the command line")
        sys.exit(1)

    try:
        # Load configuration
        LOGGER.info("Using credentials file '%s'", args.config)
        config = load_config(args.config)

        # Get credentials and frame config
        credentials = get_login_credentials(config)
        frame_config = get_frame_config(config, args.frame)

        email = credentials['email']
        password = credentials['password']
        frame_id = frame_config['frame_id']
        file_path = frame_config['file_path']

    except ConfigError as e:
        LOGGER.error(str(e))
        sys.exit(1)

    # Run the download
    try:
        downloaded, skipped, total = download_photos_from_aura(
            email=email,
            password=password,
            frame_id=frame_id,
            file_path=file_path,
            organize_by_year=args.years,
            count_only=args.count,
        )

        if args.count:
            LOGGER.info("Total photos in frame: %d", total)
        else:
            LOGGER.info("Downloaded %d photos (%d skipped)", downloaded, skipped)

    except LoginError as e:
        LOGGER.error(str(e))
        sys.exit(1)

    except NoAssetsError as e:
        LOGGER.error(str(e))
        sys.exit(0)

    except DownloadCancelledError:
        LOGGER.info("Download cancelled")
        sys.exit(0)

    except AuraError as e:
        LOGGER.error(str(e))
        sys.exit(1)


if __name__ == '__main__':
    app()
