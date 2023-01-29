# -*- coding: utf-8 -*-

# This file is part of JellyPy.
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
import uuid

import jellypy
from jellyfin_apiclient_python import JellyfinClient
from jellypy import helpers
from jellypy import http_handler
from jellypy.common import PRODUCT, RELEASE


class Jellyfin(object):
    def __init__(self, token=None, ssl=0, hostname=None, port=None, api_key=None):
        if not jellypy.CONFIG.JELLYFIN_UUID:
            jellypy.CONFIG.JELLYFIN_UUID = uuid.uuid4()
            jellypy.CONFIG.write()

        self.jf = JellyfinClient()
        self.jf.config.data["app.default"] = True
        self.jf.config.app(PRODUCT, RELEASE, PRODUCT, jellypy.CONFIG.JELLYFIN_UUID)

        self.jf.config.data["http.user_agent"] = PRODUCT
        self.jf.config.data["auth.ssl"] = jellypy.CONFIG.JELLYFIN_SSL
        self.id = None
        self.token = token if token else jellypy.CONFIG.JELLYFIN_ACCESS_TOKEN
        self.api_key = api_key if api_key else jellypy.CONFIG.JELLYFIN_API_KEY
        self.ssl = ssl if ssl else jellypy.CONFIG.JELLYFIN_SSL
        self.hostname = hostname if hostname else jellypy.CONFIG.JELLYFIN_IP
        self.port = port if port else jellypy.CONFIG.JELLYFIN_PORT

        """if self.token:
            self.login()"""

    def get_library(self, section_id):
        return self.jf.library.sectionByID(str(section_id))

    def get_library_items(self, section_id):
        return self.get_library(str(section_id)).all()

    def get_item(self, rating_key):
        return self.jf.fetchItem(rating_key)

    """def login(self, user=None, password=None) -> bool:
        if user and password and self.url:
            self.jf.auth.connect_to_address(self.url)
            result = self.jf.auth.login(self.url, user, password)

            if "AccessToken" in result:
                credentials = self.jf.auth.credentials.get_credentials()
                self.id = credentials["Servers"][0]["Id"]
                # jellypy.CONFIG.JELLYFIN_TOKEN =
                #
                # self._connect_client(server)
                # self.credentials.append(server)
                # self.save_credentials()
                return True
        if self.token and self.url:
            # TODO: Add token auth
            pass

        return False"""

    def get_full_users_list(self):
        users_list = []

        ssl = helpers.bool_true(self.ssl)
        scheme = 'https' if ssl else 'http'
        url = '{scheme}://{hostname}:{port}'.format(scheme=scheme, hostname=self.hostname, port=self.port)
        uri = '/Users'

        request_handler = http_handler.HTTPHandler(urls=url, ssl_verify=False, api_key=self.api_key)
        request = request_handler.make_request(uri=uri, request_type='GET', output_format='json')

        if request:
            for a in request:
                if a["Policy"]["IsAdministrator"]:
                    own_details = {
                        "user_id": helpers.get_json_attr(a, 'Id'),
                        "username": helpers.get_json_attr(a, 'Name'),
                        "title": helpers.get_json_attr(a, 'Name'),
                        "email": helpers.get_json_attr(a, 'Email'),
                        "is_home_user": helpers.get_json_attr(a, 'home'),
                        "is_restricted": helpers.get_json_attr(a, 'restricted'),
                        "filter_all": helpers.get_json_attr(a, 'filterAll'),
                        "filter_movies": helpers.get_json_attr(a, 'filterMovies'),
                        "filter_tv": helpers.get_json_attr(a, 'filterTelevision'),
                        "filter_music": helpers.get_json_attr(a, 'filterMusic'),
                        "filter_photos": helpers.get_json_attr(a, 'filterPhotos'),
                        "user_token": helpers.get_json_attr(a, 'authToken'),
                        "server_token": helpers.get_json_attr(a, 'authToken'),
                        "shared_libraries": None,
                        "is_allow_sync": 1,
                        "is_active": 1,
                        "is_admin": 1
                    }

                    try:
                        if a["PrimaryImageTag"]:
                            own_details["thumb"] = f"/Users/{helpers.get_json_attr(a, 'Id')}/Images/Primary"
                    except KeyError:
                        own_details["thumb"] = None
                        pass

                    users_list.append(own_details)

            for a in request:
                friend = {
                    "user_id": helpers.get_json_attr(a, 'Id'),
                    "username": helpers.get_json_attr(a, 'Name'),
                    "title": helpers.get_json_attr(a, 'Name'),
                    "email": helpers.get_json_attr(a, 'Email'),
                    "is_home_user": helpers.get_json_attr(a, 'home'),
                    "is_allow_sync": 1,
                    "is_restricted": helpers.get_json_attr(a, 'restricted'),
                    "filter_all": helpers.get_json_attr(a, 'filterAll'),
                    "filter_movies": helpers.get_json_attr(a, 'filterMovies'),
                    "filter_tv": helpers.get_json_attr(a, 'filterTelevision'),
                    "filter_music": helpers.get_json_attr(a, 'filterMusic'),
                    "filter_photos": helpers.get_json_attr(a, 'filterPhotos'),
                    "user_token": helpers.get_json_attr(a, 'authToken'),
                    "server_token": helpers.get_json_attr(a, 'authToken'),
                    "shared_libraries": None,
                    "is_active": 1,
                    "is_admin": 0
                }

                try:
                    if a["PrimaryImageTag"]:
                        friend["thumb"] = f"/Users/{helpers.get_json_attr(a, 'Id')}/Images/Primary"
                except KeyError:
                    friend["thumb"] = None
                    pass

                users_list.append(friend)

        return users_list
