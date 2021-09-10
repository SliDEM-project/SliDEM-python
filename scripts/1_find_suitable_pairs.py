# -*- coding: utf-8 -*-
"""
Find suitable Sentinel-1 pairs to generate interferograms based on 
their pass, relative orbit, and their temporal baseline. 
Baselines are computed with snappy, by creating a stack between 
all pair of images. Once computation is done only suitable 
master/slave pairs are filtered and results saved into a table.

Code partly based on: 
  https://forum.step.esa.int/t/insar-dinsar-perpendicular-baseline-calculation/3776/34

First version: September 2021
@authors: 
  Benjamin Robson, University of Bergen
  Lorena Abad, University of Salzburg
"""

# Call in libraries
import snappy as snap
import os
import pandas as pd
from itertools import combinations

### Variables --------
# Path to directory with Sentinel-1 imagery; change to your directory
data_folder = r"PATH/TO/S1/DATA"
# Minimum temporal baseline in days (should be negative)
min_btemp = -7

# Create an empty list to hold manifest.safe paths
paths = []
# Loop over the data folder to find all the manifest.safe files
for root, dirs, files in os.walk(data_folder):
  for file in files:
    if file.endswith('manifest.safe'):
    path = os.path.join(root, file)
    paths.append(path)

## Generate unique combinations of single Sentinel-1 images ------
# Create an empty list to hold the path to the two sets of images
paths1 = []
paths2 = []

# Compute unique combinations, paths1 and paths will now be 
# two ordered lists with unique combination pairs
for i in combinations(paths, 2):
  p1 = i[0]
  p2 = i[1]
  paths1.append(p1)
  paths2.append(p2)

## Generate table with extracted S1 metadata and baseline calculations ----
# Create empty data frame to hold the results
df = pd.DataFrame()

# Loop over the unique pair of images
for i in range(0, len(paths1)):
  product1 = snap.ProductIO.readProduct(paths1[i])
  product2 = snap.ProductIO.readProduct(paths2[i])
  # import the stack operator from snappy
  create_stack = snap.jpy.get_type('org.esa.s1tbx.insar.gpf.coregistration.CreateStackOp')
  # Use the getBaselines method.
  # 1st argument: list of products between which you want to compute the baseline
  # 2nd argument: a product that will receive the baselines as new metadata
  create_stack.getBaselines([product1, product2], product1)
  # Now there is a new piece of metadata in product one called 'Baselines'
  baseline_root_metadata = product1.getMetadataRoot().getElement('Abstracted_Metadata').getElement('Baselines')
  
  # You can now display all the baselines between all master/slave configurations
  # Get IDs of master images
  master_ids = list(baseline_root_metadata.getElementNames())
  # Loop over all master/slave combinations to obtain relevant info
  for master_id in master_ids:
    # Get IDs of slave images
    slave_ids = list(baseline_root_metadata.getElement(master_id).getElementNames())
    # Loop over combinations
    for slave_id in slave_ids:
      # Extract the Product ID of each image 
      productid_p1 = product1.getMetadataRoot().getElement('Abstracted_Metadata').getAttributeString('PRODUCT')
      productid_p2 = product2.getMetadataRoot().getElement('Abstracted_Metadata').getAttributeString('PRODUCT')
      # Extract the timestamp of each image
      timestamp_p1 = product1.getMetadataRoot().getElement('Abstracted_Metadata').getAttributeString('PROC_TIME')
      timestamp_p2 = product2.getMetadataRoot().getElement('Abstracted_Metadata').getAttributeString('PROC_TIME')
      # Extract the pass of each image
      pass_p1 = product1.getMetadataRoot().getElement('Abstracted_Metadata').getAttributeString('PASS')
      pass_p2 = product2.getMetadataRoot().getElement('Abstracted_Metadata').getAttributeString('PASS')
      # Extract the relative orbit of each image
      orbit_p1 = product1.getMetadataRoot().getElement('Abstracted_Metadata').getAttributeDouble('REL_ORBIT')
      orbit_p2 = product2.getMetadataRoot().getElement('Abstracted_Metadata').getAttributeDouble('REL_ORBIT')
      # Extract the polarisation of each image
      mds1_tx_rx_polar
      mds2_tx_rx_polar
      mds3_tx_rx_polar
      mds4_tx_rx_polar
      polar_p1 = product1.getMetadataRoot().getElement('Abstracted_Metadata').getAttributeString('transmitterReceiverPolarisation')
      polar_p2 = product2.getMetadataRoot().getElement('Abstracted_Metadata').getAttributeString('transmitterReceiverPolarisation')
      # Compute statistics for image pairs
      pair_stats = baseline_root_metadata.getElement(master_id).getElement(slave_id)
      # Extract perpendicular and temporal baseline
      perp_baseline = pair_stats.getAttributeDouble('Perp Baseline')
      temp_baseline = pair_stats.getAttributeDouble('Temp Baseline')
      
      # Save variables into a dictionary
      dictionary = {
        "path1": paths1[i],
        "path2": paths2[i],
        "id1": productid_p1,
        "id2": productid_p2,
        "timestamp1": timestamp_p1,
        "timestamp2": timestamp_p2,
        "pass1": pass_p1,
        "pass2": pass_p2,
        "orbit1": orbit_p1,
        "orbit2": orbit_p2,
        "master": master_id,
        "slave": slave_id,
        "Temp_baseline": temp_baseline,
        "Perp_baseline": perp_baseline
      }
      
# Collect variables in a data frame, where each row corresponds to an image pair
df = df.append(dictionary, ignore_index = True)

# Filter data frame according to recquired characteristics
# For DEM generation, the pairs should
# 1. Have a temporal baseline lower than min_btemp (configures on top of the script)
df_filtered = df[df["Temp_baseline"] < 0]
df_filtered = df_filtered[df_filtered["Temp_baseline"] >= min_btemp]
# 2. The master/slave pair should be from the same orbit
df_filtered = df_filtered[df_filtered["orbit1"] == df_filtered["orbit2"]]
# 2. The master/slave pair should be from the same pass
df_filtered = df_filtered[df_filtered["pass1"] == df_filtered["pass2"]]

# Save results to an excel file
df_filtered.to_excel(os.path.join(data_folder, "data.xlsx"), index = False) 
