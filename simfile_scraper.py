import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser as dateparser
import zipfile
from io import BytesIO
import shutil
import logging

BASE_URL = 'https://zenius-i-vanisher.com/v5.2/'
URL = BASE_URL + 'viewsimfile.php?simfileid=65828'
BASE_SIMFILES_DIR = 'simfiles/'
SIMFILES_DIR = BASE_SIMFILES_DIR + 'DDR WORLD/'

logging.basicConfig(level=logging.INFO, format='%(message)s')

def get_last_updated(soup):
    import re
    from datetime import datetime
    for td in soup.find_all('td', string='Last Activity'):
        next_td = td.find_next_sibling('td')
        if next_td:
            match = re.search(r'\(([^)]+)\)', next_td.get_text())
            if match:
                date_str = match.group(1)
                return datetime.strptime(date_str, "%Y-%m-%d %I:%M%p")
    raise Exception("Couldn't find last updated date on the page.")

def get_zip_link(soup):
    for a in soup.find_all('a', href=True):
        if a.text.strip() == 'ZIP':
            link = a['href']
            link = BASE_URL + link
            return link
    raise Exception("Couldn't find zip download link.")

def clean_simfiles_dir():
    if os.path.exists(SIMFILES_DIR):
        shutil.rmtree(SIMFILES_DIR)
    os.makedirs(SIMFILES_DIR)

def extract_zip_to_dir(zip_bytes, target_dir):
    with zipfile.ZipFile(BytesIO(zip_bytes)) as z:
        z.extractall(target_dir)

def find_sm_file(directory, simfile_name):
    # Look for {simfile_name}.sm in each subdirectory of directory
    target = directory + f"{simfile_name}/{simfile_name}.sm"
    if os.path.exists(target):
        return target

def main():
    try:
        resp = requests.get(URL, timeout=30)
        resp.raise_for_status()
        html = resp.text
        soup = BeautifulSoup(html, 'html.parser')
        last_updated_dt = get_last_updated(soup)
        zip_link = get_zip_link(soup)
    except Exception as e:
        logging.error(f"Error scraping page: {e}")
        return

    sm_file = find_sm_file(SIMFILES_DIR, 'ARACHNE')
    if sm_file:
        local_mtime = datetime.fromtimestamp(os.path.getmtime(sm_file))
        logging.info(f"Local SM file last modified: {local_mtime}")
        logging.info(f"Remote SM file last updated: {last_updated_dt}")
        if local_mtime >= last_updated_dt:
            logging.info("Local SM file is up to date.")
            return
        else:
            logging.info("Local SM file is outdated. Downloading new zip...")
            clean_simfiles_dir()
    else:
        logging.info("No local SM file found. Downloading zip...")
        clean_simfiles_dir()

    try:
        zip_resp = requests.get(zip_link, timeout=30)
        zip_resp.raise_for_status()
        extract_zip_to_dir(zip_resp.content, SIMFILES_DIR)
        logging.info(f"Downloaded and extracted to {SIMFILES_DIR}/")
    except Exception as e:
        logging.error(f"Error downloading or extracting zip: {e}")

if __name__ == "__main__":
    main()
