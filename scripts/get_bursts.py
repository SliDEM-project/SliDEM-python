# Create object
import stsa
import os
import geopandas as gpd
import json
from shapely.geometry import shape, GeometryCollection

# Call aoi as a shapely geometry
aoi = "home/data/aoi/Alta.geojson"
with open(aoi) as f:
  features = json.load(f)["features"]

aoishp = GeometryCollection([shape(feature["geometry"]).buffer(0) for feature in features])

# Extract subswaths geometries
# Calling an internal method to avoid writing to json and reloading
data = "home/data/s1"
img1 = "S1A_IW_SLC__1SDV_20190810T155114_20190810T155141_028509_03390E_9F11"
img2 = "S1B_IW_SLC__1SDV_20190816T155043_20190816T155110_017613_02122D_39CD"

s1_img1 = stsa.TopsSplitAnalyzer(target_subswaths=['iw1', 'iw2', 'iw3'], polarization='vv')
s1_img1.load_data(zip_path=os.path.join(data, img1 + '.zip'))
s1_img1._create_subswath_geometry()
s1df = s1_img1.df

s1df = s1df[s1df.intersects(aoishp)]
# s1_img1.to_json(os.path.join(data, img1 + '.json'))

s1_img2 = stsa.TopsSplitAnalyzer(target_subswaths=['iw1', 'iw2', 'iw3'], polarization='vv')
s1_img2.load_data(zip_path=os.path.join(data, img2 + '.zip'))
s1_img2._create_subswath_geometry()
print(s1_img2.df)
# print(s1_img2.to_json())
# s1_img2.to_json(os.path.join(data, img2 + '.json'))

