# -*- coding: utf-8 -*-

# Import modules
import argparse
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

# Arguments
parser = argparse.ArgumentParser(
    description='''Query Sentinel-1 scenes that fit into a geographical region and 
within an specific time period. 
Uses the ASF repository to query scenes by a wkt region and a specific temporal 
range. The resulting scenes will go then into a loop to find matching scenes
using the baseline tool from ASF. 

The output is a CSV file with the scenes matching the wkt and temporal arguments,
the matching IDs with a perpendicular and temporal baseline set by the user, and a
URL link to check for atmospheric conditions for the dates in the SentinelHub Explorer.

Not every matching scene is also overlapping the geographical and temporal settings, 
hence a column `inAOInDates` is also included, where TRUE values indicate an overlap of 
both scenes temporally and geographically.

The user is prompted now to check the file and update the `Download` column manually
according to the scenes that they deem useful. 
''',
    epilog='''
Versions: 
  v0.1 - 06/2019 - Download from SentinelHub repository
  v0.2 - 11/2021 - Query from ASF repository
Authors:
  Lorena Abad - University of Salzburg - lorena.abad@plus.ac.at
  Benjamin Robson - University of Bergen''',
    formatter_class=argparse.RawTextHelpFormatter
)
parser.add_argument(
    '--download_folder',
    type=str,
    default='data',
    help='''relative path (refers to mounted volume) to the folder
     where the query_result CSV file should be written to.'''
)
parser.add_argument(
    '--query_result',
    type=str,
    help='''path to the CSV file with query results from 0_query_s1.py.
     Should be located in the specified download folder.'''
)
parser.add_argument(
    '--date_start',
    type=str,
    help='''start date of S1 scene query'''
)
parser.add_argument(
    '--date_end',
    type=str,
    help='''start date of S1 scene query'''
)
parser.add_argument(
    '--aoi',
    type=str,
    help='''path to GeoJSON file (WGS84 - EPSG:4326) with the study area outline.
    Any scenes intersecting this area will be included in the query result'''
)
parser.add_argument(
    '--btempth',
    type=int,
    default=60,
    help='''temporal baseline threshold to query matching scenes. 
    What is the maximum time that matching scenes should have between each other?
    Defaults to 60 days.
    This is checked forward and backwards.'''
)
parser.add_argument(
    '--bperpth',
    type=int,
    default=140,
    help='''perpendicular baseline threshold to query matching scenes. 
    What is the minimum perpendicular baseline between matching scenes?
    Defaults to 140 meters.
    This is checked forward and backwards.'''
)
args = parser.parse_args()

# Input login credentials
# Change credentials inside a .env file
load_dotenv('home/.env')
os.chdir('home/')

# Create download directory if not exisiting
if not os.path.exists(args.download_folder):
    os.mkdir(args.download_folder)

# Setup params
dates = '[' + args.date_start + 'T00:00:00.000Z TO ' + args.date_end + 'T00:00:00.000Z]'
footprint = geojson_to_wkt(read_geojson(args.aoi))
tempfile1 = 'tmpgeo.csv'
# Repository to query, can be sentinelhub or asf
repo = 'asf'

# Connect to API and search
print("Connecting to API and searching images, depending on your AOI size and time period,"
      " this process may take a while. Be patient :)")
if repo == 'sentinelhub':  # not active currently, seems to only query recent images?
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
    file_name = os.path.join(args.download_folder, tempfile1)
    products_df.to_csv(file_name, index=False)
elif repo == "asf":
    products = asf.geo_search(platform=[asf.PLATFORM.SENTINEL1],
                              intersectsWith=footprint,
                              processingLevel=[asf.PRODUCT_TYPE.SLC],
                              start=args.date_start,
                              end=args.date_end,
                              maxResults=1000)
    products_df = pd.DataFrame([p.properties for p in products])

    # Write to CSV file
    file_name = os.path.join(args.download_folder, tempfile1)
    products_df.to_csv(file_name, index=False)
else:
    print("Repository not supported.")

# Create empty list to hold the results
candidates = []

# Read scene IDs
# Get ids for filtered images
geo_prod = pd.read_csv(os.path.join(args.download_folder, tempfile1))
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
    baseline_file = os.path.join(args.download_folder, tempfile2)
    f = open(baseline_file, "w")
    f.write(response.text)
    f.close()

    # Read in CSV file
    baseline = pd.read_csv(baseline_file).replace(to_replace='None', value=np.nan)
    baseline = baseline[(baseline.TemporalBaseline.notnull()) &
                        (baseline.PerpendicularBaseline.notnull())]
    baseline[['TemporalBaseline', 'PerpendicularBaseline']] = \
        baseline[['TemporalBaseline', 'PerpendicularBaseline']].apply(pd.to_numeric)

    baseline_filter = baseline[(abs(baseline['TemporalBaseline']) <= args.btempth) &
                               (abs(baseline['PerpendicularBaseline']) >= args.bperpth)]
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
aoidf = gpd.read_file(args.aoi)
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
file_name = os.path.join(args.download_folder, args.query_result)
candidates_df.to_csv(file_name, index=False)
os.remove(os.path.join(args.download_folder, tempfile1))
os.remove(os.path.join(args.download_folder, tempfile2))
print("CSV file with images to be processed has been written to " + file_name)
print("Now is your turn! Open the file and check the potential S1 pairs, "
      "which of them would you want to download? Update the Download column to TRUE "
      "to set those scene pairs you would like to download and process.")
