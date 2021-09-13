library(sf)
library(here)
library(tidyverse)
aoi = "../../01_data/01_no/aoi/01_Alta.json"
aoisf = read_sf(aoi) %>% 
  st_transform(4326) 

scenes = read_csv("data/Sentinel_images.csv") %>% 
  st_as_sf(wkt = 'footprint')

sel = scenes %>% 
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

write_csv(matched, "data/Sentinel_images_filtered.csv") 
