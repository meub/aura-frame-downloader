# Aura Frame Downloader

This is a simple script to bulk download all the photos from an Aura digital picture frame (auraframes.com). Aura provides no easy way to bulk download photos off of frames so I created this for use with Python 3. Aura stores all photos in the cloud so no physical access to the frame is necessary to download the photos.

### Setup

This script requires Python 3 and depends on the Python [requests](https://github.com/psf/requests) module. You'll need to have Python 3 installed and use `pip install requests` to install this module. You may have to run `pip3 install requests` and use `python3` to run the script if you have multiple Python versions installed on your system.

Before running this script you need to set your Aura email, password, and frame ID as the `email`, `password` and `frame_id` variables in the script. You can get your frame ID by doing the following:

 * Go to https://app.auraframes.com and log in
 * Click on "View Photos" underneath your frame
 * Then grab the ID from the URL: `https://app.auraframes.com/frame/<FRAME ID HERE>`


### Usage

Run the script with:

    python download-aura-photos.py


Photos will be downloaded to the `images/` folder.
