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
import numpy as np
import datetime
from itertools import combinations

### Variables --------
# Path to directory with Sentinel-1 imagery; change to your directory
data_folder = r"home/data"
# Minimum temporal baseline in days (should be negative)
min_btemp = -7

# Create an empty list to hold manifest.safe paths
paths = []
# Loop over the data folder to find all the manifest.safe files
for root, dirs, files in os.walk(data_folder):
    for file in files:
        if file.endswith('manifest.safe'):
            path: object = os.path.join(root, file)
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
    # Call products metadata
    metadata_p1 = product1.getMetadataRoot().getElement('Abstracted_Metadata')
    metadata_p2 = product2.getMetadataRoot().getElement('Abstracted_Metadata')
    # import the stack operator from snappy
    create_stack = snap.jpy.get_type('org.esa.s1tbx.insar.gpf.coregistration.CreateStackOp')
    # Use the getBaselines method.
    # 1st argument: list of products between which you want to compute the baseline
    # 2nd argument: a product that will receive the baselines as new metadata
    create_stack.getBaselines([product1, product2], product1)
    # Now there is a new piece of metadata in product one called 'Baselines'
    baseline_root_metadata = metadata_p1.getElement('Baselines')

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
            productid_p1 = metadata_p1.getAttributeString('PRODUCT')
            productid_p2 = metadata_p2.getAttributeString('PRODUCT')
            # Extract the timestamp of each image
            timestamp_p1 = metadata_p1.getAttributeString('PROC_TIME')
            timestamp_p2 = metadata_p2.getAttributeString('PROC_TIME')
            # Extract the pass of each image
            pass_p1 = metadata_p1.getAttributeString('PASS')
            pass_p2 = metadata_p2.getAttributeString('PASS')
            # Extract the relative orbit of each image
            orbit_p1 = metadata_p1.getAttributeDouble('REL_ORBIT')
            orbit_p2 = metadata_p2.getAttributeDouble('REL_ORBIT')
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
              "temp_baseline": temp_baseline,
              "perp_baseline": perp_baseline
            }

            # Collect variables in a data frame, where each row corresponds to an image pair
            df = df.append(dictionary, ignore_index=True)

# Filter data frame according to recquired characteristics
# For DEM generation, the pairs should:
# 1. Have a temporal baseline lower than min_btemp (configures on top of the script)
df_filtered = df[df["temp_baseline"] < 0]
df_filtered = df_filtered[df_filtered["temp_baseline"] >= min_btemp]
# 2. The master/slave pair should be from the same orbit
df_filtered = df_filtered[df_filtered["orbit1"] == df_filtered["orbit2"]]
# 3. The master/slave pair should be from the same pass
df_filtered = df_filtered[df_filtered["pass1"] == df_filtered["pass2"]]

## Format new variables to include in string column to pass to PCI Geomatica
df_filtered['timestamp1'] = pd.to_datetime(df_filtered['timestamp1'])
df_filtered['timestamp1'] = df_filtered['timestamp1'].dt.strftime('%Y%m%d').astype(int)
df_filtered['timestamp2'] = pd.to_datetime(df_filtered['timestamp2'])
df_filtered['timestamp2'] = df_filtered['timestamp2'].dt.strftime('%Y%m%d').astype(int)
df_filtered['index'] = np.arange(df_filtered.shape[0]).astype(str)
df_filtered['timedelta'] = pd.to_timedelta(df_filtered['temp_baseline'] * -1, unit='D')
df_filtered['day'] = df_filtered['timedelta'].dt.components['days'].astype(str).str.zfill(2)
df_filtered['hour'] = df_filtered['timedelta'].dt.components['hours'].astype(str).str.zfill(2)
df_filtered['min'] = df_filtered['timedelta'].dt.components['minutes'].astype(str).str.zfill(2)
df_filtered['sec'] = df_filtered['timedelta'].dt.components['seconds'].astype(str).str.zfill(2)
df_filtered['string'] = (
        df_filtered['index'] + ';' +
        df_filtered['path1'] + ';' +
        df_filtered['timestamp1'].astype(str) + ';' +
        df_filtered['path2'] + ';' +
        df_filtered['timestamp2'].astype(str) + ';' +
        df_filtered['day'] + ':' + df_filtered['hour'] + ':' + df_filtered['min'] + ':' + df_filtered['sec'] + ';' +
        df_filtered['perp_baseline'].astype(str)
)

# Save results to an CSV file
df_filtered.to_csv(os.path.join(data_folder, "data.csv"), index=False)

# Extract formatted string for input to PCI Geomatica
strings = df_filtered["string"].values.tolist()

imagelist = os.path.join(data_folder, "master_slaves_images.txt")

imgtxt = open(imagelist, 'w')
for string in strings:
    imgtxt.write("%s\n" % string)
imgtxt.close()

print("Baseline report written to " + imagelist)
