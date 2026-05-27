# YTMusic-ListenBrainz-Importer
Python script to import historical YouTube Music data to ListenBrainz.

I have taken *heavy* inspiration from this Gist made by Fuddl: https://gist.github.com/fuddl/e17aa687df6ac1c7cbee5650ccfbc889

## Prerequisites
1. Python 3.x installed
   ##### Must have the lxml python packages installed:
     ```
     pip install lxml
     ```
3. An active ListenBrainz account
4. Your YouTube watch history file from Google takeout in html format.

## Instructions
### Step 1: Download your YouTube History
- Visit the Google Takeout website https://takeout.google.com/, ensuring you're logged into the account you want data from
- From the list, deselect all options besides the "YouTube and YouTube Music" option
- Click "All YouTube data included" button (may need to wait a second for it to appear), deselecting all options besides 'history'
- Once ready, download your takeout data which contains a `watch-history.html` file

### Step 2: Prepare your environment:
1. Download the `ytmusic-listenbrainz-importer.py` file
2. Place the `watch-history.html` file in the same directory as the python file (alternatively, specify the file path in the `file_path` variable near the top of the script)
3. Enter your ListenBrainz User token in the `listenbrainz_token` variable within `ytmusic-listenbrainz-importer.py`

### Step 3: Run the Script
Open a terminal or command prompt and navigate to the directory that contains the takout data and python script. Run the script with the following command:
```
python3 ytmusic-listenbrainz-importer.py
```
The script will output to the terminal:

- The total number of entires in the history file
- The number of parsed YouTube Music entries
- The number of *SKIPPED* entries (entries that couldn't be parsed, e.g. deleted from YouTube, copyright claimed, etc.)
- The progress of submitted history

### Step 4: Verification
After running the script, log into your ListenBrainz account to verify that your watch history was successfully imported. You can view any missed items in `skipped.log`, which appears in the same directory as the script, if any failed.
The script also creates a file named `parsed_entries.json`, which details all the songs sent to ListenBrainz.
