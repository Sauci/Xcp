FROM alpine:3.10

LABEL maintainer="Guillaume Sottas"

# setup environment variables.
ENV PROJECT_DIR=/usr/project

# install required binaries.
# cmake is not among these: alpine 3.10's apk pins it at 3.14.5, and string(JSON) in
# CMakeLists.txt needs 3.19. requirements.txt below pulls it from PyPI instead.
RUN apk update && apk add \
    bash \
    build-base \
    curl \
    doxygen \
    findutils \
    gdb \
    git \
    graphviz \
    libffi-dev \
    python3-dev

# install python requirements.
COPY ./requirements.txt requirements.txt
RUN pip3 install --upgrade pip && pip3 install -r requirements.txt

# setup a shared volume.
WORKDIR $PROJECT_DIR
VOLUME ["$PROJECT_DIR"]
RUN cd $PROJECT_DIR
