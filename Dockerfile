# Get docker container from mundialis
FROM mundialis/esa-snap:ubuntu

## Move local packages to tmp file
COPY setup/requirements.txt /tmp/base_requirements.txt
# COPY setup/stsa/requirements.txt /tmp/stsa_requirements.txt

# Update snap-tools
# If not running locally GitHub Actions will take care of compiling,
# only pulling the image from DockerHub is needed then
## This line results in an infinite loop, better use the .sh
# RUN /usr/local/snap/bin/snap --nosplash --nogui --modules --refresh --update-all
## When not running behind a firewall, uncomment the next two lines
COPY setup/update-snap.sh /tmp/update-snap.sh
RUN bash /tmp/update-snap.sh

## Install requirements for python
RUN python3.6 -m pip install --upgrade pip
RUN python3.6 -m pip install --no-cache-dir --upgrade -r /tmp/base_requirements.txt

# Install stsa
RUN git clone https://github.com/pbrotoisworo/s1-tops-split-analyzer.git
## After certain updates, support for python 3.6 was taken away, but I still need it!
## So I go back to a previous version (December 2021)
WORKDIR ./s1-tops-split-analyzer
RUN git reset --hard 12ea576989cce7cbff5569ece6d17df52a17b0a9
RUN python3.6 -m pip install -e .
WORKDIR ..

# Install snaphu
RUN wget --no-check-certificate  \
    https://web.stanford.edu/group/radar/softwareandlinks/sw/snaphu/snaphu-v2.0.5.tar.gz \
    && tar -xvf snaphu-v2.0.5.tar.gz \
    && rm snaphu-v2.0.5.tar.gz \
    && mkdir -p /usr/local/man/man1/ \
    && cd ./snaphu-v2.0.5/src \
    && make install \
    && make Clean

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
