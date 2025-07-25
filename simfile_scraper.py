import math
import os
from os.path import exists
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import zipfile
from io import BytesIO
import logging
import re

BASE_URL = 'https://zenius-i-vanisher.com/v5.2/'
WORLD_URL = BASE_URL + 'viewsimfilecategory.php?categoryid=1709'
BASE_SIMFILES_DIR = 'simfiles/'
SIMFILES_DIR = BASE_SIMFILES_DIR + 'DDR WORLD/'

logging.basicConfig(level=logging.INFO, format='%(message)s')

def parse_relative_date(text):
    match = re.match(r'([\d.]+)\s(years?|months?|weeks?|days?)\sago', text)
    if not match:
        return None

    value, unit = float(match.group(1)), match.group(2)
    if 'year' in unit:
        days = math.ceil(value * 366)
    elif 'month' in unit:
        days = math.ceil(value * 31)
    elif 'week' in unit:
        days = math.ceil(value * 7)
    elif 'day' in unit:
        days = math.ceil(value)

    return datetime.now() - timedelta(days=days)

## PARSING FUNCTIONS
def get_simfile_name(soup):
    top_nav = soup.find('div', id='top-nav')
    if top_nav:
        links = top_nav.find_all('a')
        if links:
            return links[-1].text.strip()
    raise Exception("Couldn't find simfile name in the page.")

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

def get_last_updated_from_category(soup):
    # Returns a list of: {simfile_id: id, simfile_name: name, last_updated_dt: dt}
    def is_div_id_simfile(id):
        return id is not None and re.match(r'^sim(\d+)$', id) is not None

    simfile_info = []
    for a in soup.find_all('a', id=is_div_id_simfile):
        match = re.match(r'^viewsimfile\.php\?simfileid=(\d+)', a['href'])
        if match:
            simfile_id = match.group(1)
            simfile_name = a.text.strip()
            row = a.find_parent('tr')
            cells = row.find_all('td')
            for cell in cells:
                last_update_text = cell.get_text(strip=True)
                last_updated_dt = parse_relative_date(last_update_text)
                if last_updated_dt:
                    break
            if not last_updated_dt:
                raise Exception(f"Failed to find a date fo simfile_id {simfile_id} ({simfile_name})")

            simfile_info.append({
                'simfile_id': simfile_id, 
                'simfile_name': simfile_name,
                'last_updated_dt': last_updated_dt
            })
    return simfile_info

## FILE HANDLING FUNCTIONS
def extract_zip_to_dir(zip_bytes, target_dir):
    with zipfile.ZipFile(BytesIO(zip_bytes)) as z:
        z.extractall(target_dir)

def mkdir_simfiles_dir():
    os.makedirs(SIMFILES_DIR, exist_ok=True)

def find_sm_file(directory, simfile_name):
    # Look for {simfile_name}.sm in each subdirectory of directory
    base_name = directory + f"{simfile_name}/{simfile_name}"
    if os.path.exists(base_name+".sm"):
        return base_name+".sm"
    if os.path.exists(base_name+".ssc"):
        return base_name+".ssc"

def scrape_simfile(simfile_id):
    simfile_url = BASE_URL + f'viewsimfile.php?simfileid={simfile_id}'
    try:
        resp = requests.get(simfile_url, timeout=30)
        resp.raise_for_status()
        html = resp.text
        soup = BeautifulSoup(html, 'html.parser')
        simfile_name = get_simfile_name(soup)
        zip_link = get_zip_link(soup)
    except Exception as e:
        logging.error(f"Error scraping page: {e}")
        return

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
    simfile_info = get_last_updated_from_category(soup)
    for simfile in simfile_info:
        simfile_id = simfile['simfile_id']
        simfile_name = simfile['simfile_name']
        last_updated_dt = simfile['last_updated_dt']

        sm_file = find_sm_file(SIMFILES_DIR, simfile_name)
        if sm_file:
            local_mtime = datetime.fromtimestamp(os.path.getmtime(sm_file))
            logging.info(f"[{simfile_id} - {simfile_name}] Local SM file last modified: {local_mtime}")
            logging.info(f"[{simfile_id} - {simfile_name}] Remote SM file last updated: {last_updated_dt}")
            if local_mtime >= last_updated_dt:
                logging.info(f"[{simfile_id} - {simfile_name}] Local SM file is up to date.")
                continue
            else:
                logging.info(f"[{simfile_id} - {simfile_name}] Local SM file is outdated. Downloading new zip...")
        else:
            logging.info(f"[{simfile_id} - {simfile_name}] No local SM file found. Downloading zip...")
        # scrape_simfile(simfile_id)

if __name__ == "__main__":
    scrape_category(WORLD_URL)
