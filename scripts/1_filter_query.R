library(sf)
library(here)
library(tidyverse)
aoi = "data/aoi/Alta.geojson"
aoisf = read_sf(aoi) %>% 
  st_transform(4326) 

scenes_sh = read_csv("data/s1/sentinelhub_images.csv") %>%
  st_as_sf(wkt = 'footprint')
scenes_asf = read_csv("data/s1/asf_images.csv") 

sel = scenes_sh %>% 
  mutate(id = row_number()) %>% 
  select(
    id, uuid, sceneid = title, date = beginposition,
    relativeorbitnumber, orbitdirection,
    polarisationmode, size, footprint) %>% 
  separate(
    polarisationmode,
    sep = " ",
    into = c("polar_a", "polar_b")
  ) %>% 
  group_by(relativeorbitnumber, orbitdirection) %>% 
  mutate(groupid = row_number())
sel = scenes_asf %>% 
  mutate(id = row_number()) %>% 
  select(
    id, sceneid = fileID, date = processingDate,
    pathNumber, flightDirection,
    polarization, bytes) %>% 
  separate(
    polarization,
    sep = "\\+",
    into = c("polar_a", "polar_b")
  ) %>% 
  group_by(pathNumber, flightDirection) %>% 
  mutate(groupid = row_number())

distmat = lapply(
  group_split(sel),
  function(x) {
    mat = as.matrix(dist(x$date)) / (3600*24)
    rownames(mat) = x$id
    colnames(mat) = x$id
    mat
  }
)

tbaseline_pairs = lapply(
  distmat,
  function(x) {
    idx = as.data.frame(
      which(
        x < 7 & x > 1,
        arr.ind = TRUE, useNames = TRUE
      )
    )
    group_by(idx, row) %>%
      summarise(match = paste(col, collapse = ","))
  }
)

matched = group_split(sel) %>% 
  map2(tbaseline_pairs, ~ left_join(.x, .y, by = c('groupid'='row'))) %>% 
  bind_rows() %>% 
  filter(!is.na(match))

write_csv(matched, "data/sentinelhub_images_filtered.csv") 
