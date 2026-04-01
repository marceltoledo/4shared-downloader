# 4shared Multi-Account Media Downloader

A Python script that recursively downloads media from public 4shared folder accounts. Give it a list of folder URLs and it handles everything — subfolders, pagination, history tracking, and smart skipping.

## What It Downloads

Supported file types: `.jpg` `.jpeg` `.png` `.gif` `.webp` `.mp4` `.mov` `.avi` `.mkv`

## Requirements

**Python 3.9 or higher** is required.

Install dependencies:
```bash
pip install playwright requests beautifulsoup4
playwright install chromium
```

## Setup

1. Download `4shared_downloader.py` and `myaccounts.txt` into the same folder
2. Open `myaccounts.txt` and add one 4shared folder URL per line, for example:
```
https://www.4shared.com/folder/xy-o4oZ4/_online.html
https://www.4shared.com/folder/4Pgyranu/Download.html
https://www.4shared.com/folder/goPSYinJ/BBM.html
https://www.4shared.com/folder/h22L5M24/Fotos_Cel_Nena.html
https://www.4shared.com/folder/msNO-Zcn/MCC.html
```
3. Run the script:
```bash
python 4shared_downloader.py
```

## How It Works

On launch the script shows an **account review screen** before downloading anything. For each account it shows how many files have been previously downloaded and asks if you want to run it. Type `y` to queue it, anything else to skip.

Downloads are saved to a `downloads/` folder inside the same directory as the script. Each account gets its own subfolder named by its unique folder ID.

## History & Skip System

Every successfully downloaded file is recorded in a history file (stored in `history_files/`). The skip logic is based on this history file, **not what is on disk** — so deleting downloaded files will not cause them to be re-downloaded on the next run. This is intentional.

New files added to a 4shared account since your last run will be picked up automatically on the next run. This is helpful to scan good accounts later, and pick up new files.

## Logs

A `download_log.txt` file is created in the same directory and records every skip, success, and failure with timestamps.

## Notes

- The script uses a headless Chromium browser (via Playwright) to crawl folder pages since 4shared uses JavaScript for content loading
- File downloads use plain HTTP requests which is significantly faster than keeping a browser open
- If an account fails after multiple retries it is logged and skipped — the script continues to the next account rather than crashing
- Page loads are retried up to 3 times with a delay before giving up

## Folder URL Format

Any of these formats work:
```
https://www.4shared.com/folder/F6YhfbPq/_online.html
https://www.4shared.com/folder/F6YhfbPq/FolderName.html
and others too..
```

## Support & Donations

If you find this tool useful and would like to support me, consider donating:

- **PayPal:** [https://www.paypal.me/RonaldsServices](https://www.paypal.me/RonaldsServices)
- **Bitcoin (BTC):** `bc1qpdnu3mcl96g8puru982ndq3kyft7f9srjnx3mt`

Your support is greatly appreciated!
```
