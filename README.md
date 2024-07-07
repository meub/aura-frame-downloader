# Aura Frame Downloader

This is a simple script to bulk download all the photos from an Aura digital picture frame (auraframes.com). Aura provides no easy way to bulk download photos off of frames so I created this for use with Python 3. Aura stores all photos in the cloud so no physical access to the frame is necessary to download the photos.

### Setup

This script requires Python 3 and depends on the Python [requests](https://github.com/psf/requests) module. You'll need to have Python 3 installed and use `pip install requests` to install this module. You may have to run `pip3 install requests` and use `python3` to run the script if you have multiple Python versions installed on your system.

Before running this script you need to set up a configuration file that containss your Aura email, password, and the file_path and frame_id for each Aura frame you want to download from. This allows you to keep your Aura login credentials out of any repository you may have the script in and allows you to set up multiple frames to download.

The default file locations are as follows:
They can be overridded using the --config /path/to/config.ini command line option
--------------------------------------------------
Windows: %USERPROFILE%/etc/aura/credentials.ini
Linux  : $HOME/etc/aura/credentials.ini

Example file, found under etc/credentials.ini
---------------------------------------------------------------
# Credentials to log into api.auraframes.com
[login]
email = myemail2@gmail.com
password = mYpa$$w0rd-11

# Defined frames, One section per frams
[mine]
file_path = ./images
frame_id  = abf53be3-b73d-4de3-98cd-cfd289bd82df

[mom]
file_path = /images-moms-frame
frame_id  = b69ddd8d-bcad-483f-adf4-e15ff9a48c47

[nana]
file_path = ./images-sisters-frame
frame_id = cd3e8813-8fb6-434f-b709-e66deb3ea2a6

You can get the frame ID by doing the following:

 * Go to https://app.auraframes.com and log in
 * Cliek on the Frame name
 * Click on "View Photos" underneath the frame
 * Then grab the ID from the URL: `https://app.auraframes.com/frame/<FRAME ID HERE>`


### Usage

Run the script with:

    python download-aura-photos.py frame_name
    python download-aura-photos.py --config /Users/name/aura/config.ini frame_name

e.g.
    python download-aura-photos.py mine
    python download-aura-photos.py mom
    python download-aura-photos.py --config /alternate/pat/to/credentials.ini nana


Photos will be downloaded to the folder defined by the file_path in the requestion .ini file section. The Aura API will throttle the downloads so you may have to restart the script multiple times to fully download all of your photos. 
The good thing is that download progress is saved so photos that are already downloaded will be skipped when restarting the script. You can also adjust the `time.sleep(2)` to something longer if throttling becomes a problem.

The script creates the local picture file name using the following attributes from the 
item JSON data.
- 'taken_at' (a timestamp) 
- 'id' (a unique identifier in the Aura frame)
- 'file_name' (the extension only) 

Example file name: 2012-04-15-03-15-04.000_B9A0E367-FA8D-4157-A090-7EE33F603312.jpeg

Note: It's possible for the same picture file to be uploaded to an Aura
frame by different people.  This will result in each picture being downloaded
to a separate filename under images/.  If there are a lot of people updating
a frame, you may want to run a duplicate photo finder on the downloaded 
photos.
