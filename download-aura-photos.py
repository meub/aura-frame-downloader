import requests
import json
import shutil
import time
import os
import os.path
import re

# Put Aura email/password here
email = "youremail@email.com"
password =  "yourpassword"
file_path = "images/"

# You can get your frame id by going to app.auraframes.com
# Log in there and click on "View Photos" underneath your frame
# Then grab the ID from the URL: https://app.auraframes.com/frame/<FRAME ID HERE>
frame_id = "your-frame-id"

# Main download function
def download_photos_from_aura( email, password, frame_id):

  # define URLs and payload format
  login_url = "https://api.pushd.com/v5/login.json"
  frame_url = "https://api.pushd.com/v5/frames/" + frame_id + "/assets.json?limit=1000&side_load_users=false"
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
    print("Login Error")
    return

  print("Login Success")

  # get json and update user and auth token headers for next request
  json_data = r.json()
  s.headers.update({'X-User-Id': json_data['result']['current_user']['id'],  'X-Token-Auth':  json_data['result']['current_user']['auth_token'] })

  # make request to get all phtos (frame assets)
  r = s.get(frame_url)
  json_data = json.loads(r.text)
  counter = 1

  for item in json_data["assets"]:

    try:
      # construct new filename
      new_filename = re.sub(':|T','-', item["taken_at"]).replace('Z','')
      if  item["file_name"].endswith(".jpeg"):
        new_filename = new_filename + ".jpeg"
      elif  item["file_name"].endswith(".jpg"):
        new_filename = new_filename + ".jpg"
      elif  item["file_name"].endswith(".png"):
        new_filename = new_filename + ".png"

      # check if file exists and skip it if so
      if os.path.isfile(file_path + new_filename):
        print(counter, "Skipping!", new_filename, "already downloaded" )
        counter = counter + 1
        continue

      # construct raw photo URL and get it
      url = "https://imgproxy.pushd.com/" + item["user_id"] + "/" + item["file_name"]
      print(counter,": Downloading ",item["file_name"])
      response = requests.get(url, stream=True)

      # write to a file
      with open(file_path + new_filename, 'wb') as out_file:
          shutil.copyfileobj(response.raw, out_file)
      del response
      counter = counter + 1

      # wait a bit to avoid throttling
      time.sleep(2)

    except KeyboardInterrupt:
      print('Exiting from keyboard interrupt')
      break

    except Exception as e:
      print("Errored out on item:", counter, "(probably due to throttling)")
      print(str(e))
      time.sleep(10)

  return counter

total = download_photos_from_aura( email, password, frame_id)
print("Downloaded", total, "photos")