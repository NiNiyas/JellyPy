FROM ghcr.io/linuxserver/baseimage-alpine:arm64v8-3.16

LABEL maintainer="NiNiyas"

ARG BRANCH
ARG COMMIT

ENV JELLYPY_DOCKER=True
ENV TZ=UTC

RUN \
  echo "**** install build packages ****" && \
  apk add --no-cache --virtual=build-dependencies \
    g++ \
    gcc \
    make \
    libffi-dev \
    python3-dev && \
  echo "**** install packages ****" && \
  apk add --no-cache \
    curl \
    jq \
    py3-openssl \
    py3-pip \
    py3-setuptools \
    python3 \
    su-exec && \
 echo "**** install pip packages ****" && \
  python3 -m pip install --upgrade pip wheel

WORKDIR /app
COPY . /app

RUN pip3 install --no-cache -U pip && \
    pip3 install --upgrade --no-cache -r requirements.txt && \
    apk del --purge build-dependencies

RUN \
  mkdir /config && \
  touch /config/DOCKER
VOLUME /config

CMD [ "python", "JellyPy.py", "--datadir", "/config" ]
ENTRYPOINT [ "./start.sh" ]

EXPOSE 8181
HEALTHCHECK --start-period=90s CMD curl -ILfSs http://localhost:8181/status > /dev/null || curl -ILfkSs https://localhost:8181/status > /dev/null || exit 1
