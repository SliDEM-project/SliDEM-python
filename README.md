# SliDEM
Development of the SliDEM Python package for the SliDEM project

**NOTE!** The scripts still need some refinement before being fully ready to use. Cleaning of directories and naming is still needed so please check before running.

## Setup

To test scripts inside a docker container, follow these steps:

1. Clone this repository (download as zip and unzip OR even better use git)
2. Build the docker image with the Dockerfile
    - Be sure to have docker installed. See instructions for [Windows here](https://docs.docker.com/desktop/windows/install/) and for [Linux here](https://docs.docker.com/engine/install/).
    - Go to you terminal, navigate to the folder where you unzipped this repo and type the command below.
    - What it does:
      - `docker build` is the command to build an image
      - `-t snap-8` is assigning a tag to this image so you can refer to it later
      - `.` will look for the Dockerfile in the current directory
   ```
   docker build -t snap-8 .
   ```

3. Create a container to work on
    - You can mount a volume into the container.
    - I recommend having a `data` folder where all the data can be included and through the volume, it can also be accessed inside docker. 
    - What the command does:
      - `docker run` is the command to run an image through a container
      - `-it` calls an interactive process (like a shell)
      - `--entrypoint /bin/bash` will start your container in bash
      - `--name snap` gives a name to your image, so you can refer to it later
      - `-v PATH_TO_DIR/SliDEM-python:/home/` mounts a volume on your container. 
Replace `PATH_TO_DIR` with the path of the directory where you cloned SliDEM-python.
      - `snap-8` this is the name we gave to the image in the command above

   ```
   docker run -it --entrypoint /bin/bash --name snap -v PATH_TO_DIR/SliDEM-python:/home/ snap-8
   ```

4. You can remove the container once you are done. All results should be written to the mounted volume, but of course make sure that this is well set in the parameters when calling the scripts. 
   - You can exit your container by doing `CTRL+D`
   - you can delete the container with:
   ```
   docker stop snap
   docker rm snap
   ```
   - If you don't want to delete your container after use, then just **exit** it, **stop** it, and next time you want to use it run:
   ```
   docker start snap
   docker exec -it --entrypoint /bin/bash snap
   ```

5. Using `demcoreg`:
   - Given the different dependencies for this module, you should use the virtual environment created for it. 
   - Here are some commands useful to activate and deactivate the environment:

   ```
   # to activate:
   source activate demcoreg
   
   # to deactivate:
   conda deactivate
   ```

## Workflow

So far, steps are organized into 3 executable scripts:
1. Query S1 data
2. Download S1 data
3. Compute DEM from S1 data

To run the scripts for now you need to navigate to each folder with the scripts included. 
Assuming that you cloned this repo and started the Docker container from this directory,
you can just follow the examples below.

I recommend you mainly work on the `data` directory as download folder and a workplace to save your results. 
But of course this is up to you.

### 1. Query 
For this script, since we are using ASF to query images, no credentials are needed. 
Depending on your time range the data querying can take long since what it does is loop over every single image that
intersects your AOI and find matching scenes for the whole S1 lifetime 
(I know a bit useless but seems to be the only way now).

```commandline
# Usage example
python3.6 home/scripts/0_query_s1.py --download_folder data/s1/ --query_result s1_scenes.csv --date_start 2019/06/01 --date_end 2019/06/10 --aoi data/aoi/alta.geojson
```
```commandline
# Get help
python3.6 home/scripts/0_query_s1.py -h
```

```commandline
usage: 0_query_s1.py [-h] [--download_folder DOWNLOAD_FOLDER]
                     [--query_result QUERY_RESULT] [--date_start DATE_START]
                     [--date_end DATE_END] [--aoi AOI] [--btempth BTEMPTH]
                     [--bperpth BPERPTH]

Query Sentinel-1 scenes that fit into a geographical region and
within an specific time period.
Uses the ASF repository to query scenes by a wkt region and a specific temporal
range. The resulting scenes will go then into a loop to find matching scenes
using the baseline tool from ASF.

The output is a CSV file with the scenes matching the wkt and temporal arguments,
the matching IDs with a perpendicular and temporal baseline set by the user, and a
URL link to check for atmospheric conditions for the dates in the SentinelHub Explorer.

Not every matching scene is also overlapping the geographical and temporal settings,
hence a column `inAOInDates` is also included, where TRUE values indicate an overlap of
both scenes temporally and geographically.

The user is prompted now to check the file and update the `Download` column manually
according to the scenes that they deem useful.

optional arguments:
  -h, --help            show this help message and exit
  --download_folder DOWNLOAD_FOLDER
                        relative path (refers to mounted volume) to the folder
                             where the query_result CSV file should be written to.
  --query_result QUERY_RESULT
                        path to the CSV file with query results from 0_query_s1.py.
                             Should be located in the specified download folder.
  --date_start DATE_START
                        start date of S1 scene query
  --date_end DATE_END   start date of S1 scene query
  --aoi AOI             path to GeoJSON file (WGS84 - EPSG:4326) with the study area outline.
                            Any scenes intersecting this area will be included in the query result
  --btempth BTEMPTH     temporal baseline threshold to query matching scenes.
                            What is the maximum time that matching scenes should have between each other?
                            Defaults to 60 days.
                            This is checked forward and backwards.
  --bperpth BPERPTH     perpendicular baseline threshold to query matching scenes.
                            What is the minimum perpendicular baseline between matching scenes?
                            Defaults to 140 meters.
                            This is checked forward and backwards.

Versions:
  v0.1 - 06/2019 - Download from SentinelHub repository
  v0.2 - 11/2021 - Query from ASF repository
Authors:
  Lorena Abad - University of Salzburg - lorena.abad@plus.ac.at
  Benjamin Robson - University of Bergen
```
