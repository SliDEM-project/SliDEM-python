# -*- coding: utf-8 -*-

# Import modules
import argparse
import glob
import geopandas as gpd
import json
import numpy as np
import os
import pandas as pd
from shapely.geometry import shape, GeometryCollection
from snappy import ProductIO, jpy, GPF
import stsa
import subprocess

# Arguments
parser = argparse.ArgumentParser(
    description='''Generate DEMs based on Sentinel-1 image pairs. 
This module will go through four processing pipelines, which
output different intermediate steps within the workflow,
including interferogram and coherence layers.
Each pipeline results in a different directory within the output
directory set in the arguments. 

The `query_result` file from the previous steps, should have been edited
by the user to change the Download column to TRUE for those pair of scenes
that seem suitable for processing, since this script loops over this file. 
''',
    epilog='''
Versions: 
  v0.0.1 - 06/2022 - Generate DEMs from S1
Authors:
  Lorena Abad - University of Salzburg - lorena.abad@plus.ac.at''',
    formatter_class=argparse.RawTextHelpFormatter
)
parser.add_argument(
    '--download_dir',
    type=str,
    default='data',
    required=True,
    help='''relative path (refers to mounted volume) to the directory
  where S1 scenes were downloaded'''
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
    '--query_result',
    type=str,
    help='''path to the CSV file with query results from 0_query_s1.py. 
  Should be located in the specified download_dir, and should have been 
  edited to set Download=True where relevant.'''
)
parser.add_argument(
    '--pair_index',
    type=int,
    default=0,
    help='''refers to the query_result CSV file, where the rows with Download=True
  are filtered out to get a list of the image pairs to process. 
  Set the index to indicate which row to process next.
  Defaults to the first pair (pair_index=0)'''
)
parser.add_argument(
    '--pair_ids',
    nargs="+",
    default=None,
    help='''what are the scene IDs to process, in a list form. Ignored when query_result
    and pair_index are given.'''
)
parser.add_argument(
    '--aoi_path',
    type=str,
    required=True,
    help='''path to GeoJSON file (WGS84 - EPSG:4326) with the
    study area outline. This is used to extract the subswaths and
    bursts automatically and to subset the area if desired.'''
)
parser.add_argument(
    '--polarization',
    type=str,
    default="VV",
    help='''Set polarization to use, defaults to VV.'''
)
parser.add_argument(
    '--dem',
    type=str,
    default="Copernicus 30m Global DEM",
    help='''Set DEM for back-geocoding. 
    Defaults to `Copernicus 30m Global DEM`.
    To choose from: `SRTM 3Sec`, `SRTM 1Sec HGT`,
     `GETASSE30`, `CDEM`'''
)
parser.add_argument(
    '--no_subset',
    action='store_false',
    help='''Call this flag if the process should 
    be performed in the whole AOI? Otherwise it will create 
    additionally a subset corresponding to the
    given AOI.'''
)
parser.add_argument(
    '--aoi_buffer',
    type=float,
    default=0,
    help='''If subsetting the area to the AOI, should a 
    buffer around it be drawn? How big? Defaults to 0'''
)
parser.add_argument(
    '--no_output_projected',
    action='store_false',
    help='''Call this flag if the final outputs should 
    be in WGS84. Otherwise it will project them in WGS84/UTM.'''
)
parser.add_argument(
    '--ifg_indwinsize',
    action='store_false',
    help='''Call this flag if the resulting interferogram should have 
    independent window sizes otherwise, it will have squared pixel size'''
)
parser.add_argument(
    '--ifg_cohwin_rg',
    type=int,
    default=10,
    help='''Coherence range window size (defaults to 10)'''
)
parser.add_argument(
    '--ifg_cohwin_az',
    type=int,
    default=2,
    help='''Coherence azimuth window size
     (defaults to 2, when --ifg_indwinsize is called)'''
)
parser.add_argument(
    '--no_multilook',
    action='store_false',
    help='''Should multilooking be skipped?'''
)
parser.add_argument(
    '--multilook_range',
    type=int,
    default=6,
    help='''Number of multilook range, defaults to 6'''
)
parser.add_argument(
    '--no_goldstein',
    action='store_false',
    help='''Should Goldstein filtering be skipped?'''
)
parser.add_argument(
    '--gpf_fftsize',
    type=int,
    default=64,
    help='''FFT size, defaults to 64. Options 32, 64, 128, 256'''
)
parser.add_argument(
    '--gpf_win',
    type=int,
    default=3,
    help='''FFT window size, defaults to 3. Options: 3, 5, 7'''
)
parser.add_argument(
    '--gpf_cohmask',
    action='store_true',
    help='''Use coherence mask?'''
)
parser.add_argument(
    '--gpf_cohth',
    type=float,
    default=0.2,
    help='''If coherence mask is used, what should be the threshold? 
    Between 0 and 1, Defaults to 0.2'''
)
parser.add_argument(
    '--snaphu_costmode',
    type=str,
    default='TOPO',
    help='''Cost mode parameter for snaphu export. 
    Either TOPO or SMOOTH are viable options.
    DEFO is for deformation and not recommended.
    Defaults to TOPO'''
)
parser.add_argument(
    '--snaphu_tiles',
    type=int,
    default=1,
    help='''Number of tiles parameter for snaphu export. 
    (Usually increasing this argument causes problems).
    Defaults to 1'''
)
parser.add_argument(
    '--snaphu_tile_overlap_row',
    type=float,
    default=200,
    help='''If more than one tile is set, what should the overlap
    between tiles be for the rows. Ignored when snaphu_tiles = 1.
    Defaults to 200'''
)
parser.add_argument(
    '--snaphu_tile_overlap_col',
    type=float,
    default=200,
    help='''If more than one tile is set, what should the overlap
    between tiles be for the columns. 
    Defaults to 200'''
)
parser.add_argument(
    '--pixel_size',
    type=float,
    default=30.0,
    help='''When applying terrain correction, what pixel size to use, defaults to 30'''
)
parser.add_argument(
    '--no_data_value',
    type=float,
    default=-99999,
    help='''Value to use for no data, defaults to -99999'''
)
parser.add_argument(
    '--coherence_threshold',
    type=float,
    default=0.15,
    help='''Minimum coherence value to export valid elevation pixels, defaults to 0.15'''
)
parser.add_argument(
    '--pipelines',
    nargs="+",
    default=['P1', 'P2', 'P3'],
    help='''Which pipelines to run, defaults to all.
    Pipeline 1: generates interferogram
    Pipeline 2: performs snaphu unwrapping
    Pipeline 3: generates DEM.
    Useful for debugging.'''
)
args = parser.parse_args()

# Set home as current directory
os.chdir('home/')

# Read in image pairs
if args.query_result is not None:
    products = pd.read_csv(
        os.path.join(args.download_dir, args.query_result),
        sep=None, engine='python'
    )
    productsIn = products[products['Download']]

    prodRefDate = productsIn.iloc[args.pair_index]['ReferenceDate']
    prodMatDate = productsIn.iloc[args.pair_index]['MatchDate']
    prodRefId = productsIn.iloc[args.pair_index]['ReferenceID']
    prodMatId = productsIn.iloc[args.pair_index]['MatchID']
elif args.pair_ids is not None:
    prodRefId = args.pair_ids[0]
    prodRefDate = pd.to_datetime(
        prodRefId[17:25],
        format='%Y%m%d'
    )
    prodMatId = args.pair_ids[1]
    prodMatDate = pd.to_datetime(
        prodMatId[17:25],
        format='%Y%m%d'
    )
else:
    raise ValueError("You need to provide either the "
                     "path to the query_result CSV file "
                     "or a list containing pair_ids")

# Set image order
# "before" image .zip
if pd.to_datetime(prodRefDate) < pd.to_datetime(prodMatDate):
    file_path_1 = os.path.join(args.download_dir, prodRefId + '.zip')
else:
    file_path_1 = os.path.join(args.download_dir, prodMatId + '.zip')
# "after" image .zip
if pd.to_datetime(prodMatDate) > pd.to_datetime(prodRefDate):
    file_path_2 = os.path.join(args.download_dir, prodMatId + '.zip')
else:
    file_path_2 = os.path.join(args.download_dir, prodRefId + '.zip')

ref_date_str = pd.to_datetime(
    prodRefDate,
    yearfirst=False,
    dayfirst=True
)
mat_date_str = pd.to_datetime(
    prodMatDate,
    yearfirst=False,
    dayfirst=True
)

# Create output_dir if not existing
if not os.path.exists(args.output_dir):
    os.mkdir(args.output_dir)

# Output directory with date parenthesis
date_bundle = ref_date_str.strftime('%Y%m%d') + '_' + \
              mat_date_str.strftime('%Y%m%d')
output_dir = os.path.join(args.output_dir, 'out_' + date_bundle)
if not os.path.exists(output_dir):
    os.mkdir(output_dir)

# Get some metadata from the CSV file:
ref_date = ref_date_str.strftime('%d/%m/%Y')
mat_date = mat_date_str.strftime('%d/%m/%Y')

# Hashmap is used to give us access to all JAVA operators
HashMap = jpy.get_type('java.util.HashMap')
parameters = HashMap()


# Functions:
# From this section I define a set of functions that are called
# within a pipeline at the end of the script. Each function will start with a
# comment saying what it does, and will include an indicator as to which
# pipeline it belongs to (P1, P2, P3, P4)


# [P1|P2] Function to read AOI
def read_aoi(aoi, buffer):
    tempgeojson = os.path.join(args.download_dir, "temp_aoi.geojson")
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


# [P1] Function to get subswaths and bursts
def get_swath_burst(filename, aoi, polar=args.polarization, product_idx=1):
    print('Extracting subswath and bursts for AOI...')
    aoi_geom = read_aoi(aoi, buffer=args.aoi_buffer)

    # Apply Top Split Analyzer to S1 file with stsa
    # Initialize object
    img = stsa.TopsSplitAnalyzer(
        target_subswaths=['iw1', 'iw2', 'iw3'],
        polarization=polar.lower()
    )
    # Load zip file
    img.load_data(zip_path=filename)
    #  Create geodataframe with subswaths, bursts and geoms
    #  Calling an internal method to avoid writing to json and reloading
    img._create_subswath_geometry()
    img_df = img.df

    # Intersect geodataframe with aoi
    img_df = img_df[img_df.intersects(aoi_geom)].reset_index()

    # Return intersecting subswaths and bursts
    df = img_df[['subswath', 'burst']]
    df['burst_idx'] = df.groupby('subswath').cumcount()
    if product_idx == 1:
        df['burst_idx'] = np.where(df['burst_idx'] == 0, "firstBurstIndex_1",
                                   np.where(df['burst_idx'] == 1, "lastBurstIndex_1", "ignore"))
        df = df.pivot(index='subswath', columns='burst_idx', values='burst') \
            .rename_axis(columns=None).reset_index()
        if 'lastBurstIndex_1' not in df.columns:
            df['lastBurstIndex_1'] = np.nan
        return df
    else:
        df['burst_idx'] = np.where(df['burst_idx'] == 0, "firstBurstIndex_2",
                                   np.where(df['burst_idx'] == 1, "lastBurstIndex_2", "ignore"))
        df = df.pivot(index='subswath', columns='burst_idx', values='burst') \
            .rename_axis(columns=None).reset_index()
        if 'lastBurstIndex_2' not in df.columns:
            df['lastBurstIndex_2'] = np.nan
        return df


# [P1|P2|P3|P4] Function to read the .zip file into SNAP
def read(filename):
    print('Reading...')
    return ProductIO.readProduct(filename)


# [P1|P2|P3] Function to write SNAP product to GeoTIFF
def write_TIFF_format(product, filename):
    ProductIO.writeProduct(product, filename, "GeoTiff")


# [P1|P2|P3] Function to write SNAP product to BEAM-DIMAP format
def write_BEAM_DIMAP_format(product, filename):
    print('Saving BEAM-DIMAP format.')
    ProductIO.writeProduct(product, filename + '.dim', 'BEAM-DIMAP')


# [P2] Function to apply TOPSAR split with SNAP
def topsar_split(product, IW, firstBurstIndex, lastBurstIndex, polar=args.polarization):
    print('Applying TOPSAR Split...')
    parameters.put('subswath', IW)
    parameters.put('firstBurstIndex', firstBurstIndex)
    parameters.put('lastBurstIndex', lastBurstIndex)
    parameters.put('selectedPolarisations', polar)
    output = GPF.createProduct("TOPSAR-Split", parameters, product)
    return output


# [P2] Function to apply Orbit file with SNAP
def apply_orbit_file(product):
    print('Applying orbit file...')
    parameters.put("Orbit State Vectors", "Sentinel Precise (Auto Download)")
    parameters.put("Polynomial Degree", 3)
    parameters.put("Do not fail if new orbit file is not found", True)
    return GPF.createProduct("Apply-Orbit-File", parameters, product)


# [P2] Function to do back geocoding with SNAP
def back_geocoding(product, dem):
    print('Back geocoding...')
    parameters.put("demName", dem)
    parameters.put("demResamplingMethod", "BILINEAR_INTERPOLATION")
    parameters.put("resamplingType", "BILINEAR_INTERPOLATION")
    parameters.put("maskOutAreaWithoutElevation", True)
    parameters.put("outputDerampDemodPhase", True)
    parameters.put("disableReramp", False)
    return GPF.createProduct("Back-Geocoding", parameters, product)


# [P2] Function to apply Enhanced Spectral Diversity with SNAP
def enhanced_spectral_diversity(product):
    print('Applying Enhanced Spectral Diversity...')
    # called with defaults
    # should only be applied if multiple bursts were used in topsar_split
    return GPF.createProduct("Enhanced-Spectral-Diversity", parameters, product)


# [P2] Function for TOPSAR deburst with SNAP
def topsar_deburst(sources):
    print('Running TOPSAR deburst...')
    parameters.put("Polarisations", args.polarization)
    output = GPF.createProduct("TOPSAR-Deburst", parameters, sources)
    return output


# [P2] Function to calculate the interferogram with SNAP
def interferogram(product, ifg_indwinsize, ifg_cohwin_az, ifg_cohwin_rg):
    print('Creating interferogram...')
    parameters.put("Subtract flat-earth phase", True)
    parameters.put("Degree of \"Flat Earth\" polynomial", 5)
    parameters.put("Number of \"Flat Earth\" estimation points", 501)
    parameters.put("Orbit interpolation degree", 3)
    parameters.put("Include coherence estimation", True)
    parameters.put("Square Pixel", not ifg_indwinsize)
    parameters.put("Independent Window Sizes", ifg_indwinsize)
    parameters.put("Coherence Range Window Size", ifg_cohwin_rg)
    parameters.put("Coherence Azimuth Window Size", ifg_cohwin_az)
    return GPF.createProduct("Interferogram", parameters, product)


# [P2] Function for TOPSAR merge with SNAP
def topsar_merge(sources):
    print('Running TOPSAR merge...')
    parameters.put("selectedPolarisations", args.polarization)
    output = GPF.createProduct("TOPSAR-Merge", parameters, sources)
    return output


# [P2] Function for topophase removal (optional) with SNAP
def topophase_removal(product, dem):
    parameters.put("Orbit Interpolation Degree", 3)
    parameters.put("demName", dem)
    parameters.put("Tile Extension[%]", 100)
    parameters.put("Output topographic phase band", True)
    parameters.put("Output elevation band", False)
    return GPF.createProduct("TopoPhaseRemoval", parameters, product)


# [P2] Function for multilooking (optional) with SNAP
# Multi-looking is used to reduce resolution.
# ML_nRgLooks stands for number of range looks
# grSquarePixel is set to True to default to a square pixel,
# hence the number of azimuth looks is automatically calculated.
# https://forum.step.esa.int/t/alterring-spatial-resolution-of-sentinel-1-image/21906/7
def multilook(product, ML_nRgLooks):
    print('Multi-looking...')
    parameters.put('grSquarePixel', True)
    parameters.put("nRgLooks", ML_nRgLooks)  # half of range looks on metadata
    output = GPF.createProduct("Multilook", parameters, product)
    return output


# [P2] Function to apply Goldstein phase filtering (optional) with SNAP
def goldstein_phase_filter(product, gpf_fftsize, gpf_win,
                           gpf_cohmask, gpf_cohth):
    print('Applying Goldstein phase filtering...')
    parameters.put("Adaptive Filter Exponent in(0,1]:", 1.0)
    parameters.put("FFT Size", gpf_fftsize)
    parameters.put("Window Size", gpf_win)
    parameters.put("Use coherence mask", gpf_cohmask)
    parameters.put("Coherence Threshold in[0,1]:", gpf_cohth)
    return GPF.createProduct("GoldsteinPhaseFiltering", parameters, product)


# [P2] Function to create a subset with SNAP
def subset(source, aoi, buffer):
    print('Subsetting...')
    wkt = read_aoi(aoi, buffer).wkt
    parameters.put('geoRegion', wkt)
    parameters.put('copyMetadata', True)
    output = GPF.createProduct('Subset', parameters, source)
    return output


# [P3] Function to export to snaphu
def snaphu_export(product, snaphu_exp_folder, tiles, cost_mode, tile_overlap_row, tile_overlap_col):
    print("Exporting to SNAPHU format...")
    parameters.put('targetFolder', snaphu_exp_folder)
    parameters.put('statCostMode', cost_mode)
    parameters.put('initMethod', 'MCF')
    parameters.put('numberOfTileCols', tiles)
    parameters.put('numberOfTileRows', tiles)
    parameters.put('rowOverlap', tile_overlap_row)
    parameters.put('colOverlap', tile_overlap_col)
    parameters.put('numberOfProcessors', 4)
    parameters.put('tileCostThreshold', 500)
    output = GPF.createProduct('SnaphuExport', parameters, product)
    ProductIO.writeProduct(output, snaphu_exp_folder, 'Snaphu')
    return output


# [P3] Function for snaphu unwrapping
# Unwrapping code adapted from:
# https://forum.step.esa.int/t/snaphu-read-error-due-to-non-ascii-unreadable-file/14374/4
def snaphu_unwrapping(snaphu_exp_folder):
    print('Unwrapping...')
    infile = os.path.join(snaphu_exp_folder, "snaphu.conf")
    with open(str(infile)) as lines:
        line = lines.readlines()[6]
        snaphu_string = line[1:].strip()
        snaphu_args = snaphu_string.split()
    print("\nCommand sent to snaphu:\n", snaphu_string)
    process = subprocess.Popen(snaphu_args, cwd=str(snaphu_exp_folder))
    process.communicate()
    process.wait()

    unw_img_file = glob.glob(os.path.join(output_dir, str("out_P3_snaphu" + "/UnwPhase*.img")))
    if not unw_img_file:
        raise ValueError("Snaphu unwrapping failed. Pipeline [P3] incomplete.")

    unwrapped_list = glob.glob(str(snaphu_exp_folder) + "/UnwPhase*.hdr")
    unwrapped_hdr = str(unwrapped_list[0])
    unwrapped_read = ProductIO.readProduct(unwrapped_hdr)
    fn = os.path.join(snaphu_exp_folder, "unwrapped")
    write_BEAM_DIMAP_format(unwrapped_read, fn)
    print('Phase unwrapping performed successfully.')


# [P4] Function to import snaphu object
def snaphu_import(product, unwrapped):
    print('Importing snaphu product...')
    snaphu_files = jpy.array('org.esa.snap.core.datamodel.Product', 2)
    snaphu_files[0] = product
    snaphu_files[1] = unwrapped
    output = GPF.createProduct("SnaphuImport", parameters, snaphu_files)
    return output


# [P4] Function to transform phase to elevation
def phase_to_elev(unwrapped_product, dem):
    print('Converting phase to elevation...')
    parameters.put("demName", dem)
    output = GPF.createProduct("PhaseToElevation", parameters, unwrapped_product)
    return output


# [P4] Function to perform terrain correction
def terrain_correction(source, band=None, projected=None, pixel_size=None):
    print('Terrain correction...')
    parameters.put('demName', args.dem)
    parameters.put('imgResamplingMethod', 'BILINEAR_INTERPOLATION')
    if projected:
        parameters.put('mapProjection', 'AUTO:42001')
    # parameters.put('saveProjectedLocalIncidenceAngle', False)
    if band is not None:
        parameters.put('sourceBands', band)
    parameters.put('saveSelectedSourceBand', True)
    parameters.put('nodataValueAtSea', False)
    parameters.put('pixelSpacingInMeter', pixel_size)
    output = GPF.createProduct('Terrain-Correction', parameters, source)
    return output


# [P4] Function to combine two products
def collocate(product1, product2):
    print('Collocating two products...')
    sourceProducts = HashMap()
    sourceProducts.put('master', product1)
    sourceProducts.put('slave', product2)
    parameters.put('renameMasterComponents', False)
    parameters.put('renameSlaveComponents', False)
    output = GPF.createProduct("Collocate", parameters, sourceProducts)
    return output


# [P4] Function to set no data value for several bands
def set_no_data(product, bands, ndval):
    for b in bands:
        product.getBand(b).setGeophysicalNoDataValue(ndval)
        product.getBand(b).setNoDataValueUsed(True)
    return product


# [P4] Function to select band
def band_select(product, bands):
    parameters = HashMap()
    parameters.put('sourceBands', bands)
    output = GPF.createProduct('Subset', parameters, product)
    return output


# [P4] Filter elevation pixels by coherence threshold
def filter_elevation(product, elev_band, coh_band, coh_th, nodata):
    bandmath_expression = 'if ' + coh_band + ' > ' + str(coh_th) + \
                          ' then ' + elev_band + ' else ' + str(nodata)
    product.getBand(elev_band)
    BandDescriptor = jpy.get_type('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor')
    targetBand1 = BandDescriptor()
    targetBand1.name = elev_band + '_filtered_cohth_' + str(coh_th)
    targetBand1.type = 'float32'
    targetBand1.expression = bandmath_expression
    targetBands = jpy.array('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor', 1)
    targetBands[0] = targetBand1
    parameters = HashMap()
    parameters.put('targetBands', targetBands)
    output = GPF.createProduct('BandMaths', parameters, product)
    print(bandmath_expression)
    return output


# Pipe functions
# Pipeline 1 [P1]:
def run_P1_interferogram(out_dir, file1, file2, polarization, aoi=None,
                         topophaseremove=False, dem=None,
                         ifg_squarepixel=None, ifg_cohwin_rg=None,
                         ifg_cohwin_az=None,
                         multilooking=None, ml_rangelooks=None,
                         goldsteinfiltering=None,
                         gpf_fftsize=None, gpf_win=None,
                         gpf_cohmask=None, gpf_cohth=None,
                         subsetting=None, subset_buffer=None):
    # Write user settings to log file
    file = open(os.path.join(out_dir, 'log.txt'), 'w')
    file.write(
        'USER-SETTINGS FOR PIPELINE 1:\n' +
        'ReferenceID path: ' + file1 + '\n' +
        'ReferenceID date: ' + ref_date + '\n' +
        'MatchID path: ' + file2 + '\n' +
        'MatchID date: ' + mat_date + '\n' +
        'Polarization: ' + polarization + '\n' +
        'DEM for back-geocoding: ' + dem + '\n'
    )
    file.close

    # Read files in
    product_1 = read(file1)
    product_2 = read(file2)

    # Get pass & orbit from the input files
    pass_metadata_p1 = product_1.getMetadataRoot() \
        .getElement('Abstracted_Metadata') \
        .getAttribute('PASS').getData()
    relorbit_metadata_p1 = product_1.getMetadataRoot(). \
        getElement('Abstracted_Metadata') \
        .getAttribute('REL_ORBIT').getData()
    pass_metadata_p2 = product_2.getMetadataRoot() \
        .getElement('Abstracted_Metadata') \
        .getAttribute('PASS').getData()
    relorbit_metadata_p2 = product_2.getMetadataRoot(). \
        getElement('Abstracted_Metadata') \
        .getAttribute('REL_ORBIT').getData()

    if str(pass_metadata_p1) != str(pass_metadata_p2) and \
            str(relorbit_metadata_p1) != str(relorbit_metadata_p2):
        raise ValueError("Image pair orbits and pass do not match.")

    # Apply stsa workflow
    stsa_1 = get_swath_burst(file1, aoi, polar=polarization, product_idx=1)
    stsa_2 = get_swath_burst(file2, aoi, polar=polarization, product_idx=2)

    if not list(set(stsa_1['subswath'])) == list(set(stsa_2['subswath'])):
        # subswaths should be the same because each of them is
        # processed separately.
        raise ValueError("Subswaths intersecting the AOI do not match.")
    else:
        stsa_df = stsa_1.join(stsa_2.set_index('subswath'), on='subswath')
        stsa_df.lastBurstIndex_1.fillna(stsa_df.firstBurstIndex_1, inplace=True)
        stsa_df.lastBurstIndex_2.fillna(stsa_df.firstBurstIndex_2, inplace=True)

    # Compute InSAR stack overview
    # import the stack operator
    # From: https://forum.step.esa.int/t/insar-dinsar-perpendicular-baseline-calculation/3776/34
    stack = jpy.get_type('org.esa.s1tbx.insar.gpf.coregistration.CreateStackOp')
    stack.getBaselines([product_1, product_2], product_1)
    # Now there is a new piece of metadata in product one called 'Baselines'
    baseline_root_metadata = product_1.getMetadataRoot(). \
        getElement('Abstracted_Metadata').getElement('Baselines')
    # Write to log all the baselines between all master/slave configurations
    file = open(os.path.join(out_dir, 'log.txt'), 'a')
    file.write(
        'Pass: ' + str(pass_metadata_p1) + '\n' +
        'Orbit: ' + str(relorbit_metadata_p1) + '\n'
    )
    file.write('\nCOMPUTED STACKS IN PIPELINE 1:')
    master_ids = list(baseline_root_metadata.getElementNames())
    for master_id in master_ids:
        slave_ids = list(baseline_root_metadata.getElement(master_id).getElementNames())
        for slave_id in slave_ids:
            file.write(f'\n{master_id}, {slave_id}\n')
            baseline_metadata = baseline_root_metadata.getElement(master_id).getElement(slave_id)
            for baseline in list(baseline_metadata.getAttributeNames()):
                file.write(f'{baseline}: {baseline_metadata.getAttributeString(baseline)}\n')
            file.write('')
    file.close

    # Proceed to SNAP workflow
    # Write user settings to log file
    file = open(os.path.join(out_dir, 'log.txt'), 'a')
    file.write(
        '\nUSER-SETTINGS FOR PIPELINE 1 (cont.):\n' +
        'Interferogram settings:'
        '- Square pixel: ' + str(ifg_squarepixel) + '\n' +
        '- Coherence range window size: ' + str(ifg_cohwin_rg) + '\n' +
        '- Coherence azimuth window size: ' + str(ifg_cohwin_az) + '\n' +
        'Multi-looking applied: ' + str(multilooking) + '\n' +
        '- Multi-looking range: ' + str(ml_rangelooks) + '\n' +
        'Goldstein filtering applied: ' + str(goldsteinfiltering) + '\n' +
        '- FFT size: ' + str(gpf_fftsize) + '\n' +
        '- Window size: ' + str(gpf_win) + '\n' +
        '- Coherence mask applied: ' + str(gpf_cohmask) + '\n' +
        '- Coherence mask threshold: ' + str(gpf_cohth) + '\n'
    )
    file.close

    def snap_single_iw(iw,
                       firstBurstIndex_1, firstBurstIndex_2,
                       lastBurstIndex_1, lastBurstIndex_2):
        # Write sub-swath and burst to log file
        file = open(os.path.join(out_dir, 'log.txt'), 'a')
        file.write(
            '\nAUTOMATICALLY EXTRACTED PARAMETERS IN PIPELINE 1:\n'
            'Subswath: ' + iw + '\n' +
            'Bursts 1: ' + str(firstBurstIndex_1) + ',' + str(lastBurstIndex_1) + '\n' +
            'Bursts 2: ' + str(firstBurstIndex_2) + ',' + str(lastBurstIndex_2) + '\n')
        file.close

        product_TOPSAR_1 = topsar_split(product_1, iw,
                                        firstBurstIndex_1, lastBurstIndex_1)
        product_TOPSAR_2 = topsar_split(product_2, iw,
                                        firstBurstIndex_2, lastBurstIndex_2)
        product_orbitFile_1 = apply_orbit_file(product_TOPSAR_1)
        product_orbitFile_2 = apply_orbit_file(product_TOPSAR_2)
        product = back_geocoding([product_orbitFile_1, product_orbitFile_2], dem)
        if lastBurstIndex_1 - firstBurstIndex_1 > 1 or \
                lastBurstIndex_2 - firstBurstIndex_2 > 1:
            product = enhanced_spectral_diversity(product)
        out_filename = os.path.join(out_dir, 'out_' + iw)
        write_BEAM_DIMAP_format(product, out_filename)

        # takes result from previous pipeline
        product = interferogram(product,
                                ifg_squarepixel, ifg_cohwin_rg, ifg_cohwin_az)
        product = topsar_deburst(product)
        return product

    if len(stsa_df) > 1:
        products = []
        for index, row in stsa_df.iterrows():
            product = snap_single_iw(
                iw=row['subswath'],
                firstBurstIndex_1=row['firstBurstIndex_1'],
                firstBurstIndex_2=row['firstBurstIndex_2'],
                lastBurstIndex_1=row['lastBurstIndex_1'],
                lastBurstIndex_2=row['lastBurstIndex_2']
            )
            products.append(product)
        product = topsar_merge(products)
    else:
        product = snap_single_iw(
            iw=stsa_df['subswath'].item(),
            firstBurstIndex_1=stsa_df['firstBurstIndex_1'].item(),
            firstBurstIndex_2=stsa_df['firstBurstIndex_2'].item(),
            lastBurstIndex_1=stsa_df['lastBurstIndex_1'].item(),
            lastBurstIndex_2=stsa_df['lastBurstIndex_2'].item()
        )

    if topophaseremove:
        product = topophase_removal(product, dem)
    if multilooking:
        product = multilook(product, ML_nRgLooks=ml_rangelooks)
    if goldsteinfiltering:
        product = goldstein_phase_filter(product,
                                         gpf_fftsize, gpf_win,
                                         gpf_cohmask, gpf_cohth)
    out_filename = os.path.join(out_dir, 'out_P1')
    write_BEAM_DIMAP_format(product, out_filename)
    if subsetting:
        product_ss = subset(product, aoi, buffer=subset_buffer)
        out_filename = os.path.join(out_dir, 'out_P1_subset')
        write_BEAM_DIMAP_format(product_ss, out_filename)
    print("Pipeline [P1] for interferogam creation complete")


# [P2]:
def run_P2_unwrap(out_dir, tiles, cost_mode, tile_overlap_row,
                  tile_overlap_col, subset=None):
    # Write user settings to log file
    file = open(os.path.join(out_dir, 'log.txt'), 'a')
    file.write(
        '\nUSER-SETTINGS FOR PIPELINE 2:\n' +
        'Tiles: ' + str(tiles) + '\n' +
        'Tiles overlap: row ' + str(tile_overlap_row) +
        ', col ' + str(tile_overlap_row) + '\n' +
        'Cost mode: ' + cost_mode + '\n'
    )
    file.close

    if subset:
        # takes subset result from previous pipeline
        in_filename = os.path.join(out_dir, 'out_P1_subset')
        product = read(in_filename + ".dim")  # reads .dim
    else:
        # takes result from previous pipeline
        in_filename = os.path.join(out_dir, 'out_P1')
        product = read(in_filename + ".dim")  # reads .dim
    out_dir_snaphu = os.path.join(output_dir, "out_P2_snaphu")
    snaphu_export(product, out_dir_snaphu, tiles, cost_mode,
                  tile_overlap_row, tile_overlap_col)
    snaphu_unwrapping(out_dir_snaphu)
    print("Pipeline [P2] for product unwrapping complete")


# [P3]:
def run_P3_elevation(out_dir, dem=None, subset=None, proj=None,
                     pixel_size=None, coherence_threshold=None, nodataval=None):
    # Write user settings to log file
    file = open(os.path.join(out_dir, 'log.txt'), 'a')
    file.write(
        '\nUSER-SETTINGS FOR PIPELINE 3:\n' +
        'Pixel size: ' + str(pixel_size) + '\n' +
        'Coherence threshold: ' + str(coherence_threshold) + '\n' +
        'No data value: ' + str(nodataval) + '\n'
    )
    file.close
    if subset:
        #  takes subset result from previous pipeline
        in_filename = os.path.join(out_dir, 'out_P1_subset')
        product = read(in_filename + ".dim")  # reads .dim
    else:
        # takes result from previous pipeline
        in_filename = os.path.join(out_dir, 'out_P1')
        product = read(in_filename + ".dim")  # reads .dim

    out_dir_snaphu = os.path.join(output_dir, "out_P2_snaphu")
    unwrapped_fn = os.path.join(out_dir_snaphu, 'unwrapped')
    unwrapped = read(unwrapped_fn + ".dim")
    product_unwrapped = snaphu_import(product, unwrapped)
    elevation = phase_to_elev(product_unwrapped, dem)
    # Combine elevation product with intensity, coherence, wrapped and unwrapped phase
    product_comb = collocate(product_unwrapped, elevation)
    bands_comb = list(product_comb.getBandNames())
    product_comb = set_no_data(product_comb, bands_comb[2:7], nodataval)
    # Terrain correct
    product_comb_tc = terrain_correction(product_comb, band=','.join(bands_comb[2:7]),
                                         projected=proj, pixel_size=pixel_size)
    # Create new elevation band with valid pixels above coherence threshold
    bands_comb_tc = list(product_comb_tc.getBandNames())
    elev_filter = filter_elevation(product_comb_tc,
                                   bands_comb_tc[4], bands_comb_tc[2],
                                   coherence_threshold, nodataval)
    product_comb_tc_filtered = collocate(product_comb_tc, elev_filter)
    bands_comb_tc_filtered = list(product_comb_tc_filtered.getBandNames())
    # Save to BEAM-DIMAP
    out_filename = os.path.join(out_dir, 'out_P3')
    write_BEAM_DIMAP_format(product_comb_tc_filtered, out_filename)
    # Save each band to a TIFF
    print(bands_comb_tc_filtered[0])
    intensity = band_select(product_comb_tc_filtered, bands=bands_comb_tc_filtered[0])
    intensity_tiff = os.path.join(out_dir, date_bundle + '_intensity.tif')
    write_TIFF_format(intensity, intensity_tiff)
    wrapped = band_select(product_comb_tc_filtered, bands=bands_comb_tc_filtered[1])
    wrapped_tiff = os.path.join(out_dir, date_bundle + '_wrapped_phase.tif')
    write_TIFF_format(wrapped, wrapped_tiff)
    coherence = band_select(product_comb_tc_filtered, bands=bands_comb_tc_filtered[2])
    coherence_tiff = os.path.join(out_dir, date_bundle + '_coherence.tif')
    write_TIFF_format(coherence, coherence_tiff)
    unwrapped = band_select(product_comb_tc_filtered, bands=bands_comb_tc_filtered[3])
    unwrapped_tiff = os.path.join(out_dir, date_bundle + '_unwrapped_phase.tif')
    write_TIFF_format(unwrapped, unwrapped_tiff)
    elevation = band_select(product_comb_tc_filtered, bands=bands_comb_tc_filtered[4])
    elevation_tiff = os.path.join(out_dir, date_bundle + '_elevation.tif')
    write_TIFF_format(elevation, elevation_tiff)
    elevation_cohth = band_select(product_comb_tc_filtered, bands=bands_comb_tc_filtered[5])
    elevation_cohth_tiff = os.path.join(out_dir, date_bundle +
                                        '_elevation_filtered_cohth_' +
                                        str(coherence_threshold) + '.tif')
    write_TIFF_format(elevation_cohth, elevation_cohth_tiff)
    print("Pipeline [P3] for DEM generation complete")


# Run the workflow
if 'P1' in args.pipelines:
    run_P1_interferogram(
        file1=file_path_1, file2=file_path_2,
        aoi=args.aoi_path, polarization=args.polarization,
        dem=args.dem, out_dir=output_dir,
        ifg_squarepixel=not args.ifg_indwinsize,
        ifg_cohwin_rg=args.ifg_cohwin_rg,
        ifg_cohwin_az=args.ifg_cohwin_az,
        multilooking=args.no_multilook,
        ml_rangelooks=args.multilook_range,
        goldsteinfiltering=args.no_goldstein,
        gpf_fftsize=args.gpf_fftsize,
        gpf_win=args.gpf_win,
        gpf_cohmask=args.gpf_cohmask,
        gpf_cohth=args.gpf_cohth,
        subsetting=args.no_subset,
        subset_buffer=args.aoi_buffer
    )

if 'P2' in args.pipelines:
    run_P2_unwrap(
        out_dir=output_dir,
        tiles=args.snaphu_tiles,
        cost_mode=args.snaphu_costmode,
        tile_overlap_row=args.snaphu_tile_overlap_row,
        tile_overlap_col=args.snaphu_tile_overlap_col,
        subset=args.no_subset
    )

if 'P3' in args.pipelines:
    run_P3_elevation(
        out_dir=output_dir,
        dem=args.dem,
        proj=args.no_output_projected,
        subset=args.no_subset,
        pixel_size=args.pixel_size,
        coherence_threshold=args.coherence_threshold,
        nodataval=args.no_data_value
    )
