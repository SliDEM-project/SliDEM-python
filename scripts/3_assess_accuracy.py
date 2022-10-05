import argparse
import os.path
import xdem
import csv
import geoutils as gu
import glob
import numpy as np
import matplotlib.pyplot as plt
import scicomap as sc

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
    '--s1_dem_dir',
    type=str,
    help='''relative path (refers to mounted volume) to the directory where
    the results of the DEM generation step are stored.
    If the file structures and naming was not altered, the script will look
    for the file with the ending `_elevation.tiff`.'''
)
parser.add_argument(
    '--s1_dem_path',
    type=str,
    help='''path to S1-based DEM to be assessed for errors. Ignored if
    s1_dem_dir is set.'''
)
parser.add_argument(
    '--unstable_area_path',
    type=str,
    help='''path to spatial file (WGS84 - EPSG:4326) 
    with the outline for unstable areas (e.g. mass movement areas). 
    This can include any other area that should be ignored during 
    accuracy assessment (e.g. water areas, dense vegetation, etc.).
    If absent then the whole AOI is used for error analysis.'''
)
parser.add_argument(
    '--ref_dem_path',
    type=str,
    help='''path to external DEM to use for error assessment 
    (and vertical co-registration if coregister=True). 
    Use 3_1_aux_data_download.py to download elevation
    data from OpenTopography for your area of interest.'''
)
parser.add_argument(
    '--coregister',
    action='store_true',
    help='''Call this flag if the S1 DEM should be coregistered
    vertically to the reference DEM'''
)
parser.add_argument(
    '--coregistration_method',
    nargs="+",
    default=["NuthKaab", "Deramp_d1"],
    help='''List of xdem.coreg functions to set-up a coregistration algorithm
    Defaults to Nuth-Kaab (NuthKaab) and Deramping with degree 1 (Deramp_d1). 
    Options are:
    "NuthKaab"
    "Deramp_d1"
    "Deramp_d2"
    "Deramp_d3"
    "ICP"
    "BiasCorr"
    Combined coregistration pipelines: 
    "NuthKaab_Deramp_d1"
    "ICP_NuthKaab"
    "BiasCorr_ICP_NuthKaab"
    '''
)
parser.add_argument(
    '--lulc_path',
    type=str,
    default=None,
    help='''path to LULC raster dataset to use for error assessment. 
    Use 3_1_aux_data_download.py to download WorldCover LULC data 
    from the AWS S3 Bucket for your area of interest.'''
)
parser.add_argument(
    '--ref_dem_name',
    type=str,
    help='''shorter name for external DEM used. 
    Used to determine output file names.'''
)
parser.add_argument(
    '--acc_output_dir',
    type=str,
    default='accuracy',
    help='''name of the directory where the accuracy assessment should 
    be saved into. It defaults to a sub-directory inside the `s1_dem_dir` 
    named "accuracy".'''
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
# If directory to DEM generation output folder is given,
# then create the directory inside this folder
if args.s1_dem_dir is not None:
    accuracy_dir = os.path.join(args.s1_dem_dir, args.acc_output_dir)
    if not os.path.exists(accuracy_dir):
        os.mkdir(accuracy_dir)
# Otherwise just create the given folder for the accuracy assessment
else:
    accuracy_dir = args.acc_output_dir
    if not os.path.exists(accuracy_dir):
        os.mkdir(accuracy_dir)

# Naming for files
if args.ref_dem_name is None:
    ref_dem_name = args.ref_dem_path.split('/', -1)[-1].replace('.tif', '')
else:
    ref_dem_name = args.ref_dem_name

if args.s1_dem_path is not None:
    s1_dem_path = args.s1_dem_path
else:
    s1_dem_path = glob.glob(os.path.join(args.s1_dem_dir,
                                         str("*_elevation.tif")))[0]

s1_dem_name = s1_dem_path.split('/', -1)[-1].replace('.tif', '')

# Error assessment with xdem
reference_dem = xdem.DEM(args.ref_dem_path)
s1_dem = xdem.DEM(s1_dem_path)
if args.lulc_path is not None:
    lulc = gu.Raster(args.lulc_path)
    lulc_resampled = lulc.reproject(s1_dem, resampling="bilinear")

# Assign no data value if needed
s1_dem.set_nodata(args.no_data_value,
                  update_array=True, update_mask=True)

# Reproject reference DEM to S1 DEM
reference_dem = reference_dem.reproject(s1_dem)

# Unstable areas
unstable = gu.Vector(args.unstable_area_path)
unstable = gu.Vector(unstable.ds.to_crs(s1_dem.crs))

prefix_before = "error_" + ref_dem_name + "_S1_" + s1_dem_name

# Write error measurements to CSV file
header = [
    's1_dem', 'ref_dem',
    'lulc', 's1_dem_coreg',
    'min_error', 'max_error', 'mean_error',
    'std_error', 'mae', 'rmse', 'nmad'
]
csv_file = os.path.join(
    accuracy_dir,
    "error_S1_" + s1_dem_name + '.csv'
)

if not os.path.exists(csv_file):
    with open(csv_file, 'w', encoding='UTF8') as f:
        writer = csv.writer(f)

        # write the header
        writer.writerow(header)


# Function to compute errors
def compute_errors(src, ref, prefix, coreg_filename=None):
    # Calculate DEM error (dh)
    dh = ref - src
    dh_file = os.path.join(
        accuracy_dir,
        prefix + ".tif"
    )
    dh.save(dh_file)

    dem_ls = [ref, src, dh]
    # Plot
    plt.figure(figsize=(16, 4), dpi=300.0, tight_layout=True)
    plt_extent = [
        dh.bounds.left,
        dh.bounds.right,
        dh.bounds.bottom,
        dh.bounds.top,
    ]
    cmaps = ['viridis', 'viridis', sc.ScicoDiverging(cmap='vik').get_mpl_color_map()]
    vlims = [(None, None) for i in range(3)]
    vlims[0] = [np.nanmin(ref.data), np.nanmax(ref.data)]
    vlims[1] = vlims[0]
    vlims[2] = [-args.elev_diff_min_max, args.elev_diff_min_max]
    labels = [
        'Elevation (m)',
        'Elevation (m)',
        'Elevation difference (m)'
    ]
    titles = [
        'Reference DEM',
        'S1 DEM',
        'Reference - S1 DEM'
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
            accuracy_dir,
            prefix + ".png"
        )
    )

    dh = gu.Raster(dh_file)
    mask = ~unstable.create_mask(dh)

    # Keep only stable terrain data
    dh.set_mask(np.invert(mask))

    # Compute terrain attributes for reference DEM
    attr_list = ["hillshade", "slope", "aspect", "curvature",
                 "terrain_ruggedness_index", "rugosity"]
    attributes_ref_dem = xdem.terrain.get_terrain_attribute(
        dem=ref.data,
        resolution=dh.res,
        attribute=attr_list
    )
    attributes_src_dem = xdem.terrain.get_terrain_attribute(
        dem=src.data,
        resolution=dh.res,
        attribute=attr_list
    )

    # Plot attributes for ref and src
    def plot_attr(dem, attributes):
        plt.figure(figsize=(8.2, 7), dpi=300.0, tight_layout=True)

        plt_extent = [dem.bounds.left, dem.bounds.right, dem.bounds.bottom, dem.bounds.top]

        cmaps = ["Greys_r", "Reds", "twilight", "RdGy_r", "Purples", "YlOrRd"]
        labels = ["Hillshade", "Slope (°)", "Aspect (°)", "Curvature (100 / m)",
                  "Terrain Ruggedness Index", "Rugosity"]
        vlims = [(None, None) for i in range(6)]
        vlims[3] = [-2, 2]

        for i in range(6):
            plt.subplot(3, 2, i + 1)
            plt.imshow(
                attributes[i].squeeze(),
                cmap=cmaps[i],
                extent=plt_extent,
                vmin=vlims[i][0], vmax=vlims[i][1]
            )
            cbar = plt.colorbar()
            cbar.set_label(labels[i])
            plt.xticks([])
            plt.yticks([])

        return plt

    plot_attr_ref = plot_attr(ref, attributes_ref_dem)
    plot_attr_ref.savefig(
        os.path.join(
            accuracy_dir,
            "terrain_attributes_" + ref_dem_name + ".png"
        ),
        dpi=300, bbox_inches='tight'
    )

    plot_attr_src = plot_attr(src, attributes_src_dem)
    plot_attr_src.savefig(
        os.path.join(
            accuracy_dir,
            "terrain_attributes_" + s1_dem_name + ".png"
        ),
        dpi=300, bbox_inches='tight'
    )

    # Compute measures
    # Write error measures data to csv file
    with open(csv_file, 'a', encoding='UTF8') as f:
        writer = csv.writer(f)

        # data input
        data = [
            s1_dem_path, args.ref_dem_path,
            (args.lulc_path if args.lulc_path else "Not used"),
            (coreg_filename if coreg_filename else "Before coregistration"),
            np.nanmin(dh.data), np.nanmax(dh.data), np.nanmean(dh.data),
            np.nanstd(dh.data),
            np.nanmean(np.abs(dh.data)),
            np.sqrt((dh.data ** 2).mean()), xdem.spatialstats.nmad(dh.data)
        ]
        # write the data
        writer.writerow(data)

    # Estimate the measurement error by bin of slope,
    # using a desired error measure as robust estimator
    # defaults to count and nmad
    variables = [attributes_ref_dem[1].ravel(), attributes_ref_dem[2].ravel()]
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
            accuracy_dir,
            'binned_stats_' + prefix + ".csv"
        ),
        index=False
    )

    # Plot binned elevation
    xdem.spatialstats.plot_1d_binning(
        df_ns, 'slope', 'nmad',
        'Slope (degrees) calculated from Reference DEM',
        'Elevation error: NMAD (m)'
    )

    plt.savefig(
        os.path.join(
            accuracy_dir,
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
            accuracy_dir,
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
                accuracy_dir,
                prefix + "_nmad_binned_lulc.png"
            ),
            dpi=300, bbox_inches='tight'
        )

    # if coreg_filename is not None:


def coregister_func(coregister_name):
    match coregister_name:
        case "NuthKaab":
            return xdem.coreg.NuthKaab()
        case "Deramp_d1":
            return xdem.coreg.Deramp(degree=1)
        case "Deramp_d2":
            return xdem.coreg.Deramp(degree=2)
        case "Deramp_d3":
            return xdem.coreg.Deramp(degree=3)
        case "ICP":
            return xdem.coreg.ICP()
        case "BiasCorr":
            return xdem.coreg.BiasCorr()
        case "NuthKaab_Deramp_d1":
            return xdem.coreg.NuthKaab() + xdem.coreg.Deramp(degree=1)
        case "ICP_NuthKaab":
            return xdem.coreg.ICP() + xdem.coreg.NuthKaab()
        case "BiasCorr_ICP_NuthKaab":
            return xdem.coreg.BiasCorr() + xdem.coreg.ICP() + xdem.coreg.NuthKaab()


def coregister(src, ref, coreg_type):
    coregister_function = coregister_func(coreg_type)
    unstable_mask = ~unstable.create_mask(ref)
    coregister_function.fit(
        ref.data, src.data,
        inlier_mask=unstable_mask,
        transform=ref.transform
    )
    out = xdem.DEM.from_array(
        coregister_function.apply(src.data, transform=src.transform),
        transform=src.transform,
        crs=src.crs,
        nodata=args.no_data_value
    )
    prefix_file = s1_dem_name + '_' + ref_dem_name + '_coreg_' + coreg_type
    prefix_after = "error_" + ref_dem_name + "_S1_" + s1_dem_name + '_coreg_' + coreg_type
    filename = os.path.join(
        accuracy_dir,
        prefix_file + '.tif'
    )
    out.save(filename)
    s1_dem_coregistered = xdem.DEM(filename)
    # Assign no data value if needed
    s1_dem_coregistered.set_nodata(args.no_data_value,
                                   update_array=True, update_mask=True)
    compute_errors(
        s1_dem_coregistered,
        ref,
        prefix_after,
        coreg_filename=filename
    )
    dh_before = (ref - src).data[np.invert(unstable_mask)]
    dh_after = (ref - s1_dem_coregistered).data[np.invert(unstable_mask)]
    nmad_before = xdem.spatialstats.nmad(dh_before)
    nmad_after = xdem.spatialstats.nmad(dh_after)
    # Make histogram with values before and after coregistration
    plt.figure(figsize=(6, 6.7), dpi=300.0, tight_layout=True)
    plt.title(f"NMAD before: {nmad_before:.2f} m, "
              f"NMAD after: {nmad_after:.2f} m")
    plt.hist(dh_before,
             bins=np.linspace(-args.elev_diff_min_max, args.elev_diff_min_max, 100),
             alpha=0.75, label="Before coregistration")
    plt.hist(dh_after, facecolor='g',
             bins=np.linspace(-args.elev_diff_min_max, args.elev_diff_min_max, 100),
             alpha=0.75, label="After coregistration")
    plt.legend(loc='upper right')
    plt.savefig(
        os.path.join(
            accuracy_dir,
            prefix_after + "_hist.png"
        ),
        dpi=300, bbox_inches='tight'
    )
    return out


# Compute errors before coregistration
compute_errors(s1_dem, reference_dem, prefix_before)

# Coregister and compute errors
if args.coregister:
    coreg_list = []
    for c in args.coregistration_method:
        s1_dem_coreg = coregister(s1_dem, reference_dem, c)
        coreg_list.append(s1_dem_coreg)
