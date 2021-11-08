# -*- coding: utf-8 -*-
"""
Download Sentinel-1 images that fit into a geographical region and 
within an specific time period. 
Needs credentials to SentinelHub stored in .env file
Recommended: first run an image query using repo = 'asf',
no credentials needed

First version: June 2019
Update: November 2021
@authors:
  Benjamin Robson, University of Bergen
  Lorena Abad, University of Salzburg
"""

# Import modules and activate logging
import asf_search as asf
from dotenv import load_dotenv
import logging
import os
import pandas as pd
from sentinelsat import SentinelAPI, read_geojson, geojson_to_wkt

logging.basicConfig(format='%(message)s', level='INFO')

# VARIABLES SET START------
# Input login credentials
# Change credentials inside a .env file
load_dotenv('home/.env')
os.chdir('home/')

# Set the working directory and search queries
download_folder = r"data/s1"

# Set date range.
# NB: Older images may be "Offline".
# See Sentinelsat documentation on how to request offline products
date_start = '2019-06-01'
date_end = '2019-10-30'

# GeoJSON file of study area. Any images overlapping this will be downloaded
aoi = r"data/aoi/Alta.geojson"

# Repository to query, can be sentinelhub or asf
repo = 'asf'
# VARIABLES SET END ------

# Setup params
dates = '[' + date_start + 'T00:00:00.000Z TO ' + date_end + 'T00:00:00.000Z]'
footprint = geojson_to_wkt(read_geojson(aoi))

# Connect to API and search
if repo == 'sentinelhub':
    # Connect to Sentinel API
    # Norway mirror:
    api_url = 'https://colhub.met.no/'
    # Austria mirror:
    # api_url = 'https://data.sentinel.zamg.ac.at/'
    username = os.environ.get('hub_login_br')
    password = os.environ.get('hub_pwd_br')
    api = SentinelAPI(
        username,
        password,
        api_url=api_url,
        show_progressbars=True
    )

    # Additional parameters can be set here, for example the processing level.
    # Valid search query keywords can be found at the Copernicus Open Access Hub documentation.
    # (https://scihub.copernicus.eu/twiki/do/view/SciHubUserGuide/FullTextSearch?redirectedfrom=SciHubUserGuide.3FullTextSearch)
    products = api.query(
        footprint,
        dates,
        platformname='Sentinel-1',
        producttype='SLC'
    )

    # Convert list of available images to Pandas DataFrame
    products_df = api.to_dataframe(products)

    # Write to CSV file
    file_name = os.path.join(download_folder, "sentinelhub_images.csv")
    products_df.to_csv(file_name, index=False)
    print("CSV file with images to be processed has been written to " + file_name)
elif repo == "asf":
    products = asf.geo_search(platform=[asf.PLATFORM.SENTINEL1],
                              intersectsWith=footprint,
                              processingLevel=[asf.PRODUCT_TYPE.SLC],
                              start=date_start,
                              end=date_end,
                              maxResults=1000)
    products_df = pd.DataFrame([p.properties for p in products])

    # Write to CSV file
    file_name = os.path.join(download_folder, "asf_images.csv")
    products_df.to_csv(file_name, index=False)
    print("CSV file with images to be processed has been written to " + file_name)
else:
    print("Repository not supported.")
