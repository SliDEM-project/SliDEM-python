# -*- coding: utf-8 -*-
# Adapted from: https://github.com/stienheremans/download-planet_python/blob/master/download_planet_data.py

import pandas as pd
import json
import geojson
import requests
import time
import pathlib
import os
from requests.auth import HTTPBasicAuth

# set aoi
aoi_def = "Kleinarl"

# set up requests to work with api
orders_url = 'https://api.planet.com/compute/ops/orders/v2'

# os.environ['PL_API_KEY']='22c7555380db430285fc246936510788'
auth = HTTPBasicAuth(os.getenv('PL_API_KEY'), '')
headers = {'content-type': 'application/json'}


# define helpful functions for submitting, polling, and downloading an order
def place_order(request, auth):

    response = requests.post(orders_url, data=json.dumps(request), auth=auth, headers=headers)
    print(response)

    if not response.ok:
        raise Exception(response.content)

    order_id = response.json()['id']
    print(order_id)
    order_url = orders_url + '/' + order_id
    return order_url


def poll_for_success(order_url, auth, num_loops=50):
    count = 0
    while count < num_loops:
        count += 1
        r = requests.get(order_url, auth=auth)
        response = r.json()
        state = response['state']
        print(state)
        success_states = ['success', 'partial']
        if state == 'failed':
            raise Exception(response)
        elif state in success_states:
            break

        time.sleep(10)


def download_order(order_url, auth, overwrite=False):
    r = requests.get(order_url, auth=auth)
    print(r)

    response = r.json()
    results = response['_links']['results']
    results_urls = [r['location'] for r in results]
    results_names = [r['name'] for r in results]
    results_paths = [pathlib.Path(os.path.join('data', 'optical', 'PlanetScope', aoi_def, n)) for n in results_names]
    print('{} items to download'.format(len(results_urls)))

    for url, name, path in zip(results_urls, results_names, results_paths):
        if overwrite or not path.exists():
            print('downloading {} to {}'.format(name, path))
            r = requests.get(url, allow_redirects=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            open(path, 'wb').write(r.content)
        else:
            print('{} already exists, skipping {}'.format(path, name))

    return dict(zip(results_names, results_paths))


data_dir = r"E:\UniSalzburg\Projects\SliDEM\02_code\SliDEM-python\data"
with open(os.path.join(data_dir, "aoi", str(aoi_def) + ".geojson")) as f:
    gj = geojson.load(f)
features = gj['features'][0]

geometry = {
    "type": "Polygon",
    "coordinates": [
        [
            []

        ]
    ]
}
# replace coordinates in the empty json file created above by the actual coordinates from the geojson file
geometry["coordinates"] = features.geometry.coordinates
print(geometry)

# define the clip tool
clip = {
    "clip": {
        "aoi": geometry
    }
}

# Open the CSV with the selected images for download
scene_file = os.path.join(data_dir, "scenes", "Planet_S2_potential_scenes.csv")
scenes = pd.read_csv(scene_file)

# Filter only planet scenes
scenes_ps = scenes[(scenes['sensor'] == 'PlanetScope') & (scenes['aoi'] == aoi_def)]

# Extract ids from CSV
scene_ids = scenes_ps['scene_id'].tolist()

# Loop over images and download
for i in range(2, len(scene_ids)):
    # define products part of order
    single_product = [
        {
            "item_ids": [scene_ids[i]],
            "item_type": "PSScene4Band",
            "product_bundle": "analytic_sr"
        }
    ]
    request_clip = {
        "name": "clip_scene",
        "products": single_product,
        "tools": [clip]
    }

    # create an order request with the clipping tool
    clip_order_url = place_order(request_clip, auth)
    poll_for_success(clip_order_url, auth)
    downloaded_files = download_order(clip_order_url, auth)
