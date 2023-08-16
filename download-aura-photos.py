import json
import os
import os.path
import re
import shutil
import time

import requests

# Put Aura email/password here
email = "youremail@email.com"
password = "yourpassword"
file_path = "images"

# You can get your frame id by going to app.auraframes.com
# Log in there and click on "View Photos" underneath your frame
# Then grab the ID from the URL: https://app.auraframes.com/frame/<FRAME ID HERE>
frame_id = "your-frame-id"

# Main download function
def download_photos_from_aura(email, password, frame_id):
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
        print("Login Error: Check your credentials")
        return 0

    print("Login Success")

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
        print("Download Error: No images returned from this Aura Frame. API responded with:")
        print(json_data)
        return 0

    photo_count = len(json_data["assets"])
    print(f"Found {photo_count} photos, starting download process")
    print("Downloading pictures to filename <taken_at>_<file_name>")

    for item in json_data["assets"]:

        try:
            # construct the raw photo URL
            url = f"https://imgproxy.pushd.com/{item['user_id']}/{item['file_name']}"

            # make a unique new_filename using
            #  item['taken_at'] + item['id'] + item['file_name']'s extension
            new_filename = item['taken_at'] + "_" + item['id'] + os.path.splitext(item['file_name'])[1]
            file_to_write = os.path.join(file_path, new_filename)

            # Bump the counter and print the new_filename out to track progress
            counter += 1

            # check if file exists and skip it if so
            if os.path.isfile(file_to_write):
                print(f"{counter}: Skipping {new_filename}, already downloaded")
                skipped += 1
                continue

            # Get the photo from the url
            print(f"{counter}: Downloading {new_filename}")
            response = requests.get(url, stream=True)

            # write to a file
            with open(file_to_write, 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file)
            del response

            # wait a bit to avoid throttling
            time.sleep(2)

        except KeyboardInterrupt:
            print('Exiting from keyboard interrupt')
            break

        except Exception as e:
            print(f"Errored out on item: {counter}, probably due to throttling")
            print(str(e))
            time.sleep(10)

    return counter - skipped

# Check the output directory exists in case the script is moved
# or the file_path is changed.
if not os.path.isdir(file_path):
    print(f"Error: output directory {file_path} does not exist")
else:
    total = download_photos_from_aura(email, password, frame_id)
    print(f"Downloaded {total} photos")
