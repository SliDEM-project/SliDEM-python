# To download SRTM data as a base for an accuracy assessment:
# https://github.com/bopen/elevation
#
# Find ways also for copernicus DEM, the idea would be that
# if the user used one for generating the DEM then the other
# one should be used for accuracy assessment.
#
# External DEMs should also be supported
# Most likely this script will need to run with a conda environment
# check how to do that here: https://stackoverflow.com/a/64771620/12118669

import argparse
from bmi_topography import Topography
import os.path
from dotenv import load_dotenv
import geopandas as gpd
import json
from shapely.geometry import shape, GeometryCollection
import xdem
import geoutils as gu
import numpy as np
import matplotlib.pyplot as plt

# Arguments
parser = argparse.ArgumentParser(
    description='''Perform an accuracy assessment of the S1-DEMs.
    One can pass an external DEM for comparison or download locally
    a subset of a global DEM through the OpenTopography API. 
    Note that for the later you require to create a free account and API key.
''',
    epilog='''
Versions: 
  v0.0.1 - 08/2022 - First implementation
Authors:
  Lorena Abad - University of Salzburg - lorena.abad@plus.ac.at''',
    formatter_class=argparse.RawTextHelpFormatter
)
parser.add_argument(
    '--output_dir',
    type=str,
    default='data',
    required=True,
    help='''relative path (refers to mounted volume) to the directory where'
  results should be written into'''
)
parser.add_argument(
    '--unstable_area_path',
    type=str,
    help='''path to GeoJSON file (WGS84 - EPSG:4326) with the outline for unstable areas
    (e.g. mass movement areas). This can include any other area that should be 
    ignored during accuracy assessment (e.g. water areas, dense vegetation, etc.).
    If absent then the whole AOI is used for error analysis.'''
)
parser.add_argument(
    '--s1_dem_path',
    type=str,
    required=True,
    help='''path to S1-based DEM to be assessed for errors.'''
)
parser.add_argument(
    '--external_ref_dem',
    type=str,
    help='''path to external DEM to use for error assessment. 
    If you have already downloaded data previously from OpenTopography for 
    your area of interest, please add the path to the data here 
    and avoid re-fetching.'''
)
parser.add_argument(
    '--external_ref_dem_name',
    type=str,
    help='''shorter name for external DEM used. Used to determine output file names.'''
)
parser.add_argument(
    '--aoi_path',
    type=str,
    help='''path to GeoJSON file (WGS84 - EPSG:4326) with the study area outline.
    This area will be used to download a subset of the selected OpenTopography DEM.'''
)
parser.add_argument(
    '--ref_dem_download_dir',
    type=str,
    help='''relative path (refers to mounted volume) to the directory where'
  the reference DEM for the study area should be downloaded.'''
)
parser.add_argument(
    '--opentopoapikey',
    type=str,
    default=None,
    help='''API key to download data from the OpenTopography API. 
    Can also be saved to the .env file under OPENTOPOGRAPHY_API_KEY.
    More information here: 
    https://opentopography.org/blog/introducing-api-keys-access-opentopography-global-datasets'''
)
parser.add_argument(
    '--ref_dem',
    type=str,
    default='NASADEM',
    help='''string referring to which DEM to use for error assessment. 
    Can refer to any of the options provided by the OpenTopography API 
    (https://bmi-topography.readthedocs.io/en/latest/). 
    But of course, make sure the data you use overlaps your study area.'''
)
parser.add_argument(
    '--ref_dem_download',
    type=bool,
    default=False,
    help='''Boolean to confirm actively for data download from the OpenTopography API.
    If you already downloaded the reference DEM for your AOI please call it with the
    external_dem argument instead of saturating the API.'''
)
parser.add_argument(
    '--elev_diff_min_max',
    type=float,
    default=20,
    help='''To plot elevation differences,
     what should be the minimum and maximum elevation difference value? 
     Defaults to -20, +20.'''
)
args = parser.parse_args()

os.chdir('home/')

if os.path.isfile('.env'):
    load_dotenv('.env')
    api_key = os.environ.get('OPENTOPOGRAPHY_API_KEY')
else:
    api_key = args.opentopoapikey

# Download reference DEM data
if args.ref_dem_download:
    def read_aoi(aoi=args.aoi_path, buffer=0):
        tempgeojson = os.path.join(args.output_dir, "temp_aoi.geojson")
        aoidf = gpd.read_file(aoi)
        if aoidf.crs != 'epsg:4326':
            aoidf = aoidf.to_crs(4326)
            aoidf.to_file(tempgeojson, driver="GeoJSON")
            aoi_file = tempgeojson
        else:
            aoi_file = aoi
        # Read aoi with shapely
        with open(aoi_file) as f:
            features = json.load(f)["features"]

        if os.path.exists(tempgeojson):
            os.remove(tempgeojson)

        return GeometryCollection(
            [shape(feature["geometry"]).buffer(buffer) for feature in features]
        )


    aoi_bound = read_aoi()

    topo = Topography(
        dem_type=args.ref_dem,
        west=aoi_bound.bounds[0],  # minx
        south=aoi_bound.bounds[1],  # miny
        east=aoi_bound.bounds[2],  # maxx
        north=aoi_bound.bounds[3],  # maxy
        output_format="GTiff",
        cache_dir=args.ref_dem_download_dir
    )

    fname = topo.fetch()
    print(
        'Reference DEM data (', args.ref_dem,
        ') for your AOI was downloaded here:', fname
    )

    reference_dem_path = fname
else:
    reference_dem_path = args.external_ref_dem

# Naming for files

if args.external_ref_dem_name is None:
    external_ref_dem_name = args.external_ref_dem.split('/', -1)[-1].replace('.tif', '')
else:
    external_ref_dem_name = args.external_ref_dem_name

s1_dem_name = args.s1_dem_path.split('/', -1)[-1].replace('.tif', '')

# Error assessment with xdem
reference_dem = xdem.DEM(reference_dem_path)
s1_dem = xdem.DEM(args.s1_dem_path)

# Reproject reference DEM to S1 DEM
reference_dem = reference_dem.reproject(s1_dem)

# Calculate DEM error (dh)
dh = reference_dem - s1_dem
dh_file = os.path.join(
    args.output_dir,
    "elevation_diff_" + external_ref_dem_name +
    "_S1_" + s1_dem_name + ".tif"
)
dh.save(dh_file)

# Unstable areas
unstable = gu.Vector(args.unstable_area_path)

# Plot
plt.figure(figsize=(8, 5))
plt_extent = [
    dh.bounds.left,
    dh.bounds.right,
    dh.bounds.bottom,
    dh.bounds.top,
]
ax = plt.gca()
unstable.ds.plot(ax=ax, fc='none', ec='tab:gray')
ax.plot([], [], color='tab:gray', label='Unstable areas')
plt.imshow(
    dh.data.squeeze(), cmap="RdYlBu",
    vmin=-args.elev_diff_min_max,
    vmax=args.elev_diff_min_max,
    extent=plt_extent
)
cbar = plt.colorbar()
cbar.set_label('Elevation difference (m)\nReference - S1-DEM')
plt.legend(loc='lower right')
plt.savefig(
    os.path.join(
        args.output_dir,
        "elevation_diff_" + external_ref_dem_name +
        "_S1_" + s1_dem_name + ".png"
    ),
    dpi=300, bbox_inches='tight'
)

dh = gu.Raster(dh_file)
mask = ~unstable.create_mask(dh)

# Keep only stable terrain data
dh.set_mask(np.invert(mask))

# Compute slope and curvature for reference DEM in stable areas
slope, planc, profc, aspect = \
    xdem.terrain.get_terrain_attribute(
        dem=reference_dem.data,
        resolution=dh.res,
        attribute=['slope', 'planform_curvature', 'profile_curvature', 'aspect']
    )

# Estimate the measurement error by bin of slope, using the NMAD as robust estimator
df_ns = xdem.spatialstats.nd_binning(
    dh.data.ravel(), list_var=[slope.ravel(), aspect.ravel()],
    list_var_names=['slope', 'aspect'],
    statistics=['count', xdem.spatialstats.nmad], list_var_bins=30
)

xdem.spatialstats.plot_1d_binning(
    df_ns, 'slope', 'nmad',
    'Slope (degrees) calculated from Reference DEM',
    'Elevation error: NMAD (m)'
)

plt.savefig(
    os.path.join(
        args.output_dir,
        "elevation_diff_" + external_ref_dem_name +
        "_S1_" + s1_dem_name + "_binned_slope.png"
    ),
    dpi=300, bbox_inches='tight'
)

xdem.spatialstats.plot_1d_binning(
    df_ns, 'aspect', 'nmad',
    'Aspect (degrees) calculated from Reference DEM',
    'Elevation error: NMAD (m)'
)

plt.savefig(
    os.path.join(
        args.output_dir,
        "elevation_diff_" + external_ref_dem_name +
        "_S1_" + s1_dem_name + "_binned_aspect.png"
    ),
    dpi=300, bbox_inches='tight'
)

# Compute measures
# Write user settings to log file
file = open(os.path.join(args.output_dir, 'error_measures_' + external_ref_dem_name + '.txt'), 'w')
file.write(
    'S1 DEM: ' + args.s1_dem_path + '\n' +
    'Reference DEM: ' + args.external_ref_dem + '\n' +
    '\nReference DEM - S1 DEM:\n' +
    'Error measures \n================= \n'+
    'Min: {:.2f} meters.'.format(np.nanmin(dh.data)) + '\n' +
    'Max: {:.2f} meters.'.format(np.nanmax(dh.data)) + '\n' +
    'Mean: {:.2f} meters.'.format(np.nanmean(dh.data)) + '\n' +
    'STD: {:.2f} meters.'.format(np.nanstd(dh.data)) + '\n' +
    'MAE: {:.2f} meters.'.format(np.nanmean(np.abs(dh.data))) + '\n' +
    'RMSE: {:.2f} meters.'.format(np.sqrt((dh.data**2).mean())) + '\n' +
    'NMAD: {:.2f} meters.'.format(xdem.spatialstats.nmad(dh.data)) + '\n'
)
file.close
