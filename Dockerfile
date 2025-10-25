#!/bin/bash
# Build for AMD64
# Builder
FROM  --platform=linux/amd64 ubuntu:22.04
RUN apt-get update
RUN apt-get install -y python3.10
RUN apt-get install -y python3-pip
ADD requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
ADD event_detection_model.pth event_detection_model.pth
ADD utils.py utils.py
ADD data data
ADD src/ src/
ADD 3._elabora_entity_linking.py main.py

RUN mkdir output
RUN mkdir output_data


CMD ["python3.10", "main.py"]
