# Get docker container from mundialis
FROM mundialis/esa-snap:ubuntu

## Move local packages to tmp file
COPY setup/requirements.txt /tmp/base_requirements.txt
COPY setup/stsa/requirements.txt /tmp/stsa_requirements.txt

# Update snap-tools
# ENV HOME /root
# WORKDIR /usr/local/snap/snap/modules/
# RUN jar -xvf org-esa-snap-snap-rcp.jar
# WORKDIR $HOME
# COPY setup/layer.xml /tmp/layer.xml
# RUN cp /tmp/layer.xml /usr/local/snap/snap/modules/org/esa/snap/rcp/layer.xml
# WORKDIR /usr/local/snap/snap/modules/
# RUN jar -cvf org-esa-snap-snap-rcp.jar org
# WORKDIR $HOME
# RUN /usr/local/snap/bin/snap --nosplash --nogui --modules --refresh --update-all
# # COPY setup/update-snap.sh /tmp/update-snap.sh
# # RUN bash /tmp/update-snap.sh

## Install requirements for python
RUN python3.6 -m pip install --upgrade pip
RUN python3.6 -m pip install --no-cache-dir --upgrade -r /tmp/stsa_requirements.txt
RUN python3.6 -m pip install --no-cache-dir --upgrade -r /tmp/base_requirements.txt

## include local package in python folder
COPY setup/stsa/stsa/ /usr/lib/python3.6/stsa/

# Install snaphu
# Installs outdated version:
RUN apt update && \
    apt install snaphu

# Install GDAL
RUN apt-get update &&\
    apt-get install -y binutils libproj-dev gdal-bin unzip

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

# Install pygeotools, imview & demcoreg
RUN git clone https://github.com/dshean/pygeotools.git
RUN python3.6 -m pip install -e pygeotools
RUN git clone https://github.com/dshean/demcoreg.git
RUN python3.6 -m pip install -e demcoreg
RUN git clone https://github.com/dshean/imview.git
RUN python3.6 -m pip install -e imview

ENV PATH="src/pygeotools/pygeotools:src/demcoreg/demcoreg:src/imview/imview:$PATH"

WORKDIR ..

# Install xdem
RUN git clone https://github.com/GlacioHack/xdem.git
WORKDIR ./xdem
RUN conda env create -f dev-environment.yml
SHELL ["conda", "run", "-n", "xdem-dev", "/bin/bash", "-c"]
RUN pip install -e .
RUN conda init bash

WORKDIR ..
