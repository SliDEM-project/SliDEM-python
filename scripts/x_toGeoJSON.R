library(sf)
library(stringr)
list = list.files("data/aoi", ".json", full.names = TRUE)
names = str_remove(
  list.files("data/aoi", ".json", full.names = FALSE),
  ".json"
)
read = lapply(list, read_sf)
proj = lapply(read, st_transform, 4326)
purrr::map2(proj, names, ~st_write(.x, glue::glue("data/aoi/", .y, ".geojson")))
