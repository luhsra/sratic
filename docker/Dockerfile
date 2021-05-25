FROM python:3

RUN apt-get update && apt-get install -y git rsync

WORKDIR /usr/src/app

COPY requirements.txt /tmp
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

CMD /bin/bash
