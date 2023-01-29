#!/usr/bin/env bash

if [[ "$JELLYPY_DOCKER" == "True" ]]; then
    PUID=${PUID:-1000}
    PGID=${PGID:-1000}

    groupmod -o -g "$PGID" jellypy
    usermod -o -u "$PUID" jellypy

    find /config \! \( -uid $(id -u jellypy) -gid $(id -g jellypy) \) -print0 | xargs -0r chown jellypy:jellypy

    echo "Running JellyPy using user jellypy (uid=$(id -u jellypy)) and group jellypy (gid=$(id -g jellypy))"
    su-exec jellypy "$@"
else
    python_versions=("python3" "python3.8" "python3.7" "python3.6" "python" "python2" "python2.7")
    for cmd in "${python_versions[@]}"; do
        if command -v "$cmd" >/dev/null; then
            echo "Starting JellyPy with $cmd."
            if [[ "$(uname -s)" == "Darwin" ]]; then
                $cmd JellyPy.py &> /dev/null &
            else
                $cmd JellyPy.py --quiet --daemon
            fi
            exit
        fi
    done
    echo "Unable to start JellyPy. No Python interpreter was found in the following options:" "${python_versions[@]}"
fi
