import argparse
import configparser
import json
import os
import os.path
import shutil
import time
import sys
import requests
import logging

LOGGER = logging.getLogger(__name__)

def parse_command_line():
    """
    Parse the command line options
    :return: the parsed command line args
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        help="configuration file",
        default=os.path.join(os.path.expanduser('~'),'etc','aura','credentials.ini'),
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
    Sets up default logging options
    :param log_debug: True sets logging.DEBUG, False sets logging.INFO
    :return:
    """
    logging_level = logging.DEBUG if log_debug else logging.INFO
    logging.basicConfig(
        stream=sys.stdout,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        datefmt="%H:%M:%S",
        level=logging_level,
    )

    LOGGER.debug("Debug logging enabled.")


# Main download function
def download_photos_from_aura(email, password, frame_id, file_path, args):
    # define URLs and payload format
    login_url = "https://api.pushd.com/v5/login.json"
    frame_url = f"https://api.pushd.com/v5/frames/{frame_id}/assets.json?side_load_users=false"
    login_payload = {
        "identifier_for_vendor": "does-not-matter",
        "client_device_id": "does-not-matter",
        "app_identifier": "com.pushd.Framelord",
        "locale": "en",
        "user": {
            "email": email,
            "password": password
        }
    }

    # make login request with credentials
    s = requests.Session()
    r = s.post(login_url, json=login_payload)

    if r.status_code != 200:
        LOGGER.error("Login Error: Check your credentials")
        sys.exit(1)

    LOGGER.info("Login Success")

    # get json and update user and auth token headers for next request
    json_data = r.json()
    s.headers.update({'X-User-Id': json_data['result']['current_user']['id'],
                      'X-Token-Auth': json_data['result']['current_user']['auth_token']})

    # make request to get all phtos (frame assets)
    r = s.get(frame_url)
    json_data = json.loads(r.text)
    counter = 0
    skipped = 0

    # check to make sure the frame assets array exists
    if "assets" not in json_data:
        LOGGER.error("Download Error: No images returned from this Aura Frame. API responded with:")
        LOGGER.error(json_data)
        sys.exit(0)

    photo_count = len(json_data["assets"])
    LOGGER.info("Found %s photos.", photo_count)
    if args.count: sys.exit()

    LOGGER.info("Starting download process")

    for item in json_data["assets"]:

        try:
            # construct the raw photo URL
            url = f"https://imgproxy.pushd.com/{item['user_id']}/{item['file_name']}"
            # make a unique new_filename using
            #  item['taken_at'] + item['id'] + item['file_name']'s extension
            # But clean the timestamp to be Windows-friendly
            clean_time = item['taken_at'].replace(':', '-')
            new_filename = clean_time + "_" + item['id'] + os.path.splitext(item['file_name'])[1]

            if args.years:
                # download picture to file_path/year/picture, 
                # creating file_path/year if necessary
                year_dir = os.path.join(file_path,clean_time[:4])
                if not os.path.isdir(year_dir):
                    LOGGER.debug("Creating new year directory: %s", year_dir)
                    os.makedirs(year_dir)
                file_to_write = os.path.join(year_dir, new_filename)
            else:
                # default to download picture to file_path/picture
                file_to_write = os.path.join(file_path, new_filename)

            # Bump the counter and print the new_filename out to track progress
            counter += 1

            # check if file exists and skip it if so
            if os.path.isfile(file_to_write):
                LOGGER.info("%i: Skipping %s, already downloaded", counter, new_filename)
                skipped += 1
                continue

            # Get the photo from the url
            LOGGER.info("%i: Downloading %s", counter, new_filename)
            response = requests.get(url, stream=True, timeout=90)

            # write to a file
            with open(file_to_write, 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file)
            del response

            # wait a bit to avoid throttling
            time.sleep(2)

        except KeyboardInterrupt:
            LOGGER.info('Exiting from keyboard interrupt')
            break

        except Exception as e:
            LOGGER.error("Item: %i failed to download, probably due to throttling", counter)
            LOGGER.error(str(e))
            time.sleep(10)

    return counter - skipped

def app():
    # parse the command line args
    # set up logging
    # check the args before continuing
    args = parse_command_line()
    setup_logger(args.debug)

    aok = True
    if not os.path.exists(args.config):
        LOGGER.error("Config file '%s' not found", args.config)
        aok = False

    if not args.frame:
        LOGGER.error("No frame name supplied on the command line")
        aok = False

    if not aok:
        sys.exit(1)

    try :
        # Read the frame and login credentials from outside the repo
        LOGGER.info("Using credentials file '%s'", args.config)
        config = configparser.ConfigParser()
        config.read(args.config)

        if not config.has_section('login'):
            LOGGER.error("No [login] section found in file '%s'.", args.config)
            sys.exit(1)

        if not config.has_section(args.frame):
            LOGGER.error("No frame [%s] found in file '%s'.", args.frame, args.config)
            sys.exit(1)
                
        email = config['login']['email']
        password = config['login']['password']
        frame_id = config[args.frame]['frame_id']
        file_path = config[args.frame]['file_path']

    except Exception:
        LOGGER.error("Error pasring config file '%s'.", args.config)
        sys.exit(1)

    # Check the output directory exists in case the script is moved
    # or the file_path is changed.
    if not os.path.isdir(file_path):
        LOGGER.info("Creating new images directory: %s", file_path)
        os.makedirs(file_path)

    total = download_photos_from_aura(email, password, frame_id, file_path, args)
    LOGGER.info("Downloaded %i photos", total)


if __name__ == '__main__':
    app()
