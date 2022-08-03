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
import os.path
import xdem
import geoutils as gu
import numpy as np
import matplotlib.pyplot as plt

# Arguments
parser = argparse.ArgumentParser(
    description='''Perform an accuracy assessment of the S1-DEMs.
    Pass an external DEM for comparison. 
    Use LULC (e.g. WorldCover) data to get binned statistics.
    You can download subsets of external DEMs and WorldCover data
    for your AOI through the OpenTopography API and AWS-S3 buckets
    with the 3_1_aux_data_download.py. 
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
    '--no_data_value',
    type=float,
    default=-99999,
    help='''Value to use for no data, defaults to -99999'''
)
parser.add_argument(
    '--ref_dem_path',
    type=str,
    help='''path to external DEM to use for error assessment. 
    If you have already downloaded data previously from OpenTopography for 
    your area of interest, please add the path to the data here 
    and avoid re-fetching.'''
)
parser.add_argument(
    '--lulc_path',
    type=str,
    default=None,
    help='''path to LULC rasterdataset to use for error assessment. 
    If you have already downloaded WorldCover data for 
    your area of interest, please add the path to the data here 
    and avoid re-fetching.'''
)
parser.add_argument(
    '--ref_dem_name',
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
    '--elev_diff_min_max',
    type=float,
    default=20,
    help='''Absolute value to plot elevation differences,
     what should be the minimum and maximum elevation difference value? 
     Defaults to -20, +20.'''
)
args = parser.parse_args()

os.chdir('home/')

# Naming for files
if args.ref_dem_name is None:
    ref_dem_name = args.ref_dem_path.split('/', -1)[-1].replace('.tif', '')
else:
    ref_dem_name = args.ref_dem_name

s1_dem_name = args.s1_dem_path.split('/', -1)[-1].replace('.tif', '')
prefix = "error_" + ref_dem_name + "_S1_" + s1_dem_name

# Error assessment with xdem
reference_dem = xdem.DEM(args.ref_dem_path)
s1_dem = xdem.DEM(args.s1_dem_path)
if args.lulc_path is not None:
    lulc = gu.Raster(args.lulc_path)
    lulc_resampled = lulc.reproject(s1_dem, resampling="bilinear")

# Assign no data value if needed
s1_dem.set_ndv(args.no_data_value)

# Reproject reference DEM to S1 DEM
reference_dem = reference_dem.reproject(s1_dem)

# Calculate DEM error (dh)
dh = reference_dem - s1_dem
dh_file = os.path.join(
    args.output_dir,
    prefix + ".tif"
)
dh.save(dh_file)

# Unstable areas
unstable = gu.Vector(args.unstable_area_path)
unstable = gu.Vector(unstable.ds.to_crs(s1_dem.crs))

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
        prefix + ".png"
    ),
    dpi=300, bbox_inches='tight'
)

dh = gu.Raster(dh_file)
mask = ~unstable.create_mask(dh)

# Keep only stable terrain data
dh.set_mask(np.invert(mask))

# Compute slope and aspect for reference DEM in stable areas
slope, aspect = \
    xdem.terrain.get_terrain_attribute(
        dem=reference_dem.data,
        resolution=dh.res,
        attribute=['slope', 'aspect']
    )

# Estimate the measurement error by bin of slope,
# using a desired error measure as robust estimator
# defaults to count and nmad
variables = [slope.ravel(), aspect.ravel()]
variables_names = ['slope', 'aspect']
variables_bins = [30, 30]
if args.lulc_path is not None:
    variables.append(lulc_resampled.data.ravel())
    variables_names.append('lulc')
    variables_bins.append(len(np.unique(lulc_resampled.data.ravel())))
df_ns = xdem.spatialstats.nd_binning(
    dh.data.ravel(),
    list_var=variables,
    list_var_names=variables_names,
    statistics=['count', xdem.spatialstats.nmad],
    list_var_bins=variables_bins
)

df_ns[df_ns.nd == 1].to_csv(
    os.path.join(
        args.output_dir,
        'error_measures_' + ref_dem_name + "_binned_stats.csv"
    ),
    index=False
)
xdem.spatialstats.plot_1d_binning(
    df_ns, 'slope', 'nmad',
    'Slope (degrees) calculated from Reference DEM',
    'Elevation error: NMAD (m)'
)

plt.savefig(
    os.path.join(
        args.output_dir,
        prefix + "_nmad_binned_slope.png"
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
        prefix + "_nmad_binned_aspect.png"
    ),
    dpi=300, bbox_inches='tight'
)

if args.lulc_path is not None:
    xdem.spatialstats.plot_1d_binning(
        df_ns, 'lulc', 'nmad',
        'LULC',
        'Elevation error: NMAD (m)'
    )

    plt.savefig(
        os.path.join(
            args.output_dir,
            prefix + "_nmad_binned_lulc.png"
        ),
        dpi=300, bbox_inches='tight'
    )
# Compute measures
# Write user settings to log file
file = open(os.path.join(args.output_dir, 'error_measures_' + ref_dem_name + '.txt'), 'w')
file.write(
    'S1 DEM: ' + args.s1_dem_path + '\n' +
    'Reference DEM: ' + args.ref_dem_path + '\n' +
    'LULC: ' + (args.lulc_path if args.lulc_path else "Not used") + '\n' +
    '\nReference DEM - S1 DEM:\n' +
    'Error measures \n' +
    'Min: {:.2f} m'.format(np.nanmin(dh.data)) + '\n' +
    'Max: {:.2f} m'.format(np.nanmax(dh.data)) + '\n' +
    'Mean: {:.2f} m'.format(np.nanmean(dh.data)) + '\n' +
    'STD: {:.2f} m'.format(np.nanstd(dh.data)) + '\n' +
    'MAE: {:.2f} m'.format(np.nanmean(np.abs(dh.data))) + '\n' +
    'RMSE: {:.2f} m'.format(np.sqrt((dh.data**2).mean())) + '\n' +
    'NMAD: {:.2f} m'.format(xdem.spatialstats.nmad(dh.data)) + '\n'
)
file.close
