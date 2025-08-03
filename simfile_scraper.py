import math
import sys
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import zipfile
from io import BytesIO
import logging
import re

BASE_URL = 'https://zenius-i-vanisher.com/v5.2/'
BASE_SIMFILES_DIR = 'simfiles/'
VER_ID_NAME_PAIRS = [
    (1709, "WORLD"),
    (1509, "A3"),
    (1293, "A20 PLUS"),
    (1292, "A20"),
    (1148, "A"),
    (864, "2014"),
    (845, "2013"),
    (802, "X3"),
    (546, "X2"),
    (295, "X"),
    (77, "SuperNOVA2"),
    (1, "SuperNOVA"),
    (41, "EXTREME"),
    (31, "MAX2"),
    (40, "MAX"),
    (30, "5th"),
    (39, "4th"),
    (38, "3rd"),
    (32, "2nd"),
    (37, "1st")
]

try:
    os.remove("logs.log")
except:
    pass
logging.basicConfig(level=logging.INFO, format='%(message)s')
file_handler = logging.FileHandler("logs.log")
logging.getLogger().addHandler(file_handler)

def parse_relative_date(text):
    match = re.match(r'([\d.]+)\s(years?|months?|weeks?|days?|hours?|minutes?|seconds?)\sago', text)
    if not match:
        return None

    value, unit = float(match.group(1)), match.group(2)
    if 'year' in unit:
        delta = timedelta(days=math.ceil(value * 366))
    elif 'month' in unit:
        delta = timedelta(days=math.ceil(value * 31))
    elif 'week' in unit:
        delta = timedelta(days=math.ceil(value * 7))
    elif 'day' in unit:
        delta = timedelta(days=value)
    elif 'hour' in unit:
        delta = timedelta(hours=value)
    elif 'minute' in unit:
        delta = timedelta(minutes=value)
    elif 'second' in unit:
        delta = timedelta(seconds=value)

    return datetime.now() - delta

## PARSING FUNCTIONS
def get_simfile_name(soup):
    top_nav = soup.find('div', id='top-nav')
    if top_nav:
        links = top_nav.find_all('a')
        if links:
            return links[-1].text.strip()
    raise Exception("Couldn't find simfile name in the page.")

def get_simfile_version(soup):
    full_version_text = soup.find('div', id='top-nav').find_all('a')[-2].text.strip()
    pattern = '|'.join(f'{name}' for _, name in VER_ID_NAME_PAIRS)
    pattern = f'({pattern})'
    match = re.search(pattern, full_version_text)
    if match:
        simfile_ver = match.group(1)
        return simfile_ver
    else:
        logging.info(f"Failed to find simfile version in text: {full_version_text}")

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
                raise Exception(f"Failed to find a date for simfile_id [{simfile_id} - {simfile_name}]:\n{row}")

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

def mkdir_simfiles_dir(simfile_dir):
    os.makedirs(simfile_dir, exist_ok=True)

def find_simfile(directory, simfile_name):
    # Look for {simfile_name}.sm in each subdirectory of directory
    base_name = directory + f"{simfile_name}/{simfile_name}"
    sm_file= base_name + ".sm"
    ssc_file = base_name + ".ssc"
    if os.path.exists(sm_file) and os.path.exists(ssc_file):
        logging.info(f"Found both SM and SSC files for {simfile_name} in {directory}. Removing SM file.")
        os.remove(sm_file)
        return ssc_file
    elif os.path.exists(sm_file):
        return sm_file
    elif os.path.exists(ssc_file):
        return ssc_file

def scrape_simfile(simfile_id, simfiles_dir = None):
    simfile_url = BASE_URL + f'viewsimfile.php?simfileid={simfile_id}'
    try:
        resp = requests.get(simfile_url, timeout=30)
        resp.raise_for_status()
        html = resp.text
        soup = BeautifulSoup(html, 'html.parser')
        simfile_name = get_simfile_name(soup)
        zip_link = get_zip_link(soup)
        logging.info(f"[{simfile_id} - {simfile_name}] Found zip link: {zip_link}")
        if not simfiles_dir:
            simfile_ver = get_simfile_version(soup)
            logging.info(f"[{simfile_id} - {simfile_name}] Found simfile version: {simfile_ver}")
            simfiles_dir = BASE_SIMFILES_DIR + f"DDR {simfile_ver}/"
    except Exception as e:
        logging.error(f"Error scraping page: {e}")
        return

    try:
        zip_resp = requests.get(zip_link, timeout=30)
        zip_resp.raise_for_status()
        extract_zip_to_dir(zip_resp.content, simfiles_dir)
        logging.info(f"[{simfile_id} - {simfile_name}] Downloaded and extracted to {simfiles_dir}")
    except Exception as e:
        logging.error(f"[{simfile_id} - {simfile_name}] Error downloading or extracting zip: {e}")

def scrape_category(version_id, version_name):
    simfiles_dir = BASE_SIMFILES_DIR + f"DDR {version_name}/"
    mkdir_simfiles_dir(simfiles_dir)
    version_url = BASE_URL + f'viewsimfilecategory.php?categoryid={version_id}'

    resp = requests.get(version_url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    simfile_info = get_last_updated_from_category(soup)
    for simfile in simfile_info:
        simfile_id = simfile['simfile_id']
        simfile_name = simfile['simfile_name']
        last_updated_dt = simfile['last_updated_dt']

        sm_file = find_simfile(simfiles_dir, simfile_name)
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
        scrape_simfile(simfile_id, simfiles_dir)

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        for simfile_id in sys.argv[1:]:
            scrape_simfile(simfile_id)
    else:
        for version_id, version_name in VER_ID_NAME_PAIRS:
            scrape_category(version_id, version_name)
