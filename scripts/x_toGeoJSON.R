library(sf)
library(stringr)
library(here)
dir = "path_to_dir"
list = list.files(here(dir,"data/aoi"), ".json", full.names = TRUE)
names = str_remove(
  list.files(here(dir,"data/aoi"), ".json", full.names = FALSE),
  ".json"
)
read = lapply(list, read_sf)
proj = lapply(read, st_transform, 4326)
purrr::map2(
  proj,
  names,
  ~st_write(.x, here(dir, "data/aoi", glue::glue("{.y}.geojson")))
)