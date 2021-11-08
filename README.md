# SliDEM-python
Development of the SliDEM Python package for the SliDEM project

**NOTE!** The scripts still need some refinement before being fully ready to use. Cleaning of directories and naming is still needed so please check before running.

To test scripts inside s docker container, follow these steps:

1. Clone this repository (download as zip and unzip OR even better use git)
2. Build the docker image with the Dockerfile
    - Be sure to have docker installed.
    - Go to you terminal, navigate to the folder where you unzip this repo and type:
```
docker build -t snap-8 .
```

3. Create a container to work on
    - You can mount a volume into the container.
    - I recommend having a data folder where all the data can be included and through the volume, it can also be accessed inside docker. 
    
```
docker run -it --entrypoint /bin/bash --name snap --memory="8g" -v D:/SliDEM/SliDEM-python:/home/ snap-8
```

4. You can remove the container once you are done. All results should be written to the mounted volume, but of course make sure that this is well set in the scripts. 
