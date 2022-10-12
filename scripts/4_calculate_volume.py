import argparse
import os.path
import xdem
import csv
import geoutils as gu
import numpy as np
import matplotlib.pyplot as plt

# Arguments
parser = argparse.ArgumentParser(
    description='''Calculate volumes from DEM differencing
    to characterise volumetric changes between post- and pre-event 
    DEMs. The subtraction indicates then positive volumes as deposition
    and negative volumes as erosion. The computation also takes into 
    account the error propagation of the pre- and post-event DEMs
    based on a given reference DEM, if given. 
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
    default='volume',
    help='''relative path (refers to mounted volume) to the directory where'
  results should be written into'''
)
parser.add_argument(
    '--unstable_area_path',
    type=str,
    help='''path to spatial file (WGS84 - EPSG:4326) 
    with the outline for unstable areas (e.g. mass movement areas). 
    This can include any other area that should be ignored during 
    the computation of error propagation 
    (e.g. water areas, dense vegetation, etc.).
    If absent then the whole AOI is used for error analysis.'''
)
parser.add_argument(
    '--dem_pre_path',
    type=str,
    help='''path to DEM corresponding to the pre-event time.'''
)
parser.add_argument(
    '--dem_pos_path',
    type=str,
    help='''path to DEM corresponding to the post-event time.'''
)
parser.add_argument(
    '--ref_dem_path',
    type=str,
    help='''path to external DEM to use for error assessment.
    Use 3_1_aux_data_download.py to download elevation
    data from OpenTopography for your area of interest.'''
)
parser.add_argument(
    '--no_data_value',
    type=float,
    default=-99999,
    help='''Value to use for no data, defaults to -99999'''
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

# Create output_dir if not existing
if not os.path.exists(args.output_dir):
    os.mkdir(args.output_dir)

# Read in DEMs
dem_pre = xdem.DEM(args.dem_pre_path)
dem_pos = xdem.DEM(args.dem_pos_path)
reference_dem = xdem.DEM(args.ref_dem_path)

# Get DEM names
dem_pre_name = os.path.basename(args.dem_pre_path).split('.')[0]
dem_pos_name = os.path.basename(args.dem_pos_path).split('.')[0]

# Assign no data value if needed
dem_pre.set_nodata(args.no_data_value)
dem_pos.set_nodata(args.no_data_value)

# Reproject reference DEM to S1 DEM
dem_pos = dem_pos.reproject(dem_pre)
reference_dem = reference_dem.reproject(dem_pre)

# Unstable areas
unstable = gu.Vector(args.unstable_area_path)
unstable = gu.Vector(unstable.ds.to_crs(dem_pre.crs))

dh = dem_pos - dem_pre
dh.save(os.path.join(
    args.output_dir,
    "dod_" + dem_pos_name + "_" + dem_pre_name + ".tif"
))
mask = ~unstable.create_mask(dem_pre)

# Compute errors only on stable terrain
ref_pre = (reference_dem - dem_pre)
ref_pre.set_mask(np.invert(mask))

ref_pos = (reference_dem - dem_pos)
ref_pos.set_mask(np.invert(mask))

# Compute elevation difference on unstable terrain
difference = dh.copy()
difference.set_mask(mask)
difference.save(os.path.join(
    args.output_dir,
    "dod_" + dem_pos_name + "_" + dem_pre_name + "_crop.tif"
))

difference_source = difference.copy()
mask_source = difference_source.data < 0
difference_source.set_mask(mask_source)

difference_depost = difference.copy()
mask_depost = difference_depost.data > 0
difference_depost.set_mask(mask_depost)

area_pixel = dem_pre.res[0] * dem_pre.res[1]

n_tot = dem_pre.shape[0] * dem_pre.shape[1]
n = np.sqrt(n_tot * dem_pre.res[0])/(2 * (20 * dem_pre.res[0]))
sde_pre = np.nanstd(ref_pre.data)/n
sde_pos = np.nanstd(ref_pos.data)/n
prop_error_sde = np.sqrt((sde_pre ** 2) + (sde_pos ** 2))

nmad_pre = xdem.spatialstats.nmad(ref_pre.data)
nmad_pos = xdem.spatialstats.nmad(ref_pos.data)
prop_error_nmad = np.sqrt((nmad_pre ** 2) + (nmad_pos ** 2))


def calc_total_area(diff):
    return (np.count_nonzero(diff.data) - np.sum(np.isnan(diff.get_nanarray()))) * area_pixel


def calc_pixels(diff):
    return np.count_nonzero(diff.data) - np.sum(np.isnan(diff.get_nanarray()))


def calc_volume(diff):
    return np.nansum(diff.data * area_pixel)


def calc_volume_error(area_tot, prop_error):
    return area_tot * prop_error


# Write error measurements to CSV file
header = [
    'dem_pre', 'dem_pos',
    'ref_dem',
    'nmad_dem_pre_m', 'nmad_dem_pos_m',
    'sde_dem_pre_m', 'sde_dem_pos_m',
    'zone', 'area_m2', 'pixels', 'vol_m3',
    'nmad_prop_err_m',
    'vol_error_nmad_m3',
    'sde_prop_err_m',
    'vol_error_sde_m3'
]

csv_file = os.path.join(
    args.output_dir,
    "volume_estimates.csv"
)

if not os.path.exists(csv_file):
    with open(csv_file, 'w', encoding='UTF8') as f:
        writer = csv.writer(f)

        # write the header
        writer.writerow(header)

with open(csv_file, 'a', encoding='UTF8') as f:
    writer = csv.writer(f)
    # write the data
    diff_ls = [difference, difference_source, difference_depost]
    diff_nm = ['total', 'source', 'deposition']
    for i in range(3):
        data = [
            args.dem_pre_path, args.dem_pos_path,
            args.ref_dem_path,
            nmad_pre, nmad_pos,
            sde_pre, sde_pos,
            diff_nm[i],
            calc_total_area(diff_ls[i]),
            calc_pixels(diff_ls[i]),
            calc_volume(diff_ls[i]),
            prop_error_nmad,
            calc_volume_error(calc_total_area(diff_ls[i]), prop_error_nmad),
            prop_error_sde,
            calc_volume_error(calc_total_area(diff_ls[i]), prop_error_sde)
        ]
        writer.writerow(data)

plt.title('Elevation difference (m) in landslide area\nPost-event minus Pre-event')
plt.hist(difference.data.flatten(),
         bins=np.linspace(-args.elev_diff_min_max, args.elev_diff_min_max, 100))
plt.savefig(
    os.path.join(
        args.output_dir,
        "elevdiff_" + dem_pos_name + "_" + dem_pre_name + "_hist.png"
    )
)
plt.close()

dem_ls = [dem_pre, dem_pos, dh]
# Plot
plt.figure(figsize=(16, 4), dpi=300.0, tight_layout=True)
plt_extent = [
    dh.bounds.left,
    dh.bounds.right,
    dh.bounds.bottom,
    dh.bounds.top,
]
cmaps = ['viridis', 'viridis', 'PuOr']
vlims = [(None, None) for i in range(3)]
vlims[0] = [np.nanmin(dem_pre.data), np.nanmax(dem_pre.data)]
vlims[1] = vlims[0]
vlims[2] = [-args.elev_diff_min_max, args.elev_diff_min_max]
labels = [
    'Elevation (m)',
    'Elevation (m)',
    'Elevation difference (m)'
]
titles = [
    'Pre-event DEM',
    'Post-event DEM',
    'Post-event - Pre-event'
]
for i in range(3):
    plt.subplot(1, 3, i + 1)
    ax = plt.gca()
    unstable.ds.plot(ax=ax, fc='none', ec='k')
    ax.plot([], [], color='k', label='Unstable areas')
    plt.imshow(
        dem_ls[i].data.squeeze(),
        cmap=cmaps[i],
        extent=plt_extent,
        vmin=vlims[i][0], vmax=vlims[i][1]
    )
    cbar = plt.colorbar()
    cbar.set_label(labels[i])
    plt.xticks([])
    plt.yticks([])
    plt.legend(loc='lower right')
    plt.title(titles[i])

plt.savefig(
    os.path.join(
        args.output_dir,
        "elevdiff_" + dem_pos_name + "_" + dem_pre_name + ".png"
    )
)
plt.close()
