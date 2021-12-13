import json
import os
import stsa
import warnings
from shapely.geometry import shape, GeometryCollection
from snappy import ProductIO, jpy, GPF

# Set home as current directory
os.chdir('home/')

# Arguments
# "after" image .zip
file_path_1 = "data/s1/S1B_IW_SLC__1SDV_20190816T155043_20190816T155110_017613_02122D_39CD.zip"
# "before" image .zip
file_path_2 = "data/s1/S1A_IW_SLC__1SDV_20190810T155114_20190810T155141_028509_03390E_9F11.zip"
# aoi in .geojson
aoi_path = "data/aoi/Alta.geojson"
# output directory
output_dir = "data/tests/test_pipe1"
# polarization: default "VV"
polarization = "VV"
# DEM for back-geocoding
dem = "Copernicus 30m Global DEM"

# Hashmap is used to give us access to all JAVA operators
HashMap = jpy.get_type('java.util.HashMap')
parameters = HashMap()


# Functions:
# From this section I will define a set of functions that will be called
# within a pipeline at the end of the script. Each function will start with a
# comment saying what it does, and will include an indicator as to which
# pipeline it belongs to (P1, P2, P3)


# [P1] Function to get subswaths and bursts
def get_swath_burst(filename, aoi, polar=polarization):
    print('Extracting subswath and bursts for AOI...')
    # Read aoi with shapely
    with open(aoi) as f:
        features = json.load(f)["features"]
    aoi_geom = GeometryCollection(
        [shape(feature["geometry"]).buffer(0) for feature in features]
    )

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


# [P1|P2|P3] Function to read the .zip file into SNAP
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


# [P1] Pipe functions
def run_P1(file1, file2, aoi, polarization, dem, out_dir):
    # Apply stsa workflow
    stsa_1 = get_swath_burst(file1, aoi, polar=polarization)
    stsa_2 = get_swath_burst(file2, aoi, polar=polarization)
    # Get subswath that intersects AOI
    swath_1 = stsa_1['subswath']
    swath_2 = stsa_2['subswath']
    if not len(swath_1) == len(swath_2) == 1:
        raise ValueError("Multiple subswaths are not supported yet.")
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

    # Proceed to SNAP workflow
    product_1 = read(file1)
    product_2 = read(file2)
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


# Run the function
run_P1(
    file1=file_path_1, file2=file_path_2,
    aoi=aoi_path, polarization=polarization,
    dem=dem, out_dir=output_dir
)
