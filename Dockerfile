# Get docker container from mundialis
FROM mundialis/esa-snap:ubuntu

## Move local packages to tmp file
COPY stsa/requirements.txt /tmp/base_requirements.txt

## https://github.com/UKHO/dockerimages/blob/main/linux/esa-snap7-snappy/Dockerfile
RUN python3.6 -m pip install --no-cache-dir --upgrade -r /tmp/base_requirements.txt

## include local package in python folder
COPY stsa/stsa/ /usr/lib/python3.6/stsa/

# Install snaphu
RUN apt update
RUN apt install snaphu
