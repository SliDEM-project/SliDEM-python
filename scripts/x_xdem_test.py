import os.path

import xdem
import geoutils as gu

# reference_dem = xdem.DEM("home/data/ref_dem/NDH_Alta_2pkt_2018_DTM.tif")
# reference_dem = xdem.DEM("home/data/ref_dem/dgm5m_con.tif")
reference_dem = xdem.DEM("home/data/ref_dem/dgm_50413_1m_32633.tif")
# reference_dem = xdem.DEM("home/data/ref_dem/dgm_50413.tif")
# reference_dem = xdem.DEM("home/data/ref_dem/Gjerdrum_Ullensaker_Nannestad_5pkt_DTM_2020_subset.tif")
# dem_to_be_aligned = xdem.DEM("home/data/ref_dem/AltaLandslide_UAV_DTM_EPSG25835_50cm.tif")
# dem_to_be_aligned = xdem.DEM("home/data/ref_dem/Huttschlag_Austria_UAV_Oct2021_DTM_1m_clipped.tif")
# dem_to_be_aligned = xdem.DEM("home/data/tests/test_pipes_kleinarl/pre_event_2017/out_P4.data/elevation_VV_20170706_0718.tif")
# dem_to_be_aligned = xdem.DEM("home/data/tests/test_pipes_grossarl/pre_event_201808/out_P4.data/elevation_VV_20180830_0905.tif")
# dem_to_be_aligned = xdem.DEM("home/data/tests/test_pipes_grossarl/pos_event_201908/out_P4.data/elevation_VV_20190801_0807.tif")
# dem_to_be_aligned = xdem.DEM(
#     "home/data/tests/test_pipes_grossarl/pos_event_201907/out_P4.data/elevation_VV_20190726_0801.tif")
# dem_to_be_aligned = xdem.DEM(
#     "home/data/tests/test_pipes_grossarl/pos_event_202006_07_08/elevation_VV_20200608_0813.tif")
# dem_to_be_aligned = xdem.DEM(
#     "home/data/tests/test_pipes_grossarl/out_20200712_20200730/elevation_VV_20200712_0730.tif")
# dem_to_be_aligned = xdem.DEM(
#     "home/data/tests/test_pipes_grossarl/out_20200712_20200730/coreg/elevation_VV_20200712_0730_dgm1m_coreg_deramp3_aoi.tif"
# )
# dem_to_be_aligned = xdem.DEM(
#     "home/data/tests/test_pipes_grossarl/pre_event_201808/out_P4.data/coreg/elevation_VV_20180830_0905_dgm1m_coreg_deramp3_aoi.tif"
# )
# dem_to_be_aligned = xdem.DEM(
#     "home/data/tests/test_pipes_grossarl/out_20170624_20170718/coreg_2/elevation_VV_20170624_0718_dgm1m_coreg_deramp3_aoi.tif"
# )
dem_to_be_aligned = xdem.DEM(
    'home/data/tests/test_pipes_grossarl/pos_event_202006_07_08/coreg/elevation_VV_20200720_0825_dgm1m_coreg_deramp3_Aoi.tif'
)
# dem_to_be_aligned = xdem.DEM(
#     "home/data/tests/test_pipes_grossarl/out_20170624_20170718/elevation_VV_20170624_0718.tif"
# )
# dem_to_be_aligned = xdem.DEM(
#     "home/data/tests/test_pipes_grossarl/pos_event_202006_07_08/elevation_VV_20200720_0825.tif")
# dem_to_be_aligned = xdem.DEM("home/data/tests/test_pipes_grossarl/pos_event_202006/elevation_VV_20200602_0813.tif")
# dem_to_be_aligned = xdem.DEM("home/data/tests/test_pipes_alta/pre_event_201906/elevation_VV_20190612_0618.tif")
# dem_to_be_aligned = xdem.DEM("home/data/tests/test_pipes_alta/pos_event_202006/elevation_VV_20200605_0729.tif")
# dem_to_be_aligned = xdem.DEM("home/data/tests/test_pipes_alta/pos_event_202006_08/elevation_VV_20200605_0810.tif")
# dem_to_be_aligned = xdem.DEM("home/data/tests/test_pipes_gjerdrum/pos_event_202106_1/elevation_20210603_0609.tif", bands=1)
# dem_to_be_aligned = xdem.DEM("home/data/tests/test_pipes_gjerdrum/pos_event_202106_07/elevation_20210604_0710.tif", bands=1)
# dem_to_be_aligned = xdem.DEM("home/data/tests/test_pipes_gjerdrum/pre_event_202008/out_P4.data/elevation_vv.tif")
# dem_to_be_aligned = xdem.DEM("home/data/tests/test_pipes_gjerdrum/pre_event_202008_1/out_P4.data/elevation_vv.tif")
# dem_to_be_aligned = xdem.DEM("home/data/tests/test_pipes_gjerdrum/pre_event_202008_2/elevation_20200825_0831.tif")

# Assign no data value if needed
# dem_to_be_aligned.set_ndv(-9999)
# Reproject reference dem to dem to be aligned
reference_dem = reference_dem.reproject(dem_to_be_aligned)

# set unstable areas
# landslide = gu.Vector("home/data/ref_dem/Alta_unstable_area.shp")
# landslide = gu.Vector("home/data/ref_dem/gjerdrum_unstable_area.gpkg")
landslide = gu.Vector("home/data/ref_dem/arl_unstable_area.gpkg")

# Create a stable ground mask (not slided) to mark "inlier data"
inlier_mask = ~landslide.create_mask(reference_dem)

# Set-up coregistration
nuth_kaab = xdem.coreg.NuthKaab()
nuth_kaab.fit(reference_dem.data, dem_to_be_aligned.data, inlier_mask=inlier_mask, transform=reference_dem.transform)
aligned_dem_data_nk = nuth_kaab.apply(dem_to_be_aligned.data, transform=dem_to_be_aligned.transform)

deramp = xdem.coreg.Deramp(degree=1)
deramp.fit(reference_dem.data, dem_to_be_aligned.data, inlier_mask=inlier_mask, transform=reference_dem.transform)
aligned_dem_data_deramp = deramp.apply(dem_to_be_aligned.data, transform=dem_to_be_aligned.transform)

deramp2 = xdem.coreg.Deramp(degree=2)
deramp2.fit(reference_dem.data, dem_to_be_aligned.data, inlier_mask=inlier_mask, transform=reference_dem.transform)
aligned_dem_data_deramp2 = deramp2.apply(dem_to_be_aligned.data, transform=dem_to_be_aligned.transform)

deramp3 = xdem.coreg.Deramp(degree=3)
deramp3.fit(reference_dem.data, dem_to_be_aligned.data, inlier_mask=inlier_mask, transform=reference_dem.transform)
aligned_dem_data_deramp3 = deramp3.apply(dem_to_be_aligned.data, transform=dem_to_be_aligned.transform)

icp = xdem.coreg.ICP()
icp.fit(reference_dem.data, dem_to_be_aligned.data, inlier_mask=inlier_mask, transform=reference_dem.transform)
aligned_dem_data_icp = icp.apply(dem_to_be_aligned.data, transform=dem_to_be_aligned.transform)

biascorr = xdem.coreg.BiasCorr()
biascorr.fit(reference_dem.data, dem_to_be_aligned.data, inlier_mask=inlier_mask, transform=reference_dem.transform)
aligned_dem_data_biascorr = biascorr.apply(dem_to_be_aligned.data, transform=dem_to_be_aligned.transform)

pipeline_1 = nuth_kaab + deramp
pipeline_1.fit(reference_dem.data, dem_to_be_aligned.data, inlier_mask=inlier_mask, transform=reference_dem.transform)
aligned_dem_data_pipeline_1 = pipeline_1.apply(dem_to_be_aligned.data, transform=dem_to_be_aligned.transform)

pipeline_2 = icp + nuth_kaab
pipeline_2.fit(reference_dem.data, dem_to_be_aligned.data, inlier_mask=inlier_mask, transform=reference_dem.transform)
aligned_dem_data_pipeline_2 = pipeline_2.apply(dem_to_be_aligned.data, transform=dem_to_be_aligned.transform)

pipeline_3 = biascorr + icp + nuth_kaab
pipeline_3.fit(reference_dem.data, dem_to_be_aligned.data, inlier_mask=inlier_mask, transform=reference_dem.transform)
aligned_dem_data_pipeline_3 = pipeline_3.apply(dem_to_be_aligned.data, transform=dem_to_be_aligned.transform)

pipeline_4 = biascorr + nuth_kaab
pipeline_4.fit(reference_dem.data, dem_to_be_aligned.data, inlier_mask=inlier_mask, transform=reference_dem.transform)
aligned_dem_data_pipeline_4 = pipeline_4.apply(dem_to_be_aligned.data, transform=dem_to_be_aligned.transform)

pipeline_5 = deramp + nuth_kaab
pipeline_5.fit(reference_dem.data, dem_to_be_aligned.data, inlier_mask=inlier_mask, transform=reference_dem.transform)
aligned_dem_data_pipeline_5 = pipeline_5.apply(dem_to_be_aligned.data, transform=dem_to_be_aligned.transform)

# DEM of differences pre-coregistration
ddem_before = reference_dem.data - dem_to_be_aligned.data

# DEM of differences post-coregistration
ddem_after_nk = reference_dem.data - aligned_dem_data_nk
ddem_after_deramp = reference_dem.data - aligned_dem_data_deramp
ddem_after_deramp2 = reference_dem.data - aligned_dem_data_deramp2
ddem_after_deramp3 = reference_dem.data - aligned_dem_data_deramp3
ddem_after_icp = reference_dem.data - aligned_dem_data_icp
ddem_after_biascorr = reference_dem.data - aligned_dem_data_biascorr
ddem_after_p1 = reference_dem.data - aligned_dem_data_pipeline_1
ddem_after_p2 = reference_dem.data - aligned_dem_data_pipeline_2
ddem_after_p3 = reference_dem.data - aligned_dem_data_pipeline_3
ddem_after_p4 = reference_dem.data - aligned_dem_data_pipeline_4
ddem_after_p5 = reference_dem.data - aligned_dem_data_pipeline_5

e1 = f"Error before: {xdem.spatialstats.nmad(ddem_before):.2f} m"
e2 = f"Error after Nuth-Kaab: {xdem.spatialstats.nmad(ddem_after_nk):.2f} m"
e3 = f"Error after Deramping (deg1): {xdem.spatialstats.nmad(ddem_after_deramp):.2f} m"
e4 = f"Error after Deramping (deg2): {xdem.spatialstats.nmad(ddem_after_deramp2):.2f} m"
e5 = f"Error after Deramping (deg3): {xdem.spatialstats.nmad(ddem_after_deramp3):.2f} m"
e6 = f"Error after ICP: {xdem.spatialstats.nmad(ddem_after_icp):.2f} m"
e7 = f"Error after Bias Correction: {xdem.spatialstats.nmad(ddem_after_biascorr):.2f} m"
e8 = f"Error after P1 - Nuth-Kaab+Deramp (deg1): {xdem.spatialstats.nmad(ddem_after_p1):.2f} m"
e9 = f"Error after P2 - ICP+Nuth-Kaab: {xdem.spatialstats.nmad(ddem_after_p2):.2f} m"
e10 = f"Error after P3 - Bias Correction+ICP+Nuth-Kaab: {xdem.spatialstats.nmad(ddem_after_p3):.2f} m"
e11 = f"Error after P4 - Bias Correction+Nuth-Kaab: {xdem.spatialstats.nmad(ddem_after_p4):.2f} m"
e12 = f"Error after P5 - Deramp (deg1)+Nuth-Kaab: {xdem.spatialstats.nmad(ddem_after_p5):.2f} m"

# Export
aligned_dem_nk = xdem.DEM.from_array(
    aligned_dem_data_nk,
    transform=dem_to_be_aligned.transform,
    crs=dem_to_be_aligned.crs,
    nodata=-9999
)
aligned_dem_deramp = xdem.DEM.from_array(
    aligned_dem_data_deramp,
    transform=dem_to_be_aligned.transform,
    crs=dem_to_be_aligned.crs,
    nodata=-9999
)
aligned_dem_deramp2 = xdem.DEM.from_array(
    aligned_dem_data_deramp2,
    transform=dem_to_be_aligned.transform,
    crs=dem_to_be_aligned.crs,
    nodata=-9999
)
aligned_dem_deramp3 = xdem.DEM.from_array(
    aligned_dem_data_deramp3,
    transform=dem_to_be_aligned.transform,
    crs=dem_to_be_aligned.crs,
    nodata=-9999
)
aligned_dem_icp = xdem.DEM.from_array(
    aligned_dem_data_icp,
    transform=dem_to_be_aligned.transform,
    crs=dem_to_be_aligned.crs,
    nodata=-9999
)
aligned_dem_biascorr = xdem.DEM.from_array(
    aligned_dem_data_biascorr,
    transform=dem_to_be_aligned.transform,
    crs=dem_to_be_aligned.crs,
    nodata=-9999
)
aligned_dem_p1 = xdem.DEM.from_array(
    aligned_dem_data_pipeline_1,
    transform=dem_to_be_aligned.transform,
    crs=dem_to_be_aligned.crs,
    nodata=-9999
)
aligned_dem_p2 = xdem.DEM.from_array(
    aligned_dem_data_pipeline_2,
    transform=dem_to_be_aligned.transform,
    crs=dem_to_be_aligned.crs,
    nodata=-9999
)
aligned_dem_p3 = xdem.DEM.from_array(
    aligned_dem_data_pipeline_3,
    transform=dem_to_be_aligned.transform,
    crs=dem_to_be_aligned.crs,
    nodata=-9999
)
aligned_dem_p4 = xdem.DEM.from_array(
    aligned_dem_data_pipeline_4,
    transform=dem_to_be_aligned.transform,
    crs=dem_to_be_aligned.crs,
    nodata=-9999
)
aligned_dem_p5 = xdem.DEM.from_array(
    aligned_dem_data_pipeline_5,
    transform=dem_to_be_aligned.transform,
    crs=dem_to_be_aligned.crs,
    nodata=-9999
)
aligned_dem_ref_name = dem_to_be_aligned.filename.split("/")[-1].split(".")[0]

# out_dir = "home/data/tests/test_pipes_alta/pre_event_201906/coreg"
# out_dir = "home/data/tests/test_pipes_grossarl/pre_event_201808/out_P4.data/coreg"
# out_dir = "home/data/tests/test_pipes_grossarl/pos_event_201907/out_P4.data/coreg"
# out_dir = "home/data/tests/test_pipes_grossarl/pos_event_202006_07_08/coreg"
out_dir = "home/data/tests/test_pipes_grossarl/errors"
# out_dir = "home/data/tests/test_pipes_grossarl/out_20170624_20170718/coreg"
# out_dir = "home/data/ref_dem/coreg/huettschlag_uav/"
# ref_dem_alias = 'ndh50cm'
ref_dem_alias = 'dgm1m'

# aligned_dem_nk.save(os.path.join(out_dir, aligned_dem_ref_name + '_' + ref_dem_alias + '_coreg_nk.tif'))
# aligned_dem_deramp.save(os.path.join(out_dir, aligned_dem_ref_name + '_' + ref_dem_alias + '_coreg_deramp.tif'))
# aligned_dem_deramp2.save(os.path.join(out_dir, aligned_dem_ref_name + '_' + ref_dem_alias + '_coreg_deramp2.tif'))
# aligned_dem_deramp3.save(os.path.join(out_dir, aligned_dem_ref_name + '_' + ref_dem_alias + '_coreg_deramp3.tif'))
# aligned_dem_icp.save(os.path.join(out_dir, aligned_dem_ref_name + '_' + ref_dem_alias + '_coreg_icp.tif'))
# aligned_dem_biascorr.save(os.path.join(out_dir, aligned_dem_ref_name + '_' + ref_dem_alias + '_coreg_biascorr.tif'))
# aligned_dem_p2.save(os.path.join(out_dir, aligned_dem_ref_name + '_' + ref_dem_alias + '_coreg_p2.tif'))
# aligned_dem_p3.save(os.path.join(out_dir, aligned_dem_ref_name + '_' + ref_dem_alias + '_coreg_p3.tif'))
# aligned_dem_p4.save(os.path.join(out_dir, aligned_dem_ref_name + '_' + ref_dem_alias + '_coreg_p4.tif'))
# aligned_dem_p1.save(os.path.join(out_dir, aligned_dem_ref_name + '_' + ref_dem_alias + '_coreg_p1.tif'))
# aligned_dem_p5.save(os.path.join(out_dir, aligned_dem_ref_name + '_' + ref_dem_alias + '_coreg_p5.tif'))

errors = [e1, e2, e3, e4, e5, e6, e7, e8, e9, e10, e11, e12]
with open(os.path.join(out_dir, 'readme.txt'), 'w') as f:
    f.writelines('\n'.join(errors))
