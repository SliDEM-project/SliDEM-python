# -*- coding: utf-8 -*-

# Import modules
import argparse
import glob
import json
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
  v0.1 - 06/2022 - Generate DEMs from S1
Authors:
  Lorena Abad - University of Salzburg - lorena.abad@plus.ac.at''',
  formatter_class=argparse.RawTextHelpFormatter
)
parser.add_argument(
  '--download_dir',
  type=str,
  default='data',
  help='''relative path (refers to mounted volume) to the directory
  where S1 scenes were downloaded'''
)
parser.add_argument(
  '--output_dir',
  type=str,
  default='data',
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
    '--aoi_path',
    type=str,
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
    help='''Set DEM for back-geocoding, defaults to
    Copernicus 30m Global DEM.'''
)
parser.add_argument(
    '--subset_toggle',
    type=bool,
    default=True,
    help='''Should the process be performed in a subset corresponding to the
    given AOI?, defaults to True'''
)
parser.add_argument(
    '--aoi_buffer',
    type=float,
    default=0,
    help='''If subsetting the area to the AOI, should a 
    buffer around it be drawn? How big? Defaults to 0'''
)
parser.add_argument(
    '--output_projected',
    type=bool,
    default=True,
    help='''Should the results be in WGS84/UTM for the final elevation
    product?, defaults to True'''
)
parser.add_argument(
    '--pixel_size',
    type=float,
    default=30.0,
    help='''When applying terrain correction, what pixel size to use, defaults to 30'''
)
parser.add_argument(
    '--ifg_squarepixel',
    type=bool,
    default=True,
    help='''Should the resulting interferogram have a squared pixel size (True, default)
    or independent window sizes'''
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
    help='''Coherence azimuth window size (defaults to 2, ignored when ifg_squarepixel=True)'''
)
parser.add_argument(
    '--multilook_toggle',
    type=bool,
    default=True,
    help='''Should multilooking be performed?, defaults to True'''
)
parser.add_argument(
    '--multilook_range',
    type=int,
    default=6,
    help='''Number of multilook range, defaults to 6'''
)
parser.add_argument(
    '--goldstein_toggle',
    type=bool,
    default=True,
    help='''Should Goldstein filtering be applied?, defaults to True'''
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
    type=bool,
    default=False,
    help='''Use coherence mask?, defaults to False'''
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
args = parser.parse_args()

# Set home as current directory
os.chdir('home/')

# Read in image pairs
products = pd.read_csv(
    os.path.join(args.download_dir, args.query_result),
    sep=None, engine='python'
)
productsIn = products[products['Download']]

# "before" image .zip
if pd.to_datetime(productsIn.iloc[args.pair_index]['ReferenceDate']) < pd.to_datetime(productsIn.iloc[args.pair_index]['MatchDate']):
    file_path_1 = os.path.join(args.download_dir, productsIn.iloc[args.pair_index]['ReferenceID'] + '.zip')
else:
    file_path_1 = os.path.join(args.download_dir, productsIn.iloc[args.pair_index]['MatchID'] + '.zip')
# "after" image .zip
if pd.to_datetime(productsIn.iloc[args.pair_index]['MatchDate']) > pd.to_datetime(productsIn.iloc[args.pair_index]['ReferenceDate']):
    file_path_2 = os.path.join(args.download_dir, productsIn.iloc[args.pair_index]['MatchID'] + '.zip')
else:
    file_path_2 = os.path.join(args.download_dir, productsIn.iloc[args.pair_index]['ReferenceID'] + '.zip')

# Hashmap is used to give us access to all JAVA operators
HashMap = jpy.get_type('java.util.HashMap')
parameters = HashMap()

# Create output_dir if not existing
if not os.path.exists(args.output_dir):
    os.mkdir(args.output_dir)

# Create new directory on output dir with dates of reference and match image
ref_date_str = pd.to_datetime(
    productsIn.iloc[args.pair_index]['ReferenceDate'],
    yearfirst=False,
    dayfirst=True
).strftime('%Y%m%d')
mat_date_str = pd.to_datetime(
        productsIn.iloc[args.pair_index]['MatchDate'],
        yearfirst=False,
        dayfirst=True
    ).strftime('%Y%m%d')
date_bundle = ref_date_str + '_' + mat_date_str
output_dir = os.path.join(args.output_dir, 'out_' + date_bundle)
if not os.path.exists(output_dir):
    os.mkdir(output_dir)

# Get some metadata from the CSV file:
ref_date = productsIn.iloc[args.pair_index]['ReferenceDate']
mat_date = productsIn.iloc[args.pair_index]['MatchDate']
passf = productsIn.iloc[args.pair_index]['Pass']
orbit = productsIn.iloc[args.pair_index]['Orbit']

# Functions:
# From this section I define a set of functions that are called
# within a pipeline at the end of the script. Each function will start with a
# comment saying what it does, and will include an indicator as to which
# pipeline it belongs to (P1, P2, P3, P4)


# [P1|P2] Function to read AOI
def read_aoi(aoi, buffer):
    # Read aoi with shapely
    with open(aoi) as f:
        features = json.load(f)["features"]
    return GeometryCollection(
        [shape(feature["geometry"]).buffer(buffer) for feature in features]
    )


# [P1] Function to get subswaths and bursts
def get_swath_burst(filename, aoi, polar=args.polarization):
    print('Extracting subswath and bursts for AOI...')
    aoi_geom = read_aoi(aoi, buffer=0)

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
    img_df = img_df[img_df.intersects(aoi_geom)]

    # Return intersecting subswaths and bursts as a dictionary
    return dict(
        subswath=img_df['subswath'].tolist(),
        burst=img_df['burst'].tolist()
    )


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


# [P1] Function to apply TOPSAR split with SNAP
def topsar_split(product, IW, firstBurstIndex, lastBurstIndex, polar=args.polarization):
    print('Applying TOPSAR Split...')
    parameters.put('subswath', IW)
    parameters.put('firstBurstIndex', firstBurstIndex)
    parameters.put('lastBurstIndex', lastBurstIndex)
    parameters.put('selectedPolarisations', polar)
    output = GPF.createProduct("TOPSAR-Split", parameters, product)
    return output


# [P1] Function to apply Orbit file with SNAP
def apply_orbit_file(product):
    print('Applying orbit file...')
    parameters.put("Orbit State Vectors", "Sentinel Precise (Auto Download)")
    parameters.put("Polynomial Degree", 3)
    parameters.put("Do not fail if new orbit file is not found", True)
    return GPF.createProduct("Apply-Orbit-File", parameters, product)


# [P1] Function to do back geocoding with SNAP
def back_geocoding(product, dem):
    print('Back geocoding...')
    parameters.put("demName", dem)
    parameters.put("demResamplingMethod", "BILINEAR_INTERPOLATION")
    parameters.put("resamplingType", "BILINEAR_INTERPOLATION")
    parameters.put("maskOutAreaWithoutElevation", True)
    parameters.put("outputDerampDemodPhase", True)
    parameters.put("disableReramp", False)
    return GPF.createProduct("Back-Geocoding", parameters, product)


# [P1] Function to apply Enhanced Spectral Diversity with SNAP
def enhanced_spectral_diversity(product):
    print('Applying Enhanced Spectral Diversity...')
    # called with defaults
    # should only be applied if multiple bursts were used in topsar_split
    return GPF.createProduct("Enhanced-Spectral-Diversity", parameters, product)


# [P2] Function to calculate the interferogram
def interferogram(product, ifg_squarepixel, ifg_cohwin_az, ifg_cohwin_rg):
    print('Creating interferogram...')
    parameters.put("Subtract flat-earth phase", True)
    parameters.put("Degree of \"Flat Earth\" polynomial", 5)
    parameters.put("Number of \"Flat Earth\" estimation points", 501)
    parameters.put("Orbit interpolation degree", 3)
    parameters.put("Include coherence estimation", True)
    parameters.put("Square Pixel", ifg_squarepixel)
    parameters.put("Independent Window Sizes", not ifg_squarepixel)
    parameters.put("Coherence Range Window Size", ifg_cohwin_rg)
    parameters.put("Coherence Azimuth Window Size", ifg_cohwin_az)
    return GPF.createProduct("Interferogram", parameters, product)


# [P2] Function for TOPSAR deburst
def topsar_deburst(source):
    print('Running TOPSAR deburst...')
    parameters.put("Polarisations", args.polarization)
    output = GPF.createProduct("TOPSAR-Deburst", parameters, source)
    return output


# [P2] Function for topophase removal (optional)
def topophase_removal(product, dem):
    parameters.put("Orbit Interpolation Degree", 3)
    parameters.put("demName", dem)
    parameters.put("Tile Extension[%]", 100)
    parameters.put("Output topographic phase band", True)
    parameters.put("Output elevation band", False)
    return GPF.createProduct("TopoPhaseRemoval", parameters, product)


# [P2] Function for multilooking (optional)
# Multi-looking is used to reduce resolution.
# ML_nRgLooks stands for number of range looks
# grSquarePixel is set to True to default to a square pixel,
# hence the number of azimuth looks is automatically calculated.
# https://forum.step.esa.int/t/alterring-spatial-resolution-of-sentinel-1-image/21906/7
def multilook(product, ML_nRgLooks):
    print('Multi-looking...')
    parameters.put('grSquarePixel', True)
    parameters.put("nRgLooks", ML_nRgLooks) # half of range looks on metadata
    output = GPF.createProduct("Multilook", parameters, product)
    return output


# [P2] Function to apply Goldstein phase filtering (optional)
def goldstein_phase_filter(product, gpf_fftsize, gpf_win,
                           gpf_cohmask, gpf_cohth):
    print('Applying Goldstein phase filtering...')
    parameters.put("Adaptive Filter Exponent in(0,1]:", 1.0)
    parameters.put("FFT Size", gpf_fftsize)
    parameters.put("Window Size", gpf_win)
    parameters.put("Use coherence mask", gpf_cohmask)
    parameters.put("Coherence Threshold in[0,1]:", gpf_cohth)
    return GPF.createProduct("GoldsteinPhaseFiltering", parameters, product)


# [P2] Function to create a subset
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

    unw_img_file = glob.glob(os.path.join(output_dir, "out_P3_snaphu", "/UnwPhase*.img"))
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
def terrain_correction(source, band=None, projected=True, pixel_size=30.0):
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


# Pipe functions
def run_P1(file1, file2, aoi, polarization, dem, out_dir):
    # Write user settings to log file
    file = open(os.path.join(out_dir, 'log.txt'), 'w')
    file.write(
        'USER-SETTINGS FOR PIPELINE 1:\n' +
        'ReferenceID path: ' + file1 + '\n' +
        'ReferenceID date: ' + ref_date + '\n' +
        'MatchID path: ' + file2 + '\n' +
        'MatchID date: ' + mat_date + '\n' +
        'Polarization: ' + polarization + '\n' +
        'Pass: ' + passf + '\n' +
        'Orbit: ' + str(orbit) + '\n' +
        'DEM for back-geocoding: ' + dem + '\n'

    )
    file.close

    # Apply stsa workflow
    stsa_1 = get_swath_burst(file1, aoi, polar=polarization)
    stsa_2 = get_swath_burst(file2, aoi, polar=polarization)
    # Get subswath that intersects AOI
    swath_1 = stsa_1['subswath']
    swath_2 = stsa_2['subswath']
    # TODO: Multiple subswaths are not supported but currently there is no way around it,
    #  since the selection happens internally. The pipeline will exit with an Error, see below.
    #  Options: ask user to input a different AOI?
    if not len(swath_1) == len(swath_2) == 1:
        raise ValueError("Multiple subswaths are not supported yet.")
    # TODO: Add documentation here, subswaths should be the same because each of them is
    #   processed separately.
    if not swath_1 == swath_2:
        raise ValueError("Subswaths intersecting the AOI do not match.")
    IW = swath_1[0]
    # Get burst indices
    burst_1 = stsa_1['burst']
    burst_2 = stsa_2['burst']
    firstBurstIndex_1 = min(burst_1)
    lastBurstIndex_1 = max(burst_1)
    firstBurstIndex_2 = min(burst_2)
    lastBurstIndex_2 = max(burst_2)

    # Write sub-swath and burst to log file
    file = open(os.path.join(out_dir, 'log.txt'), 'a')
    file.write(
        '\nAUTOMATICALLY EXTRACTED PARAMETERS IN PIPELINE 1:\n'
        'Subswath: ' + IW + '\n' +
        'Bursts 1: ' + ','.join([str(item) for item in burst_1]) + '\n' +
        'Bursts 2: ' + ','.join([str(item) for item in burst_2]) + '\n')
    file.close

    # Compute InSAR stack overview
    product_1 = read(file1)
    product_2 = read(file2)
    # import the stack operator
    # From: https://forum.step.esa.int/t/insar-dinsar-perpendicular-baseline-calculation/3776/34
    stack = jpy.get_type('org.esa.s1tbx.insar.gpf.coregistration.CreateStackOp')
    stack.getBaselines([product_1, product_2], product_1)
    # Now there is a new piece of metadata in product one called 'Baselines'
    baseline_root_metadata = product_1.getMetadataRoot().getElement('Abstracted_Metadata').getElement('Baselines')
    # Write to log all the baselines between all master/slave configurations
    file = open(os.path.join(out_dir, 'log.txt'), 'a')
    file.write('\nCOMPUTED STACKS IN PIPELINE 1:\n')
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
    product_TOPSAR_1 = topsar_split(product_1, IW,
                                    firstBurstIndex_1, lastBurstIndex_1)
    product_TOPSAR_2 = topsar_split(product_2,
                                    IW, firstBurstIndex_2, lastBurstIndex_2)
    product_orbitFile_1 = apply_orbit_file(product_TOPSAR_1)
    product_orbitFile_2 = apply_orbit_file(product_TOPSAR_2)
    product = back_geocoding([product_orbitFile_1, product_orbitFile_2], dem)
    if len(burst_1) > 1 or len(burst_2) > 1:
        product = enhanced_spectral_diversity(product)
    out_filename = os.path.join(out_dir, 'out_P1')
    write_BEAM_DIMAP_format(product, out_filename)
    print("Pipeline [P1] complete")


def run_P2(out_dir, topophaseremove=False, dem=None,
           ifg_squarepixel=None, ifg_cohwin_rg=None,
           ifg_cohwin_az=None,
           multilooking=None, ml_rangelooks=None,
           goldsteinfiltering=None,
           gpf_fftsize=None, gpf_win=None,
           gpf_cohmask=None, gpf_cohth=None,
           subsetting=None, aoi=None, subset_buffer=None):
    # Write user settings to log file
    file = open(os.path.join(out_dir, 'log.txt'), 'a')
    file.write(
        '\nUSER-SETTINGS FOR PIPELINE 2:\n' +
        'Multi-looking range: ' + str(ml_rangelooks) + '\n'
    )
    file.close

    # takes result from previous pipeline
    in_filename = os.path.join(out_dir, 'out_P1')
    product = read(in_filename + ".dim")  # reads .dim
    product = interferogram(product,
                            ifg_squarepixel, ifg_cohwin_rg, ifg_cohwin_az)
    product = topsar_deburst(product)
    if topophaseremove:
        product = topophase_removal(product, dem)
    if multilooking:
        product = multilook(product, ML_nRgLooks=ml_rangelooks)
    if goldsteinfiltering:
        product = goldstein_phase_filter(product,
                                         gpf_fftsize, gpf_win,
                                         gpf_cohmask, gpf_cohth)
    out_filename = os.path.join(out_dir, 'out_P2')
    write_BEAM_DIMAP_format(product, out_filename)
    if subsetting:
        product_ss = subset(product, aoi, buffer=subset_buffer)
        out_filename = os.path.join(out_dir, 'out_P2_subset')
        write_BEAM_DIMAP_format(product_ss, out_filename)
    print("Pipeline [P2] complete")


def run_P3(out_dir, tiles, cost_mode, tile_overlap_row,
           tile_overlap_col, subset=None):
    # Write user settings to log file
    file = open(os.path.join(out_dir, 'log.txt'), 'a')
    file.write(
        '\nUSER-SETTINGS FOR PIPELINE 3:\n' +
        'Tiles: ' + str(tiles) + '\n'
        'Tiles overlap: row ' + str(tile_overlap_row) +
        ', col ' + str(tile_overlap_row) + '\n'
        'Cost mode: ' + cost_mode + '\n'
    )
    file.close

    if subset:
        # takes subset result from previous pipeline
        in_filename = os.path.join(out_dir, 'out_P2_subset')
        product = read(in_filename + ".dim")  # reads .dim
        bands = list(product.getBandNames())
        product.getBand(bands[3]).setGeophysicalNoDataValue(-99999)
        product.getBand(bands[3]).setNoDataValueUsed(True)
    else:
        # takes result from previous pipeline
        in_filename = os.path.join(out_dir, 'out_P2')
        product = read(in_filename + ".dim")  # reads .dim
    out_dir_snaphu = os.path.join(output_dir, "out_P3_snaphu")
    snaphu_export(product, out_dir_snaphu, tiles, cost_mode,
                  tile_overlap_row, tile_overlap_col)
    snaphu_unwrapping(out_dir_snaphu)
    print("Pipeline [P3] complete")


def run_P4(out_dir, dem=None, subset=None, proj=None, pixel_size=None):
    if subset:
        #  takes subset result from previous pipeline
        in_filename = os.path.join(out_dir, 'out_P2_subset')
        product = read(in_filename + ".dim")  # reads .dim
    else:
        # takes result from previous pipeline
        in_filename = os.path.join(out_dir, 'out_P2')
        product = read(in_filename + ".dim")  # reads .dim

    out_dir_snaphu = os.path.join(output_dir, "out_P3_snaphu")
    unwrapped_fn = os.path.join(out_dir_snaphu, 'unwrapped')
    unwrapped = read(unwrapped_fn + ".dim")
    product_unwrapped = snaphu_import(product, unwrapped)
    elevation = phase_to_elev(product_unwrapped, dem)
    elevation.getBand('elevation').setGeophysicalNoDataValue(-99999)
    elevation.getBand('elevation').setNoDataValueUsed(True)
    elevation_tc = terrain_correction(elevation, band='elevation',
                                      projected=proj, pixel_size=pixel_size)
    out_filename = os.path.join(out_dir, 'out_P4')
    write_BEAM_DIMAP_format(elevation_tc, out_filename)
    # Save elevation to TIFF
    out_elev_tiff = os.path.join(out_dir, date_bundle + '_elevation.tif')
    write_TIFF_format(elevation_tc, out_elev_tiff)
    # Terrain correct coherence, wrapped and unwrapped phase and save to TIFF
    band_unw = list(product_unwrapped.getBandNames())
    product_unwrapped.getBand(band_unw[3]).setGeophysicalNoDataValue(-99999)
    product_unwrapped.getBand(band_unw[3]).setNoDataValueUsed(True)
    product_unwrapped.getBand(band_unw[4]).setGeophysicalNoDataValue(-99999)
    product_unwrapped.getBand(band_unw[4]).setNoDataValueUsed(True)
    product_unwrapped.getBand(band_unw[5]).setGeophysicalNoDataValue(-99999)
    product_unwrapped.getBand(band_unw[5]).setNoDataValueUsed(True)
    coh_tc = terrain_correction(product_unwrapped, band=band_unw[4],
                                projected=proj, pixel_size=pixel_size)
    out_coh_tiff = os.path.join(out_dir, date_bundle + '_coherence.tif')
    write_TIFF_format(coh_tc, out_coh_tiff)
    wrapped_tc = terrain_correction(product_unwrapped, band=band_unw[3],
                                    projected=proj, pixel_size=pixel_size)
    out_w_tiff = os.path.join(out_dir, date_bundle + '_wrapped_phase.tif')
    write_TIFF_format(wrapped_tc, out_w_tiff)
    unwrapped_tc = terrain_correction(product_unwrapped, band=band_unw[5],
                                      projected=proj, pixel_size=pixel_size)
    out_unw_tiff = os.path.join(out_dir, date_bundle + '_unwrapped_phase.tif')
    write_TIFF_format(unwrapped_tc, out_unw_tiff)
    print("Pipeline [P4] complete")


# Run the workflow
# run_P1(
#     file1=file_path_1, file2=file_path_2,
#     aoi=args.aoi_path, polarization=args.polarization,
#     dem=args.dem, out_dir=output_dir
# )
#
# run_P2(
#     out_dir=output_dir,
#     ifg_squarepixel=args.ifg_squarepixel,
#     ifg_cohwin_rg=args.ifg_cohwin_rg,
#     ifg_cohwin_az=args.ifg_cohwin_az,
#     multilooking=args.multilook_toggle,
#     ml_rangelooks=args.multilook_range,
#     goldsteinfiltering=args.goldstein_toggle,
#     gpf_fftsize=args.gpf_fftsize,
#     gpf_win=args.gpf_win,
#     gpf_cohmask=args.gpf_cohmask,
#     gpf_cohth=args.gpf_cohth,
#     subsetting=args.subset_toggle,
#     aoi=args.aoi_path,
#     subset_buffer=args.aoi_buffer,
# )

run_P3(
    out_dir=output_dir,
    tiles=args.snaphu_tiles,
    cost_mode=args.snaphu_costmode,
    tile_overlap_row=args.snaphu_tile_overlap_row,
    tile_overlap_col=args.snaphu_tile_overlap_col,
    subset=args.subset_toggle
)

run_P4(
    out_dir=output_dir,
    dem=args.dem,
    proj=args.output_projected,
    subset=args.subset_toggle,
    pixel_size=args.pixel_size
)
