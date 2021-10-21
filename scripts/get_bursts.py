# Create object
import stsa
import os

data = "home/data/"
img1 = "S1A_IW_SLC__1SDV_20190825T045538_20190825T045605_028721_03406F_847F"
img2 = "S1B_IW_SLC__1SDV_20190831T045510_20190831T045537_017825_0218B6_491E"

s1_img1 = stsa.TopsSplitAnalyzer(target_subswaths=['iw1', 'iw2', 'iw3'], polarization='vv')
s1_img1.load_data(zip_path=os.path.join(data, img1 + '.zip'))
s1_img1.to_json(os.path.join(data, img1 + '.json'))

s1_img2 = stsa.TopsSplitAnalyzer(target_subswaths=['iw1', 'iw2', 'iw3'], polarization='vv')
s1_img2.load_data(zip_path=os.path.join(data, img2 + '.zip'))
s1_img2.to_json(os.path.join(data, img2 + '.json'))

