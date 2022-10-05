# v0.1.0 (develop)
## 05.10.2022
### Added
- Volume calculation script parametrized
### Changes
- 3_assess_accuracy.py has slightly changed input parameters.
- `set_ndv` was replaced by `set_nodata`

## 21.09.2022
### Added
- Upgrade to SNAP-9
- Scripts included into Docker image
  - **Important!** call scripts as `scripts/___.py` instead of `home/scripts/___.py`
### Changed
- `demcoreg` is no longer supported

## 10.08.2022
### Added
- Accuracy assessment module
- DEM co-registration within accuracy assessment module
- Land-use/land-cover statistics for accuracy assessment
- Download script for external DEM and land-use/land-cover data
- Citation file
### Changed
- Pipelines renamed
### Fixed
- `argparser` boolean type [#37](https://github.com/SliDEM-project/SliDEM-python/issues/37)
# v0.0.1
## 01.08.2022
- First implementation 