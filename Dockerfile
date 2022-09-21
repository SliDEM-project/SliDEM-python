# Get docker container from mundialis
# SNAP-8
# FROM mundialis/esa-snap:ubuntu
# SNAP-9
FROM loreabad6/esa-snap:ubuntu

# set locale
ENV LC_ALL=C

## Move local packages to tmp file
COPY setup/requirements.txt /tmp/base_requirements.txt

# Update snap-tools (skip for snap-9)
# If not running locally GitHub Actions will take care of compiling,
# only pulling the image from DockerHub is needed then
## This line results in an infinite loop, better use the .sh
# RUN /usr/local/snap/bin/snap --nosplash --nogui --modules --refresh --update-all

# When not running behind a firewall, uncomment the next two lines
# COPY setup/update-snap.sh /tmp/update-snap.sh
# RUN bash /tmp/update-snap.sh

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

# Install xdem
RUN git clone https://github.com/GlacioHack/xdem.git
WORKDIR ./xdem
RUN conda env create -f dev-environment.yml
SHELL ["conda", "run", "-n", "xdem-dev", "/bin/bash", "-c"]
RUN pip install -e .
RUN conda install -y -c conda-forge bmi-topography python-dotenv seaborn pysal
RUN pip install scicomap
RUN conda init bash

WORKDIR ..

## Move SliDEM scripts to /scripts
ADD scripts /scripts