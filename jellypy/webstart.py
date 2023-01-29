# -*- coding: utf-8 -*-

#  This file is part of JellyPy.
#
#  JellyPy is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  JellyPy is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with JellyPy.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys

import cherrypy

import jellypy
from jellypy import logger
from jellypy import webauth
from jellypy.helpers import create_https_certificates
from jellypy.webserve import WebInterface, BaseRedirect


def start():
    logger.info("JellyPy WebStart :: Initializing JellyPy web server...")
    web_config = {
        'http_port': jellypy.HTTP_PORT,
        'http_host': jellypy.CONFIG.HTTP_HOST,
        'http_root': jellypy.CONFIG.HTTP_ROOT,
        'http_environment': jellypy.CONFIG.HTTP_ENVIRONMENT,
        'http_proxy': jellypy.CONFIG.HTTP_PROXY,
        'enable_https': jellypy.CONFIG.ENABLE_HTTPS,
        'https_cert': jellypy.CONFIG.HTTPS_CERT,
        'https_cert_chain': jellypy.CONFIG.HTTPS_CERT_CHAIN,
        'https_key': jellypy.CONFIG.HTTPS_KEY,
        'http_username': jellypy.CONFIG.HTTP_USERNAME,
        'http_password': jellypy.CONFIG.HTTP_PASSWORD,
        'http_basic_auth': jellypy.CONFIG.HTTP_BASIC_AUTH
    }
    initialize(web_config)


def stop():
    logger.info("JellyPy WebStart :: Stopping JellyPy web server...")
    cherrypy.engine.exit()


def restart():
    logger.info("JellyPy WebStart :: Restarting JellyPy web server...")
    stop()
    start()


def initialize(options):

    # HTTPS stuff stolen from sickbeard
    enable_https = options['enable_https']
    https_cert = options['https_cert']
    https_cert_chain = options['https_cert_chain']
    https_key = options['https_key']

    if enable_https:
        # If either the HTTPS certificate or key do not exist, try to make self-signed ones.
        if jellypy.CONFIG.HTTPS_CREATE_CERT and \
                (not (https_cert and os.path.exists(https_cert)) or
                 not (https_key and os.path.exists(https_key))):
            if not create_https_certificates(https_cert, https_key):
                logger.warn("JellyPy WebStart :: Unable to create certificate and key. Disabling HTTPS")
                enable_https = False

        if not (os.path.exists(https_cert) and os.path.exists(https_key)):
            logger.warn("JellyPy WebStart :: Disabled HTTPS because of missing certificate and key.")
            enable_https = False

    options_dict = {
        'server.socket_port': options['http_port'],
        'server.socket_host': options['http_host'],
        'environment': options['http_environment'],
        'server.thread_pool': jellypy.CONFIG.HTTP_THREAD_POOL,
        'server.max_request_body_size': 1073741824,
        'server.socket_timeout': 60,
        'tools.encode.on': True,
        'tools.encode.encoding': 'utf-8',
        'tools.decode.on': True
    }

    if jellypy.DEV:
        options_dict['environment'] = "test_suite"
        options_dict['engine.autoreload.on'] = True

    if enable_https:
        options_dict['server.ssl_certificate'] = https_cert
        options_dict['server.ssl_certificate_chain'] = https_cert_chain
        options_dict['server.ssl_private_key'] = https_key
        protocol = "https"
    else:
        protocol = "http"

    if options['http_proxy']:
        # Overwrite cherrypy.tools.proxy with our own proxy handler
        cherrypy.tools.proxy = cherrypy.Tool('before_handler', proxy, priority=1)

    if options['http_password']:
        login_allowed = ["JellyPy admin (username is '%s')" % options['http_username']]
        if jellypy.CONFIG.HTTP_JELLYFIN_ADMIN:
            login_allowed.append("Jellyfin admin")

        logger.info("JellyPy WebStart :: Web server authentication is enabled: %s.", ' and '.join(login_allowed))

        if options['http_basic_auth']:
            jellypy.AUTH_ENABLED = False
            basic_auth_enabled = True
        else:
            jellypy.AUTH_ENABLED = True
            basic_auth_enabled = False
            cherrypy.tools.auth = cherrypy.Tool('before_handler', webauth.check_auth, priority=2)
    else:
        logger.warn("JellyPy WebStart :: Web server authentication is disabled!")

        jellypy.AUTH_ENABLED = False
        basic_auth_enabled = False

    if options['http_root'].strip('/'):
        jellypy.HTTP_ROOT = options['http_root'] = '/' + str(options['http_root'].strip('/')) + '/'
    else:
        jellypy.HTTP_ROOT = options['http_root'] = '/'

    logger.info("JellyPy WebStart :: Thread Pool Size: %d.", jellypy.CONFIG.HTTP_THREAD_POOL)
    cherrypy.config.update(options_dict)

    conf = {
        '/': {
            'engine.timeout_monitor.on': False,
            'tools.staticdir.root': os.path.join(jellypy.PROG_DIR, 'data'),
            'tools.proxy.on': bool(options['http_proxy']),
            'tools.gzip.on': True,
            'tools.gzip.mime_types': ['text/html', 'text/plain', 'text/css',
                                      'text/javascript', 'application/json',
                                      'application/javascript'],
            'tools.auth.on': jellypy.AUTH_ENABLED,
            'tools.auth_basic.on': basic_auth_enabled,
            'tools.auth_basic.realm': 'JellyPy web server',
            'tools.auth_basic.checkpassword': cherrypy.lib.auth_basic.checkpassword_dict({
                options['http_username']: options['http_password']})
        },
        '/api': {
            'tools.auth_basic.on': False
        },
        '/status': {
            'tools.auth_basic.on': False
        },
        '/interfaces': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "interfaces",
            'tools.caching.on': True,
            'tools.caching.force': True,
            'tools.caching.delay': 0,
            'tools.expires.on': True,
            'tools.expires.secs': 60 * 60 * 24 * 30,  # 30 days
            'tools.sessions.on': False,
            'tools.auth.on': False
        },
        '/images': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "interfaces/default/images",
            'tools.staticdir.content_types': {'svg': 'image/svg+xml'},
            'tools.caching.on': True,
            'tools.caching.force': True,
            'tools.caching.delay': 0,
            'tools.expires.on': True,
            'tools.expires.secs': 60 * 60 * 24 * 30,  # 30 days
            'tools.sessions.on': False,
            'tools.auth.on': False
        },
        '/css': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "interfaces/default/css",
            'tools.caching.on': True,
            'tools.caching.force': True,
            'tools.caching.delay': 0,
            'tools.expires.on': True,
            'tools.expires.secs': 60 * 60 * 24 * 30,  # 30 days
            'tools.sessions.on': False,
            'tools.auth.on': False
        },
        '/fonts': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "interfaces/default/fonts",
            'tools.caching.on': True,
            'tools.caching.force': True,
            'tools.caching.delay': 0,
            'tools.expires.on': True,
            'tools.expires.secs': 60 * 60 * 24 * 30,  # 30 days
            'tools.sessions.on': False,
            'tools.auth.on': False
        },
        '/js': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': "interfaces/default/js",
            'tools.caching.on': True,
            'tools.caching.force': True,
            'tools.caching.delay': 0,
            'tools.expires.on': True,
            'tools.expires.secs': 60 * 60 * 24 * 30,  # 30 days
            'tools.sessions.on': False,
            'tools.auth.on': False
        },
        '/cache': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': jellypy.CONFIG.CACHE_DIR,
            'tools.caching.on': True,
            'tools.caching.force': True,
            'tools.caching.delay': 0,
            'tools.expires.on': True,
            'tools.expires.secs': 60 * 60 * 24 * 30,  # 30 days
            'tools.sessions.on': False,
            'tools.auth.on': False
        },
        '/pms_image_proxy': {
           'tools.caching.on': True,
           'tools.caching.force': True,
           'tools.caching.delay': 0,
           'tools.expires.on': True,
           'tools.expires.secs': 60 * 60 * 24 * 30,  # 30 days
           'tools.auth.on': False,
           'tools.sessions.on': False
        },
        '/favicon.ico': {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': os.path.abspath(os.path.join(
                jellypy.PROG_DIR, 'data/interfaces/default/images/favicon/favicon.ico')),
            'tools.caching.on': True,
            'tools.caching.force': True,
            'tools.caching.delay': 0,
            'tools.expires.on': True,
            'tools.expires.secs': 60 * 60 * 24 * 30,  # 30 days
            'tools.sessions.on': False,
            'tools.auth.on': False
        }
    }

    cherrypy.tree.mount(WebInterface(), options['http_root'], config=conf)
    if jellypy.HTTP_ROOT != '/':
        cherrypy.tree.mount(BaseRedirect(), '/')

    try:
        logger.info("JellyPy WebStart :: Starting JellyPy web server on %s://%s:%d%s", protocol,
                    options['http_host'], options['http_port'], options['http_root'])
        #cherrypy.process.servers.check_port(str(options['http_host']), options['http_port'])
        if not jellypy.DEV:
            cherrypy.server.start()
        else:
            cherrypy.engine.signals.subscribe()
            cherrypy.engine.start()
            cherrypy.engine.block()
    except IOError as e:
        logger.error("JellyPy WebStart :: Failed to start JellyPy: %s", e)
        jellypy.alert_message('Failed to start JellyPy: %s' % e)
        sys.exit(1)

    cherrypy.server.wait()


def proxy():
    # logger.debug("REQUEST URI: %s, HEADER [X-Forwarded-Host]: %s, [X-Host]: %s, [Origin]: %s, [Host]: %s",
    #              cherrypy.request.wsgi_environ['REQUEST_URI'],
    #              cherrypy.request.headers.get('X-Forwarded-Host'),
    #              cherrypy.request.headers.get('X-Host'),
    #              cherrypy.request.headers.get('Origin'),
    #              cherrypy.request.headers.get('Host'))

    # Change cherrpy.tools.proxy.local header if X-Forwarded-Host header is not present
    local = 'X-Forwarded-Host'
    if not cherrypy.request.headers.get('X-Forwarded-Host'):
        if cherrypy.request.headers.get('X-Host'):  # lighttpd
            local = 'X-Host'
        elif cherrypy.request.headers.get('Origin'):  # Squid
            local = 'Origin'
        elif cherrypy.request.headers.get('Host'):  # nginx
            local = 'Host'
        # logger.debug("cherrypy.tools.proxy.local set to [%s]", local)

    # Call original cherrypy proxy tool with the new local
    cherrypy.lib.cptools.proxy(local=local)
