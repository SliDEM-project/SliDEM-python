import argparse
from bmi_topography import Topography
import os.path
from dotenv import load_dotenv
import geopandas as gpd
import json
from shapely.geometry import shape, GeometryCollection
from tqdm.auto import tqdm  # provides a progressbar

# Arguments
parser = argparse.ArgumentParser(
    description='''Auxiliary script to download reference DEM data
    through the OpenTopography API and WorldCover landuse/landcover 
    data for your AOI. These can then be used for the accuracy assessment. 
    Note that for the OpenTopography data you require to create 
    a free account and get API key.
    More information here: 
    https://opentopography.org/blog/introducing-api-keys-access-opentopography-global-datasets
''',
    epilog='''
Versions: 
  v0.0.1 - 08/2022 - First implementation
Authors:
  Lorena Abad - University of Salzburg - lorena.abad@plus.ac.at''',
    formatter_class=argparse.RawTextHelpFormatter
)
parser.add_argument(
    '--aoi_path',
    type=str,
    help='''path to GeoJSON file (WGS84 - EPSG:4326) with the study area outline.
    This area will be used to download a subset of the selected OpenTopography DEM.'''
)
parser.add_argument(
    '--download_dir',
    default='data',
    type=str,
    help='''relative path (refers to mounted volume) to the directory where'
  the reference DEM and LULC data for the study area should be downloaded.'''
)
parser.add_argument(
    '--opentopo_apikey',
    type=str,
    default=None,
    help='''API key to download data from the OpenTopography API. 
    Can also be saved to the .env file under OPENTOPOGRAPHY_API_KEY.
    More information here: 
    https://opentopography.org/blog/introducing-api-keys-access-opentopography-global-datasets'''
)
parser.add_argument(
    '--ref_dem_opentopo',
    type=str,
    default='NASADEM',
    help='''string referring to which DEM to use for error assessment. 
    Can refer to any of the options provided by the OpenTopography API 
    (https://bmi-topography.readthedocs.io/en/latest/). 
    But of course, make sure the data you use overlaps your study area.'''
)
parser.add_argument(
    '--ref_dem_opentopo_download',
    type=bool,
    default=False,
    help='''Boolean to confirm actively for data download from the OpenTopography API.
    If you already downloaded the reference DEM for your AOI, please call it with the
    ref_dem_path argument instead of saturating the API.'''
)
parser.add_argument(
    '--lulc_worldcover_download',
    type=bool,
    default=False,
    help='''Boolean to confirm actively for WorldCover data download from the AWS S3 bucket.
    If you already downloaded the WorldCover data for your AOI, please call it with the
    lulc_path argument instead of saturating the API.'''
)
args = parser.parse_args()

os.chdir('home/')

if os.path.isfile('.env'):
    load_dotenv('.env')
    api_key = os.environ.get('OPENTOPOGRAPHY_API_KEY')
else:
    api_key = args.opentopo_apikey


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


# Download reference DEM data
if args.ref_dem_opentopo_download:
    aoi_bound = read_aoi()

    topo = Topography(
        dem_type=args.ref_dem_opentopo,
        west=aoi_bound.bounds[0],  # minx
        south=aoi_bound.bounds[1],  # miny
        east=aoi_bound.bounds[2],  # maxx
        north=aoi_bound.bounds[3],  # maxy
        output_format="GTiff",
        cache_dir=args.download_dir
    )

    fname = topo.fetch()
    print(
        'Reference DEM data (', args.ref_dem_opentopo,
        ') for your AOI was downloaded here:', fname
    )

if args.lulc_worldcover_download:
    # Download WorldCover data
    s3_url_prefix = "https://esa-worldcover.s3.eu-central-1.amazonaws.com"

    # Get geometry from AOI
    geom = read_aoi()

    # load worldcover grid
    url = f'{s3_url_prefix}/v100/2020/esa_worldcover_2020_grid.geojson'
    grid = gpd.read_file(url)

    # get grid tiles intersecting AOI
    tiles = grid[grid.intersects(geom)]

    for tile in tqdm(tiles.ll_tile):
        url = f'{s3_url_prefix}/v100/2020/map/ESA_WorldCover_10m_2020_v100_{tile}_Map.tif\n'
        print(
            'Please copy this URL into your web browser\n'
            'to download your WorldCover tile:', url,
            '\n PS. I know it is annoying but I cannot'
            ' figure out why requests does not work'
        )
        # r = requests.get(url, allow_redirects=True)
        # out_fn = f'{args.download_dir}/ESA_WorldCover_10m_2020_v100_{tile}_Map.tif'
        # with open(out_fn, 'wb') as f:
        #     f.write(r.content)
