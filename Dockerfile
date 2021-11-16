# Get docker container from mundialis
FROM mundialis/esa-snap:ubuntu

## Move local packages to tmp file
COPY setup/requirements.txt /tmp/base_requirements.txt
COPY setup/stsa/requirements.txt /tmp/stsa_requirements.txt

## Install requirements for python
RUN python3.6 -m pip install --upgrade pip
RUN python3.6 -m pip install --no-cache-dir --upgrade -r /tmp/stsa_requirements.txt
RUN python3.6 -m pip install --no-cache-dir --upgrade -r /tmp/base_requirements.txt

## include local package in python folder
COPY setup/stsa/stsa/ /usr/lib/python3.6/stsa/

# Install snaphu
RUN apt update
RUN apt install snaphu

# Install GDAL
RUN apt-get update &&\
    apt-get install -y binutils libproj-dev gdal-bin

# Update C env vars so compiler can find gdal
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Install miniconda
ENV PATH="/root/miniconda3/bin:${PATH}"
ARG PATH="/root/miniconda3/bin:${PATH}"
RUN apt-get update

RUN apt-get install -y wget && rm -rf /var/lib/apt/lists/*

RUN wget \
    https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
    && mkdir /root/.conda \
    && bash Miniconda3-latest-Linux-x86_64.sh -b \
    && rm -f Miniconda3-latest-Linux-x86_64.sh

RUN conda create --yes -c conda-forge -n demcoreg python=3.6 gdal=2.4 rasterio \
    requests geopandas
SHELL ["conda", "run", "-n", "demcoreg", "/bin/bash", "-c"]

RUN mkdir src
WORKDIR src

# Install pygeotools & demcoreg
RUN git clone https://github.com/dshean/pygeotools.git
RUN python3.6 -m pip install -e pygeotools
RUN git clone https://github.com/dshean/demcoreg.git
RUN python3.6 -m pip install -e demcoreg

ENV PATH="src/pygeotools/pygeotools:src/demcoreg/demcoreg:$PATH"

WORKDIR ..
