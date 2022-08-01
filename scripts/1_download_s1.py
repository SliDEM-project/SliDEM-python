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
This file is used for your own security, so that you don't accidentally 
share code with your credentials. However, if you want to skip this and
pass your login and password to the command line, you can pass this to 
the `asf_login` and `asf_pwd`, respectively.

The `query_result` file should have been edited by the user 
to change the Download column to TRUE for those pair of scenes that seem 
suitable for processing. 
''',
    epilog='''
Versions: 
  v0.0.1 - 11/2021 - Download scenes from ASF repository
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
  Should be located in the specified download_folder.'''
)
parser.add_argument(
    '--asf_login',
    type=str,
    default=None,
    help='''Login information to ASF server: username'''
)
parser.add_argument(
    '--asf_pwd',
    type=str,
    default=None,
    help='''Login information to ASF server: password'''
)
args = parser.parse_args()

os.chdir('home/')

# Handle credentials
if os.path.isfile('.env'):
    load_dotenv('.env')
    usrnm = os.environ.get('asf_login')
    passw = os.environ.get('asf_pwd')
else:
    usrnm = args.asf_login
    passw = args.asf_pwd

# Initiate session
session = asf.ASFSession()
session.auth_with_creds(usrnm, passw)

# Download from URL list
products = pd.read_csv(
    os.path.join(args.download_folder, args.query_result),
    sep=None, engine='python'
)
productsIn = products[products['Download']]

refIDs = productsIn['ReferenceID'].tolist()
matchIDs = productsIn['MatchID'].tolist()
productIDs = list(set(refIDs + matchIDs))

# Check if products are already on the download directory
productList = [args.download_folder + "/" + f"{s}.zip" for s in productIDs]
productExists = []
for p in productList:
    productExists.append(os.path.exists(p))

print("Existing scenes on directory: ", sum(productExists))

productIDs_download = [d for (d, remove) in zip(productIDs, productExists) if not remove]
print("Scenes to download: ", len(productIDs_download))

urls = [f"https://datapool.asf.alaska.edu/SLC/SB/{s}.zip" for s in productIDs_download]
asf.download_urls(urls=urls, path=args.download_folder, session=session, processes=4)

print("All images downloaded!")
