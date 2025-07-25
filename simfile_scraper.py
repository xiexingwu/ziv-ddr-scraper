import os
from os.path import exists
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import zipfile
from io import BytesIO
import logging
import re

BASE_URL = 'https://zenius-i-vanisher.com/v5.2/'
WORLD_URL = BASE_URL + 'viewsimfilecategory.php?categoryid=1709'
BASE_SIMFILES_DIR = 'simfiles/'
SIMFILES_DIR = BASE_SIMFILES_DIR + 'DDR WORLD/'

logging.basicConfig(level=logging.INFO, format='%(message)s')
## PARSING FUNCTIONS
def get_simfile_name(soup):
    top_nav = soup.find('div', id='top-nav')
    if top_nav:
        links = top_nav.find_all('a')
        if links:
            return links[-1].text.strip()
    raise Exception("Couldn't find simfile name in the page.")

def get_last_updated(soup):
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

def get_simfile_ids_from_category(soup):
    simfile_ids = []
    for a in soup.find_all('a', href=True):
        match = re.match(r'^viewsimfile\.php\?simfileid=(\d+)', a['href'])
        if match:
            simfile_ids.append(match.group(1))
    return simfile_ids

## FILE HANDLING FUNCTIONS
def extract_zip_to_dir(zip_bytes, target_dir):
    with zipfile.ZipFile(BytesIO(zip_bytes)) as z:
        z.extractall(target_dir)

def mkdir_simfiles_dir():
    os.makedirs(SIMFILES_DIR, exist_ok=True)

def find_sm_file(directory, simfile_name):
    # Look for {simfile_name}.sm in each subdirectory of directory
    target = directory + f"{simfile_name}/{simfile_name}.sm"
    if os.path.exists(target):
        return target

def scrape_simfile(simfile_id):
    # Fetch simfile page
    simfile_url = BASE_URL + f'viewsimfile.php?simfileid={simfile_id}'
    try:
        resp = requests.get(simfile_url, timeout=30)
        resp.raise_for_status()
        html = resp.text
        soup = BeautifulSoup(html, 'html.parser')
        logging.info(f"[{simfile_id}] Souped {simfile_url}")
    except Exception as e:
        logging.error(f"Error scraping page: {e}")
        return

    # Parse simfile page
    simfile_name = get_simfile_name(soup)
    logging.info(f"[{simfile_id} - {simfile_name}] extracted name")
    last_updated_dt = get_last_updated(soup)
    logging.info(f"[{simfile_id} - {simfile_name}] extracted last update: {last_updated_dt}")
    zip_link = get_zip_link(soup)
    logging.info(f"[{simfile_id} - {simfile_name}] extracted zip link: {zip_link}")

    # Compare with local
    sm_file = find_sm_file(SIMFILES_DIR, simfile_name)
    if sm_file:
        local_mtime = datetime.fromtimestamp(os.path.getmtime(sm_file))
        logging.info(f"[{simfile_id} - {simfile_name}] Local SM file last modified: {local_mtime}")
        logging.info(f"[{simfile_id} - {simfile_name}] Remote SM file last updated: {last_updated_dt}")
        if local_mtime >= last_updated_dt:
            logging.info(f"[{simfile_id} - {simfile_name}] Local SM file is up to date.")
            return
        else:
            logging.info(f"[{simfile_id} - {simfile_name}] Local SM file is outdated. Downloading new zip...")
    else:
        logging.info(f"[{simfile_id} - {simfile_name}] No local SM file found. Downloading zip...")

    # download and unzip
    mkdir_simfiles_dir()
    try:
        zip_resp = requests.get(zip_link, timeout=30)
        zip_resp.raise_for_status()
        extract_zip_to_dir(zip_resp.content, SIMFILES_DIR)
        logging.info(f"[{simfile_id} - {simfile_name}] Downloaded and extracted to {SIMFILES_DIR}")
    except Exception as e:
        logging.error(f"[{simfile_id} - {simfile_name}] Error downloading or extracting zip: {e}")

def scrape_category(version_url):
    resp = requests.get(version_url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    simfile_ids = get_simfile_ids_from_category(soup)
    for simfile_id in simfile_ids:
        scrape_simfile(simfile_id)

if __name__ == "__main__":
    scrape_category(WORLD_URL)
