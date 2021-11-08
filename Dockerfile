# Get docker container from mundialis
FROM mundialis/esa-snap:ubuntu

## Move local packages to tmp file
COPY setup/requirements.txt /tmp/base_requirements.txt
COPY setup/stsa/requirements.txt /tmp/stsa_requirements.txt

## Install requirements for python
RUN python3.6 -m pip install --upgrade pip
RUN python3.6 -m pip install --no-cache-dir --upgrade -r /tmp/base_requirements.txt
RUN python3.6 -m pip install --no-cache-dir --upgrade -r /tmp/stsa_requirements.txt

## include local package in python folder
COPY setup/stsa/stsa/ /usr/lib/python3.6/stsa/

# Install snaphu
RUN apt update
RUN apt install snaphu
