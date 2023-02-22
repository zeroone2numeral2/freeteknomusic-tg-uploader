This is a stupidly easy and bare-bones script I made to upload the content of some public FTP directories to a Telegram channel

I used [Open Directory Downloader](https://github.com/KoalaBear84/OpenDirectoryDownloader) to pull the download urls, and `wget -x -i` to actually download them (see Open Directory Downloader's readme)

Before running the entry point script (`main.py`), make sure to copy `config.example.toml` to `config.toml` and edit the config values according to your needs. 
Explanation of what each option does is inside the file. Feel free to open an issue if some of them are unclear

This script uses [Pyrogram](https://docs.pyrogram.org/) instead of the standard http API for bots because we might need to upload files larger than 50 mb. 
Files larger than 2 gb will have to be uploaded manually  
If an error is raised during the execution, or a file larger than 2 gb is found, the script will exit

In the root directory there are some scripts I used to fix some errors and extract some information:
- `script_fix_text_messages.py` was used to edit some text messages that were sent with the wrong format
- `script_metadata_to_json.py` generates a json file with all the audio files' metadata of interest
- `script_total_time.py` is used to calculate the total length in days/hours of the tracks in the source directory
