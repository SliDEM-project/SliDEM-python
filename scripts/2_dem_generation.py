import glob
import json
import os
import pandas as pd
from shapely.geometry import shape, GeometryCollection
from snappy import ProductIO, jpy, GPF
import stsa
import subprocess

# Set home as current directory
os.chdir('home/')

# Arguments
download_dir = "data/s1/grossarl"
query_result = "s1_scenes_grossarl_2017.csv"
index = 3

# Read in image pairs
products = pd.read_csv(os.path.join(download_dir, query_result))
productsIn = products[products['Download']]

# "before" image .zip
if pd.to_datetime(productsIn.iloc[index]['ReferenceDate']) < pd.to_datetime(productsIn.iloc[index]['MatchDate']):
    file_path_1 = os.path.join(download_dir, productsIn.iloc[index]['ReferenceID'] + '.zip')
else:
    file_path_1 = os.path.join(download_dir, productsIn.iloc[index]['MatchID'] + '.zip')
# "after" image .zip
if pd.to_datetime(productsIn.iloc[index]['MatchDate']) > pd.to_datetime(productsIn.iloc[index]['ReferenceDate']):
    file_path_2 = os.path.join(download_dir, productsIn.iloc[index]['MatchID'] + '.zip')
else:
    file_path_2 = os.path.join(download_dir, productsIn.iloc[index]['ReferenceID'] + '.zip')

# aoi in .geojson
# aoi_path = "data/aoi/Alta.geojson"
# aoi_path = "data/aoi/Gjerdrum.geojson"
aoi_path = "data/aoi/Grossarl.geojson"
# aoi_path = "data/aoi/Kleinarl.geojson"

# output directory
# output_dir = "data/tests/test_pipes_alta"
# output_dir = "data/tests/test_pipes_gjerdrum"
output_dir = "data/tests/test_pipes_grossarl"
# output_dir = "data/tests/test_pipes_kleinarl"

# polarization: default "VV"
polarization = "VV"
# DEM for back-geocoding
dem = "Copernicus 30m Global DEM"
# Should the process be performed in a subset corresponding to the given AOI?
subset_toggle = True
# Should the results be in WGS84/UTM for the final elevation product?
output_projected = True

# Hashmap is used to give us access to all JAVA operators
HashMap = jpy.get_type('java.util.HashMap')
parameters = HashMap()

# Create output_dir if not existing
if not os.path.exists(output_dir):
    os.mkdir(output_dir)

# Create new directory on output dir with dates of reference and match image
output_dir = os.path.join(
    output_dir, 'out_' +
    pd.to_datetime(productsIn.iloc[index]['ReferenceDate'], yearfirst=False, dayfirst=True).strftime('%Y%m%d') + '_' +
    pd.to_datetime(productsIn.iloc[index]['MatchDate'], yearfirst=False, dayfirst=True).strftime('%Y%m%d'))
if not os.path.exists(output_dir):
    os.mkdir(output_dir)

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
def get_swath_burst(filename, aoi, polar=polarization):
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
def write(product, filename):
    ProductIO.writeProduct(product, filename, "GeoTiff")


# [P1|P2|P3] Function to write SNAP product to BEAM-DIMAP format
def write_BEAM_DIMAP_format(product, filename):
    print('Saving BEAM-DIMAP format.')
    ProductIO.writeProduct(product, filename + '.dim', 'BEAM-DIMAP')


# [P1] Function to apply TOPSAR split with SNAP
def topsar_split(product, IW, firstBurstIndex, lastBurstIndex, polar=polarization):
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
def interferogram(product):
    print('Creating interferogram...')
    parameters.put("Subtract flat-earth phase", True)
    parameters.put("Degree of \"Flat Earth\" polynomial", 5)
    parameters.put("Number of \"Flat Earth\" estimation points", 501)
    parameters.put("Orbit interpolation degree", 3)
    parameters.put("Include coherence estimation", True)
    parameters.put("Square Pixel", True)
    parameters.put("Independent Window Sizes", False)
    parameters.put("Coherence Azimuth Window Size", 10)
    parameters.put("Coherence Range Window Size", 2)
    return GPF.createProduct("Interferogram", parameters, product)


# [P2] Function for TOPSAR deburst
def topsar_deburst(source):
    print('Running TOPSAR deburst...')
    parameters.put("Polarisations", "VV,VH")
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
    parameters.put("nRgLooks", ML_nRgLooks)
    output = GPF.createProduct("Multilook", parameters, product)
    return output


# [P2] Function to apply Goldstein phase filtering (optional)
def goldstein_phase_filter(product):
    print('Applying Goldstein phase filtering...')
    parameters.put("Adaptive Filter Exponent in(0,1]:", 1.0)
    parameters.put("FFT Size", 64)
    parameters.put("Window Size", 3)
    parameters.put("Use coherence mask", False)
    parameters.put("Coherence Threshold in[0,1]:", 0.2)
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
    infile = os.path.join(snaphu_exp_folder, "snaphu.conf")
    with open(str(infile)) as lines:
        line = lines.readlines()[6]
        snaphu_string = line[1:].strip()
        snaphu_args = snaphu_string.split()
    print("\nCommand sent to snaphu:\n", snaphu_string)
    process = subprocess.Popen(snaphu_args, cwd=str(snaphu_exp_folder))
    process.communicate()
    process.wait()
    print('Unwrapping...')

    unwrapped_list = glob.glob(str(snaphu_exp_folder) + "/UnwPhase*.hdr")
    unwrapped_hdr = str(unwrapped_list[0])
    unwrapped_read = ProductIO.readProduct(unwrapped_hdr)
    fn = os.path.join(snaphu_exp_folder, "unwrapped")
    write_BEAM_DIMAP_format(unwrapped_read, fn)
    print('Phase unwrapping performed successfully.')


# [P4] Function to transform phase to elevation
def phase_to_elev(product, unwrapped, dem):
    print('Converting phase to elevation...')
    snaphu_files = jpy.array('org.esa.snap.core.datamodel.Product', 2)
    snaphu_files[0] = product
    snaphu_files[1] = unwrapped
    snaphu_import = GPF.createProduct("SnaphuImport", parameters, snaphu_files)
    parameters.put("demName", dem)
    output = GPF.createProduct("PhaseToElevation", parameters, snaphu_import)
    return output


# [P4] Function to perform terrain correction
def terrain_correction(source, band, projected=True):
    print('Terrain correction...')
    parameters.put('demName', dem)
    parameters.put('imgResamplingMethod', 'BILINEAR_INTERPOLATION')
    if projected:
        parameters.put('mapProjection', 'AUTO:42001')
    # parameters.put('saveProjectedLocalIncidenceAngle', False)
    parameters.put('sourceBands', band)
    parameters.put('saveSelectedSourceBand', True)
    parameters.put('nodataValueAtSea', False)
    parameters.put('pixelSpacingInMeter', 30.0)
    output = GPF.createProduct('Terrain-Correction', parameters, source)
    return output


# Pipe functions
def run_P1(file1, file2, aoi, polarization, dem, out_dir):
    # Write user settings to log file
    file = open(os.path.join(out_dir, 'log.txt'), 'w')
    file.write(
        'USER-SETTINGS FOR PIPELINE 1:\n' +
        'ReferenceID path: ' + file1 + '\n' +
        'MatchID path: ' + file2 + '\n' +
        'Polarization: ' + polarization + '\n' +
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
    product_TOPSAR_1 = topsar_split(product_1, IW, firstBurstIndex_1, lastBurstIndex_1)
    product_TOPSAR_2 = topsar_split(product_2, IW, firstBurstIndex_2, lastBurstIndex_2)
    product_orbitFile_1 = apply_orbit_file(product_TOPSAR_1)
    product_orbitFile_2 = apply_orbit_file(product_TOPSAR_2)
    product = back_geocoding([product_orbitFile_1, product_orbitFile_2], dem)
    if len(burst_1) > 1 or len(burst_2) > 1:
        product = enhanced_spectral_diversity(product)
    out_filename = os.path.join(out_dir, 'out_P1')
    write_BEAM_DIMAP_format(product, out_filename)
    print("Pipeline [P1] complete")


def run_P2(out_dir, topophaseremove=False, dem=None,
           multilooking=True, ml_rangelooks=None,
           goldsteinfiltering=True,
           subsetting=True, aoi=None, subset_buffer=0):
    # Write user settings to log file
    file = open(os.path.join(out_dir, 'log.txt'), 'a')
    file.write(
        '\nUSER-SETTINGS FOR PIPELINE 2:\n' +
        'Multi-looking range: ' + str(ml_rangelooks) + '\n'
    )
    file.close

    in_filename = os.path.join(out_dir, 'out_P1')  # takes result from previous pipeline
    product = read(in_filename + ".dim")  # reads .dim
    product = interferogram(product)
    product = topsar_deburst(product)
    if topophaseremove:
        product = topophase_removal(product, dem)
    if multilooking:
        product = multilook(product, ML_nRgLooks=ml_rangelooks)
    if goldsteinfiltering:
        product = goldstein_phase_filter(product)
    out_filename = os.path.join(out_dir, 'out_P2')
    write_BEAM_DIMAP_format(product, out_filename)
    if subsetting:
        product_ss = subset(product, aoi, buffer=subset_buffer)
        out_filename = os.path.join(out_dir, 'out_P2_subset')
        write_BEAM_DIMAP_format(product_ss, out_filename)
    print("Pipeline [P2] complete")


def run_P3(out_dir, tiles, cost_mode, tile_overlap_row, tile_overlap_col, subset=True):
    # Write user settings to log file
    file = open(os.path.join(out_dir, 'log.txt'), 'a')
    file.write(
        '\nUSER-SETTINGS FOR PIPELINE 3:\n' +
        'Tiles: ' + str(tiles) + '\n'
        'Tiles overlap: row ' + str(tile_overlap_row) + ', col ' + str(tile_overlap_row) + '\n'
        'Cost mode: ' + cost_mode + '\n'
    )
    file.close

    if subset:
        in_filename = os.path.join(out_dir, 'out_P2_subset')  # takes subset result from previous pipeline
        product = read(in_filename + ".dim")  # reads .dim
    else:
        in_filename = os.path.join(out_dir, 'out_P2')  # takes subset result from previous pipeline
        product = read(in_filename + ".dim")  # reads .dim
    out_dir_snaphu = os.path.join(output_dir, "out_P3_snaphu")
    snaphu_export(product, out_dir_snaphu, tiles, cost_mode, tile_overlap_row, tile_overlap_col)
    snaphu_unwrapping(out_dir_snaphu)
    # TODO: if unwrapping fails (no .img file is generated),
    #  pass on the error from snaphu and don't go on with the script
    print("Pipeline [P3] complete")


def run_P4(out_dir, dem=None, subset=True, proj=True):
    if subset:
        in_filename = os.path.join(out_dir, 'out_P2_subset')  # takes subset result from previous pipeline
        product = read(in_filename + ".dim")  # reads .dim
    else:
        in_filename = os.path.join(out_dir, 'out_P2')  # takes result from previous pipeline
        product = read(in_filename + ".dim")  # reads .dim
    out_dir_snaphu = os.path.join(output_dir, "out_P3_snaphu")
    unwrapped_fn = os.path.join(out_dir_snaphu, 'unwrapped')
    unwrapped = read(unwrapped_fn + ".dim")
    product = phase_to_elev(product, unwrapped, dem)
    product = terrain_correction(product, band='elevation', projected=proj)
    out_filename = os.path.join(out_dir, 'out_P4')
    write_BEAM_DIMAP_format(product, out_filename)
    print("Pipeline [P4] complete")


# Run the workflow
run_P1(
    file1=file_path_1, file2=file_path_2,
    aoi=aoi_path, polarization=polarization,
    dem=dem, out_dir=output_dir
)

run_P2(
    out_dir=output_dir,
    multilooking=True, ml_rangelooks=6,
    goldsteinfiltering=True,
    subsetting=subset_toggle, aoi=aoi_path,
    subset_buffer=0
)

run_P3(
    out_dir=output_dir,
    tiles=1,
    # Either TOPO or SMOOTH are viable options.
    # DEFO is for deformation and not recommended.
    cost_mode='TOPO',
    tile_overlap_row=200,
    tile_overlap_col=200,
    subset=subset_toggle
)

run_P4(
    out_dir=output_dir,
    dem=dem, proj=output_projected,
    subset=subset_toggle
)
