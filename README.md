# SliDEM
Development of the SliDEM Python package for the SliDEM project

---

**NOTE!** 

Even if we call it the SliDEM package, the structure of a package is not there yet. We are currently developing this repository actively and hope to have a working package soon. 

Currently, we present a series of executable scripts to run within a Docker container. You will see the instructions on how to set it up and start running the scripts below. 

The scripts still need some refinement before being fully ready to use. Cleaning of directories and naming is still needed so please check before running.

---
## Setup

To test scripts inside a docker container, follow these steps:

1. Clone this repository (download as zip and unzip OR even better use git)
2. Install Docker if you do not have it already
    - See instructions for [Windows here](https://docs.docker.com/desktop/windows/install/) and for [Linux here](https://docs.docker.com/engine/install/).

3. Create a container to work on
    - Go to you terminal, navigate to the folder where you unzipped this repo and type the command below.
    - You can mount a volume into the container.
    - I recommend having a `data` folder where all the data can be included and through the volume, it can also be accessed inside docker. 
    - What the command does:
      - `docker run` is the command to run an image through a container
      - `-it` calls an interactive process (like a shell)
      - `--entrypoint /bin/bash` will start your container in bash
      - `--name snap` gives a name to your image, so you can refer to it later
      - `-v PATH_TO_DIR/SliDEM-python:/home/` mounts a volume on your container. 
Replace `PATH_TO_DIR` with the path of the directory where you cloned SliDEM-python.
      - `loreabad6/slidem` is the Docker image available on DockerHub for this project

   ```
   docker run -it --entrypoint /bin/bash --name snap -v PATH_TO_DIR/SliDEM-python:/home/ loreabad6/slidem
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
   docker exec -it snap /bin/bash
   ```

5. Using `xdem`:
   - Given the different dependencies for this module, you should use the virtual environment created for it.

   ```commandline
   # to activate:
   conda activate xdem-dev
   
   # to deactivate:
   conda deactivate
   ```
   - Please test that the configuration when building the docker container 
was correct with (this might take several minutes):
   
   ```commandline
   cd xdem
   pytest -rA
   ```

6. Using `demcoreg`:
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
Depending on your selected time range, the data querying can take long since what it does is loop over every single image that
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

### 2. Download
Once you have run the query script, you will have a CSV file as an output. 
This file contains all the SAR image pairs that intersect your AOI and time frame and 
that correspond to the perpendicular and temporal thresholds set. 

We ask you now to go through the CSV file, and check which image pairs you would like to Download. 
For this you need to change the cell value of the image pair row under the column `Download` from `FALSE` to `TRUE`. 

Why is this a manual step? Because we want the analyst to check if the image pair is suitable or not for analysis. 
To help we added a link to the Sentinel Hub viewer for th closest Sentinel-2 image available for the dates of the image pair. 
Here you will be able to check if there was snow during your time period, if the cloud coverage was dense, if your area has
very dense vegetation that might result in errors, etc. 

**IMPORTANT!**
Since the download step will be done through the ASF server, we need credentials that allow you to obtain the data. 
The credentials should be saved in a file called `.env` on the directory mounted as a volume on the docker.
Username should be saved as `asf_login` and password as `asf_pwd`. See an example below:

```text
asf_login='USERNAME'
asf_pwd='PASSWORD'
```

Once the changes to the CSV files are saved and your `.env` file is ready, you can run the `1_download_s1.py` script as shown below.

```commandline
# Usage example
python3.6 home/scripts/1_download_s1.py --download_folder data/s1/ --query_result s1_scenes.csv
```
```commandline
# Get help
python3.6 home/scripts/1_download_s1.py -h
```

Downloading Sentinel-1 data always takes a while and requires a lot of disk space. 
Remember that the download occurs on your local disk, if you have mounted a volume as suggested. 
Be prepared and patient! :massage:

### 3. DEM generation
Now it is finally time to generate some DEMs. 
Taking the downloaded data and the query result form previous steps, we can now call the `2_dem_generation.py` module. 

The main arguments passed into this module are the path to the downloaded data, 
the CSV file which will be used to get the image pairs, a directory where the results are stored
and the AOI to subset the area and to automatically extract bursts and subswaths. 

Several other parameters can be passed to specific parts of the workflow. 
Check the help for their descriptions and default values.
```commandline
# Usage example
python3.6 home/scripts/2_dem_generation.py --download_dir data/s1/ --output_dir data/results/ --query_result s1_scenes.csv --pair_index 0 --aoi_path data/aoi/alta.geojson
```
```commandline
# Get help
python3.6 home/scripts/2_dem_generation.py -h
```

Depending on whether you have been using the container before, the processing might take more or less time.
The main reason is that reference DEM data is being downloaded for the data. 

**KNOWN ISSUES!**
- If your AOI is at the coast, the SNAPHU exporting might fail without a warning. 
This will of course result in faulty results. 
- If your AOI intersects multiple subswaths, then unfortunately your process will
exit with an error message. 

This list is not exhaustive and we try to document these problems in our issue tracker.

We are working to improve all these issues but 
for the moment please be aware and patient with us :pray: 

Feel free to open an issue if you find some new bug or have any request!