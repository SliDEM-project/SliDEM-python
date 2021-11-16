# -*- coding: utf-8 -*-
"""
Download Sentinel-1 images that fit into a geographical region and 
within an specific time period.
Needs credentials to ASF

First version: November 2021

@authors:
  Lorena Abad, University of Salzburg
"""

# Import modules
import pandas as pd
import asf_search as asf
from dotenv import load_dotenv
import os

# Change credentials inside a .env file
load_dotenv('home/.env')
os.chdir('home/')

# VARIABLES SET START------
# Initiate session
session = asf.ASFSession()
session.auth_with_creds(
  os.environ.get('earthdata_login_la'),
  os.environ.get('earthdata_pwd_la')
)

# Set the working directory and search queries
download_folder = "data/s1"
query_result_file = "s1_scenes_alta_2019.csv"
# VARIABLES SET END ------

# Download from URL list
products = pd.read_csv(os.path.join(download_folder, query_result_file))
productsIn = products[products['Download']]

refIDs = productsIn['ReferenceID'].tolist()
matchIDs = productsIn['MatchID'].tolist()
productIDs = list(set(refIDs + matchIDs))

print("Scenes to download: ", len(productIDs))

urls = [f"https://datapool.asf.alaska.edu/SLC/SB/{s}.zip" for s in productIDs]
asf.download_urls(urls=urls, path=download_folder, session=session, processes=4)

print("All images downloaded")
