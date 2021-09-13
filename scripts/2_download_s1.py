# -*- coding: utf-8 -*-
"""
Download Sentinel-1 images that fit into a geographical region and 
within an specific time period. 
Needs credentials to SentinelHub

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
# download_folder = r"PATH/TO/DIR"
download_folder = r"E:\UniSalzburg\Projects\SliDEM\02_code\SliDEM-python\data"
os.chdir(download_folder)

#### Filter scenes based on perpendicular baseline in the
#### 1_filter_query.R
# Get ids for filtered images
products_filter = pd.read_csv(os.path.join(download_folder, 'Sentinel_images_filtered.csv'))
products_ls = products_filter['uuid'].tolist()

# Filter only by HH & VV polarization
path_filter = make_path_filter("*s1?-iw[12]-slc-vv-*.tiff")

# Download files
api.download_all(products_ls, nodefilter = path_filter)

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
