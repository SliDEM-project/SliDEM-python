# -*- coding: utf-8 -*-
"""
Download Sentinel-1 images that fit into a geographical region and 
within an specific time period

First version: June 2019
@authors: 
  Benjamin Robson, University of Bergen
"""

# Import modules and activate logging
from sentinelsat import SentinelAPI, read_geojson, geojson_to_wkt
import pandas as pd
import logging
import zipfile, fnmatch
import os
logging.basicConfig(format='%(message)s', level='INFO')

# Input login credentials
# NB: If you want to download off the Norwegian mirror comment in the lines below. 
# Data is available only at level 1C, but download speeds are much greater

## Variables ------

# Can be replaced with National mirrors. 
# Remove this argument from below if you want to use the ESA Scihub
api_url = 'https://colhub.met.no/'
username = "USERNAME"
password = "PWD"
api = SentinelAPI(
  username,
  password,
  api_url = api_url,
  show_progressbars=True
)

# Set the working directory and search queries
download_folder = r"PATH/TO/DIR"
os.chdir(download_folder)

# Set date range. 
# NB: Older images may be "Offline". See Sentinelsat documentation on how to request offline products
dates = '[2019-09-01T00:00:00.000Z TO 2019-11-10T00:00:00.000Z]' 
# GeoJSON file of study area. Any images overlapping this will be downloaded
footprint = geojson_to_wkt(read_geojson(r"PATH/TO/GEOJSON_FILE.geojson")) 

# Additional parameters can be set here, for example the processing level. 
# Valid search query keywords can be found at the Copernicus Open Access Hub documentation. 
# (https://scihub.copernicus.eu/twiki/do/view/SciHubUserGuide/FullTextSearch?redirectedfrom=SciHubUserGuide.3FullTextSearch)
products = api.query(
  footprint,
  dates,
  platformname = 'Sentinel-1',
  producttype='SLC'
)

# Convert list of available images to Pandas DataFrame
products_df = api.to_dataframe(products)

# Write to Excel file
products_df.to_excel(os.path.join(download_folder, "Sentinel_images.xlsx"), index = False) 
print ("Excel file with images to be processed has been written to " + file_name)

# Download all images
api.download_all(products)

files = os.listdir(download_folder)

# Unzip all products, keeping original name
pattern = '*.zip'
for root, dirs, files in os.walk(download_folder):
  for filename in fnmatch.filter(files, pattern):
  pathzip = os.path.join(root, filename)
  
outzip = os.path.join(download_folder, os.path.splitext(filename)[0])
print ("now unzipping " + filename)
zipfile.ZipFile(pathzip).extractall(outzip)

print ("All images downloaded and zipped")
