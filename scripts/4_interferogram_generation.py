import os
import snappy
from snappy import GPF
from snappy import ProductIO
from snappy import HashMap
from snappy import jpy
import subprocess
from time import *
import glob

# documentation: http://step.esa.int/docs/v2.0/apidoc/engine/overview-summary.html

print('snappy.__file__:', snappy.__file__)
# prints the path to the snappy configs.
# change in jpyconfig.py e.g. jvm_maxmem = '30G' and in snappy.ini java_max_mem: 30G (and uncomment)

# Hashmap is used to give us access to all JAVA oerators
HashMap = jpy.get_type('java.util.HashMap')
parameters = HashMap()


def read(filename):
    print('Reading...')
    return ProductIO.readProduct(filename)


def topsar_split(product, IW, firstBurstIndex, lastBurstIndex):
    print('Apply TOPSAR Split...')
    parameters = HashMap()
    parameters.put('subswath', IW)
    parameters.put('firstBurstIndex', firstBurstIndex)  # added by me
    parameters.put('lastBurstIndex', lastBurstIndex)  # added by me
    parameters.put('selectedPolarisations', 'VV')
    output = GPF.createProduct("TOPSAR-Split", parameters, product)
    return output


def apply_orbit_file(product):
    print('Applying orbit file ...')
    parameters.put("Orbit State Vectors", "Sentinel Precise (Auto Download)")
    parameters.put("Polynomial Degree", 3)
    parameters.put("Do not fail if new orbit file is not found", True)
    return GPF.createProduct("Apply-Orbit-File", parameters, product)


def back_geocoding(product):
    print('back_geocoding ...')
    parameters.put("demName", "Copernicus 30m Global DEM")
    # parameters.put("externalDEMFile", r"E:\Ben\Norway\SliDEM\Norway\ReferenceData\LiDAR\NDH Alta 2pkt 2018\NDH_Alta_2pkt_2018_DSM.tif")
    parameters.put("demResamplingMethod", "BILINEAR_INTERPOLATION")
    parameters.put("resamplingType", "BILINEAR_INTERPOLATION")
    parameters.put("maskOutAreaWithoutElevation", True)
    parameters.put("outputDerampDemodPhase", True)
    parameters.put("disableReramp", False)
    return GPF.createProduct("Back-Geocoding", parameters, product)


def Enhanced_Spectral_Diversity(product):
    parameters = HashMap()
    #    parameters.put("fineWinWidthStr2",512)
    #    parameters.put("fineWinHeightStr",512)
    #    parameters.put("fineWinAccAzimuth",16)
    #    parameters.put("fineWinAccRange",16)
    #    parameters.put("fineWinOversampling",128)
    #    parameters.put("xCorrThreshold",0.1)
    #    parameters.put("cohThreshold",0.3)
    #    parameters.put("numBlocksPerOverlap",10)
    #    parameters.put("esdEstimator",'Periodogram')
    #    parameters.put("weightFunc",'Inv Quadratic')
    #    parameters.put("temporalBaselineType",'Number of images')
    #    parameters.put("maxTemporalBaseline",4)
    #    parameters.put("integrationMethod",'L1 and L2')
    #    parameters.put("doNotWriteTargetBands",False)
    #    parameters.put("useSuppliedRangeShift",False)
    #    parameters.put("overallRangeShift",0)
    #    parameters.put("useSuppliedAzimuthShift",False)
    #    parameters.put("overallAzimuthShift",0)
    return GPF.createProduct("Enhanced-Spectral-Diversity", parameters, product)


def interferogram(product):
    print('Creating interferogram ...')
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


def topsar_deburst(source):
    parameters = HashMap()
    parameters.put("Polarisations", "VV,VH")
    output = GPF.createProduct("TOPSAR-Deburst", parameters, source)
    return output


def topophase_removal(product):
    parameters.put("Orbit Interpolation Degree", 3)
    parameters.put("demName", "Copernicus 30 m Global DEM")
    parameters.put("Tile Extension[%]", 100)
    parameters.put("Output topographic phase band", True)
    parameters.put("Output elevation band", False)
    return GPF.createProduct("TopoPhaseRemoval", parameters, product)


# def Multilook(product, ML_nRgLooks,ML_nAzLooks):
def Multilook(product, ML_nRgLooks):
    parameters = HashMap()
    parameters.put('grSquarePixel', True)
    parameters.put("nRgLooks", ML_nRgLooks)
    output = GPF.createProduct("Multilook", parameters, product)
    return output


def goldstein_phasefiltering(product):
    parameters.put("Adaptive Filter Exponent in(0,1]:", 1.0)
    parameters.put("FFT Size", 64)
    parameters.put("Window Size", 3)
    parameters.put("Use coherence mask", False)
    parameters.put("Coherence Threshold in[0,1]:", 0.2)
    return GPF.createProduct("GoldsteinPhaseFiltering", parameters, product)


def SNAPHU_export(product, SNAPHU_exp_folder, tiles):
    parameters = HashMap()
    parameters.put('targetFolder', SNAPHU_exp_folder)  #
    parameters.put('statCostMode', 'SMOOTH')
    parameters.put('initMethod', 'MCF')
    parameters.put('numberOfTileCols', tiles)
    parameters.put('numberOfTileRows', tiles)
    parameters.put('rowOverlap', 200)
    parameters.put('colOverlap', 200)
    parameters.put('numberOfProcessors', 4)
    parameters.put('tileCostThreshold', 500)
    output = GPF.createProduct('SnaphuExport', parameters, product)
    ProductIO.writeProduct(output, SNAPHU_exp_folder, 'Snaphu')
    return (output)

def snaphu_unwrapping(SNAPHU_exp_folder):
    infile = os.path.join(SNAPHU_exp_folder, "snaphu.conf")
    with open(str(infile)) as lines:
        line = lines.readlines()[6]
        snaphu_string = line[1:].strip()
        snaphu_args = snaphu_string.split()
    process = subprocess.Popen(snaphu_args, cwd=str(SNAPHU_exp_folder))
    process.communicate()
    process.wait()
    print('done')

    unwrapped_list = glob.glob(str(SNAPHU_exp_folder) + "/UnwPhase*.hdr")

    unwrapped_hdr = str(unwrapped_list[0])
    unwrapped_read = ProductIO.readProduct(unwrapped_hdr)
    fn = os.path.join(SNAPHU_exp_folder, "unwrapped_read.dim")
    ProductIO.writeProduct(unwrapped_read, fn, "BEAM-DIMAP")
    # unwrapped = ProductIO.readProduct(fn)
    # snaphu_files = jpy.array('org.esa.snap.core.datamodel.Product', 2)
    # snaphu_files[0] = inputfile
    # snaphu_files[1] = unwrapped
    # result_SI = GPF.createProduct("SnaphuImport", parameters, snaphu_files)
    # result_PD = GPF.createProduct("PhaseToDisplacement", parameters, result_SI)
    # outpath = os.path.join(path2zipfolder, 'DisplacementVert')
    # # ProductIO.writeProduct(SNAPHU_exp_folder, filename + '.dim', 'BEAM-DIMAP')
    # ProductIO.writeProduct(result_PD, SNAPHU_exp_folder, "BEAM-DIMAP")
    print('Phase unwrapping performed successfully.')

def do_subset_band(source, wkt):
    print('\tSubsetting...')
    parameters = HashMap()
    parameters.put('geoRegion', wkt)
    # parameters.put('outputImageScaleInDb', True)
    output = GPF.createProduct('Subset', parameters, source)
    return output


def do_terrain_correction(source, band):
    # def do_terrain_correction(source, proj, downsample):
    print('\tTerrain correction...')
    parameters = HashMap()
    parameters.put('demName', 'Copernicus 30m Global DEM')  # 'SRTM 3Sec'
    #    parameters.put('imgResamplingMethod', 'BILINEAR_INTERPOLATION')
    #    #parameters.put('mapProjection', proj)       # comment this line if no need to convert to UTM/WGS84, default is WGS84
    #    parameters.put('saveProjectedLocalIncidenceAngle', False)
    parameters.put('sourceBands', band)
    parameters.put('saveSelectedSourceBand', True)
    #    parameters.put('nodataValueAtSea', False)
    # parameters.put('pixelSpacingInMeter', 35)
    #    while downsample == 1:                      # downsample: 1 -- need downsample to 40m, 0 -- no need to downsample
    #        parameters.put('pixelSpacingInMeter', 40.0)
    #        break
    output = GPF.createProduct('Terrain-Correction', parameters, source)
    return output


def write(product, filename):
    ProductIO.writeProduct(product, filename, "GeoTiff")


def write_BEAM_DIMAP_format(product, filename):
    print('Saving BEAM-DIMAP format.')
    ProductIO.writeProduct(product, filename + '.dim', 'BEAM-DIMAP')


# %%
# Input variables
file_path = r"home/data"

# should be "before" image
filename_1 = os.path.join(file_path, 'S1B_IW_SLC__1SDV_20190831T045510_20190831T045537_017825_0218B6_491E.zip')

# should be "after" image
filename_2 = os.path.join(file_path, 'S1A_IW_SLC__1SDV_20190825T045538_20190825T045605_028721_03406F_847F.zip')

out_filename_pipeline1 = os.path.join(file_path, 'out_pipe_I')
out_filename_pipeline2 = os.path.join(file_path, 'out_pipe_II')
out_filename_pipeline3 = os.path.join(file_path, 'out_pipe_III')
snaphu_unwrap_folder = os.path.join(file_path, "snaphu")

# %%

if not os.path.exists(snaphu_unwrap_folder):
    os.mkdir(snaphu_unwrap_folder)

IW = 'IW3'
polarization = 'VV'
firstBurstIndex1 = 3
lastBurstIndex1 = 4
firstBurstIndex2 = 8
lastBurstIndex2 = 9


def InSAR_pipeline_I(filename_1, filename_2, IW, firstBurstIndex1, firstBurstIndex2,
                     lastBurstIndex1, lastBurstIndex2, out_filename):
    product_1 = read(filename_1)
    product_2 = read(filename_2)
    product_TOPSAR_1 = topsar_split(product_1, IW, firstBurstIndex1, lastBurstIndex1)
    product_TOPSAR_2 = topsar_split(product_2, IW, firstBurstIndex2, lastBurstIndex2)
    product_orbitFile_1 = apply_orbit_file(product_TOPSAR_1)
    product_orbitFile_2 = apply_orbit_file(product_TOPSAR_2)
    product = back_geocoding([product_orbitFile_1, product_orbitFile_2])
    product = Enhanced_Spectral_Diversity(product)
    write_BEAM_DIMAP_format(product, out_filename)
    print("InSAR_pipeline_I complete")


def InSAR_pipeline_II(in_filename, ML_nRgLooks, out_filename_II):
    product = read(in_filename)  # reads .dim
    product = interferogram(product)
    product = topsar_deburst(product)
    # product = topophase_removal(product)
    # Insert subset here
    product = Multilook(product, ML_nRgLooks=ML_nRgLooks)
    product = goldstein_phasefiltering(product)
    # product = do_terrain_correction(product)
    write_BEAM_DIMAP_format(product, out_filename_II)
    print("InSAR_pipeline_II complete")


def InSAR_pipeline_III(in_filename_III, out_filename_III):
    product = read(in_filename_III)  # reads .dim
    band_names = product.getBandNames()
    # print("Band names: {}".format(", ".join(band_names)))
    a = format(", ".join(band_names))  # band names as a comma separated string
    b = a.split(',')  # split string into list
    # change band names as to mintpy accepts them
    product.getBand(b[3].strip()).setName('Phase_ifg')
    product.getBand(b[4].strip()).setName('coh')
    # interferogram_TC = do_terrain_correction(product,band='Phase_ifg') # interferogram terrain correction
    # write_BEAM_DIMAP_format(interferogram_TC, out_filename_III+'_filt_int_sub_tc')
    coherence_TC = do_terrain_correction(product, band='coh')  # coherence terrain correction
    write_BEAM_DIMAP_format(coherence_TC, out_filename_III + '_coh_tc')
    print("InSAR_pipeline_III complete")


# InSAR_pipeline_I(filename_1, filename_2, IW, firstBurstIndex1, lastBurstIndex1,
#                 firstBurstIndex2, lastBurstIndex2, out_filename_pipeline1)
# InSAR_pipeline_II(out_filename_pipeline1 + ".dim", 6, out_filename_pipeline2)
# InSAR_pipeline_III(out_filename_pipeline2 + ".dim", out_filename_pipeline3)
#
SNAPHU_export(read(out_filename_pipeline2 + "_subset.dim"), snaphu_unwrap_folder, tiles=3)
# SNAPHU_export(read(out_filename_pipeline2 + ".dim"), snaphu_unwrap_folder, tiles=1)
# snaphu_unwrapping(snaphu_unwrap_folder)
