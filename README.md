# JellyPy

This project is a fork of [Tautulli](https://github.com/Tautulli/Tautulli).

**I don't have time to keep working on this. I need some help from the great people of Jellyfin community.**

A python based web application for monitoring, analytics and notifications for [Jellyfin](https://jellyfin.org/).

## What it can do:

- Login to Jellyfin
- Displays
    - Libraries/Media
    - Activity
    - Users
    - Recently added
- Terminates active streams.
- Reads Jellyfin log file.
- Image caching.

## TODO

- See [TODO.md](TODO.md)

## Removed

- Plex support (not completely, there are some left).
- Analytics.
- Python2 support.

## Install

Before you install, please read this:

- Docker image is not available at the moment.
- I have only tested this on Windows 10.
- I don't have an extensive knowledge in Python.
- I don't remember exactly when I forked this.I am truly sorry for this.

### Steps

- Clone the repository.
- Install requirements. `pip install -r requirements.txt`
- Run `JellyPy.py`. `python JellyPy.py`
- Visit `http://localhost:8181`.
