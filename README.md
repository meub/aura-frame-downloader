# Aura Frame Downloader

This is a script to bulk download photos from an Aura digital picture frame (auraframes.com). Aura provides no easy way to bulk download photos so I created this for use with Python. Aura stores all photos on their servers so no physical access to the frame is necessary to download them.

### Setup

This script requires Python 3 and depends on the Python [requests](https://github.com/psf/requests) module. Before running this script you need to set up a configuration file that contains your Aura email, password, and the file_path and frame_id for each Aura frame you want to download from. This allows you to keep your Aura login credentials out of the repository and allows you to set up multiple frames to download. The frame names in the config file don't need to match anything, it's just something you'll be able to reference when you run the command. However, the frame_id must match exactly.

### Getting your frame ID

You can get the frame ID by doing the following:

 * Go to https://app.auraframes.com and log in
 * Click on the Frame name
 * Click on "View Photos" underneath the frame
 * Then grab the ID from the URL: `https://app.auraframes.com/frame/<FRAME ID HERE>`


### Configuration File

The default configuration file locations are below. They can be overridded using the --config /path/to/config.ini command line option

 * Windows: %USERPROFILE%/etc/aura/credentials.ini
 * Linux and Mac  : $HOME/etc/aura/credentials.ini

An example file can found under etc/credentials.ini


#### Config file first section: credentials to log into api.auraframes.com

    [login]
    email = myemail2@gmail.com
    password = mYpa$$w0rd-11

#### Config file second section: defined frames, one section per frame

The frame names in the config file don't need match anything. They are just used so you can reference them when running the commands.

    [myframe]
    file_path = ./images
    frame_id  = abf53be3-b73d-4de3-98cd-cfd289bd82df

    [anotherframe]
    file_path = ./images-another-frame
    frame_id  = b69ddd8d-bcad-483f-adf4-e15ff9a48c47

    [alastframe]
    file_path = ./images-last-frame
    frame_id = cd3e8813-8fb6-434f-b709-e66deb3ea2a6



### Usage

    usage: download-aura-photos.py [-h] [--config CONFIG] [--debug] [--count] [--years] [frame]

    positional arguments:
      frame

    options:
      -h, --help       show this help message and exit
      --config CONFIG  configuration file
      --debug          debug log output
      --count          show count of photos then exit
      --=years         store pictures in a directory for the year in the
                        json 'taken_at' data. 

    # example commands
    python download-aura-photos.py myframe
    python download-aura-photos.py --config /alternate/path/to/credentials.ini myframe
    python download-aura-photos.py --count myframe
    python download-aura-photos.py --count --config /alternate/path/to/credentials.ini myframe
    python download-aura-photos.py --years myframe


Photos will be downloaded to the folder defined by the frame's file_path parameter in the configuration file. The Aura API will throttle the downloads so you may have to restart the script multiple times to fully download all of your photos. 

The good thing is that download progress is saved so photos that are already downloaded will be skipped when restarting the script. You can also adjust the `time.sleep(2)` to something longer if throttling becomes a problem.

The script creates the local image file name using the following attributes from the 
item JSON data.
 * 'taken_at' (a timestamp) 
 * 'id' (a unique identifier in the Aura frame)
 * 'file_name' (the extension only) 

Example filename: 2012-04-15-03-15-04.000_B9A0E367-FA8D-4157-A090-7EE33F603312.jpeg

When the --years command line argument is used, the script combines the frame's
file_path from the configuration and the year from the json data for the final output
directory name.  It then creates the directory if needed and saves the file there.
This improved performance when viewing files as icons in Windows Explorer by reducing
the number of files per directory.

Example.
    Using file_path = ./images-another-frame and the example filename above,
    the downloaded file will be stored in :
    ./images-another-frame/2012/2012-04-15-03-15-04.000_B9A0E367-FA8D-4157-A090-7EE33F603312.jpeg 

Note: It's possible for the same picture file to be uploaded to an Aura frame by different people.  This will result in each picture being downloaded to a separate filename under images/.  If there are a lot of people updating a frame, you may want to run a duplicate photo finder on the downloaded photos.

### Development notes

The Makefile is set up to install a python virtual environment with the requests and prospector modules installed under the venv folder. 

    $  make install


To use the virtual environment as the default python, tell your IDE to use venv/bin/python
for the project, or activate it manually.

    $ . venv/bin/activate

Then run the script.

    $ python ./download-aura-photos.py [--count] [--config path] [--years] frame_name