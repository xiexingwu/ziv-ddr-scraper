# Quickstart
By default, each simfile is saved in the `simfiles/{DDR version}/` directory.

## Scrape all
```sh
python scrape_simfiles.py
```
Scrape all simfiles from all major DDR versions.

## Scrape by id
```sh
python scrape_simfiles.py 65828 52933
```
Scrape a list of simfiles by their IDs. The above would scrape:
- 65828: "ARACHNE" from WORLD
- 52933: "Lilieze to enryuu Laevateinn" from A3

# Known issues
- 729: ".59" has a broken zip file as of 2025-7-26.
