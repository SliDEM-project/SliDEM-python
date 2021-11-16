# -*- coding: utf-8 -*-
"""
Download Sentinel-1 images that fit into a geographical region and 
within an specific time period. 
Needs credentials to SentinelHub stored in .env file
Recommended: first run an image query using repo = 'asf',
no credentials needed

First version: June 2019
Update: November 2021 to use ASF

@authors:
  Benjamin Robson, University of Bergen
  Lorena Abad, University of Salzburg
"""

# Import modules and activate logging
import asf_search as asf
from dotenv import load_dotenv
import geopandas as gpd
import logging
import numpy as np
import os
import pandas as pd
from sentinelsat import SentinelAPI, read_geojson, geojson_to_wkt
import requests

pd.options.mode.chained_assignment = None  # default='warn'
# https://stackoverflow.com/questions/20625582/how-to-deal-with-settingwithcopywarning-in-pandas
logging.basicConfig(format='%(message)s', level='INFO')

# VARIABLES SET START------
# Input login credentials
# Change credentials inside a .env file
load_dotenv('home/.env')
os.chdir('home/')

# Set the working directory and search queries
download_folder = "data/s1"
query_result_file = "s1_scenes_alta_2019.csv"

# Set date range.
date_start = '2019-05-01'
date_end = '2019-09-30'

# GeoJSON file of study area. Any images overlapping this will be downloaded
aoi = r"data/aoi/Alta.geojson"

# Set maximum temporal baseline and minimum perpendicular baseline
btempth = 60
bperpth = 140

# Repository to query, can be sentinelhub or asf
repo = 'asf'
# VARIABLES SET END ------

# Setup params
dates = '[' + date_start + 'T00:00:00.000Z TO ' + date_end + 'T00:00:00.000Z]'
footprint = geojson_to_wkt(read_geojson(aoi))
tempfile1 = 'tmpgeo.csv'

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
    file_name = os.path.join(download_folder, tempfile1)
    products_df.to_csv(file_name, index=False)
elif repo == "asf":
    products = asf.geo_search(platform=[asf.PLATFORM.SENTINEL1],
                              intersectsWith=footprint,
                              processingLevel=[asf.PRODUCT_TYPE.SLC],
                              start=date_start,
                              end=date_end,
                              maxResults=1000)
    products_df = pd.DataFrame([p.properties for p in products])

    # Write to CSV file
    file_name = os.path.join(download_folder, tempfile1)
    products_df.to_csv(file_name, index=False)
else:
    print("Repository not supported.")

# Create empty list to hold the results
candidates = []

# Read scene IDs
# Get ids for filtered images
geo_prod = pd.read_csv(os.path.join(download_folder, tempfile1))
geo_ids = geo_prod['fileID'].map(lambda fileID: str.replace(fileID, '-SLC', '')).tolist()

# Loop over geo_ids to get matching scenes with desired temporal and perpendicular baselines
tempfile2 = 'tmpbaseline.csv'
for i in range(0, len(geo_ids)):
    order_url = "https://api.daac.asf.alaska.edu/services/search/baseline?reference="
    scene_id = geo_ids[i]
    output_type = "&output=csv"
    url = order_url + scene_id + output_type
    response = requests.post(url)

    # Write to .CSV
    baseline_file = os.path.join(download_folder, tempfile2)
    f = open(baseline_file, "w")
    f.write(response.text)
    f.close()

    # Read in CSV file
    baseline = pd.read_csv(baseline_file).replace(to_replace='None', value=np.nan)
    baseline = baseline[(baseline.TemporalBaseline.notnull()) &
                        (baseline.PerpendicularBaseline.notnull())]
    baseline[['TemporalBaseline', 'PerpendicularBaseline']] = \
        baseline[['TemporalBaseline', 'PerpendicularBaseline']].apply(pd.to_numeric)

    baseline_filter = baseline[(abs(baseline['TemporalBaseline']) <= btempth) &
                               (abs(baseline['PerpendicularBaseline']) >= bperpth)]
    baseline_df = baseline_filter[
        ['Granule Name', 'Path Number', 'Ascending or Descending?', 'TemporalBaseline', 'PerpendicularBaseline']]
    baseline_df.rename(columns={'Granule Name': 'MatchID', 'Path Number': 'Orbit', 'Ascending or Descending?': 'Pass'},
                       inplace=True)
    baseline_df.insert(0, 'ReferenceID', scene_id, True)

    candidates.append(baseline_df)

# Merge all dataframes
candidates_df = pd.concat(candidates)

# Extract dates from IDs
candidates_df['ReferenceDate'] = pd.to_datetime(
    candidates_df['ReferenceID'].str.slice(start=17, stop=25),
    format='%Y%m%d'
)
candidates_df['MatchDate'] = pd.to_datetime(
    candidates_df['MatchID'].str.slice(start=17, stop=25),
    format='%Y%m%d'
)

# Check if matched ids are also intersecting with the AOI and dates set
candidates_df['inAOInDates'] = candidates_df['MatchID'].isin(geo_ids)

# Create column where user can mark if download should be done or not
candidates_df['Download'] = False

# Create column with link to eo-browser to check for snow conditions using the NDSI
aoidf = gpd.read_file(aoi)
aoidf['center'] = aoidf['geometry'].centroid
aoi_lat = aoidf.center.y.astype(str)[0]
aoi_lng = aoidf.center.x.astype(str)[0]

candidates_df['EObrowser'] = ('https://apps.sentinel-hub.com/eo-browser/' +
                              '?zoom=14&lat=' + aoi_lat +
                              '&lng=' + aoi_lng +
                              '&themeId=DEFAULT-THEME&datasetId=S2L1C&fromTime=' +
                              candidates_df['ReferenceDate'].astype(str) +
                              'T00%3A00%3A00.000Z&toTime=' +
                              candidates_df['ReferenceDate'].astype(str) +
                              'T23%3A59%3A59.999Z&layerId=8-NDSI')

# Sort by intersected, True on top
candidates_df.sort_values(by=['inAOInDates'], inplace=True, ascending=False)

# Write to CSV file and remove temporal files
file_name = os.path.join(download_folder, query_result_file)
candidates_df.to_csv(file_name, index=False)
os.remove(os.path.join(download_folder, tempfile1))
os.remove(os.path.join(download_folder, tempfile2))
print("CSV file with images to be processed has been written to " + file_name)
