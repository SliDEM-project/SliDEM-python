# -*- coding: utf-8 -*-

# Import modules
import argparse
import asf_search as asf
from dotenv import load_dotenv
import os
import pandas as pd

# Arguments
parser = argparse.ArgumentParser(
  description='''Download Sentinel-1 images that fit into a geographical region and
within an specific time period. Needs credentials to ASF saved in a
.env file saved on the directory mounted as a volume on the docker.
Username should be save as `asf_login` and password as `asf_pwd`.

The `query_result` file should have been edited by the user 
to change the Download column to TRUE for those pair of scenes that seem 
suitable for processing. 
''',
  epilog='''
Versions: 
  v0.1 - 11/2021 - Download from ASF repository
Authors:
  Lorena Abad - University of Salzburg - lorena.abad@plus.ac.at''',
  formatter_class=argparse.RawTextHelpFormatter
)
parser.add_argument(
  '--download_folder',
  type=str,
  default='data',
  help='relative path (refers to mounted volume) to the folder where S1 scenes will be downloaded'
)
parser.add_argument(
  '--query_result',
  type=str,
  help='''path to the CSV file with query results from 0_query_s1.py. 
  Should be located in the specified download folder.'''
)
args = parser.parse_args()

# Change credentials inside a .env file
load_dotenv('home/.env')
os.chdir('home/')

# Initiate session
session = asf.ASFSession()
session.auth_with_creds(
  os.environ.get('asf_login'),
  os.environ.get('asf_pwd')
)

# Download from URL list
products = pd.read_csv(os.path.join(args.download_folder, args.query_result))
productsIn = products[products['Download']]

refIDs = productsIn['ReferenceID'].tolist()
matchIDs = productsIn['MatchID'].tolist()
productIDs = list(set(refIDs + matchIDs))

print("Scenes to download: ", len(productIDs))

urls = [f"https://datapool.asf.alaska.edu/SLC/SB/{s}.zip" for s in productIDs]
asf.download_urls(urls=urls, path=args.download_folder, session=session, processes=4)

print("All images downloaded")
