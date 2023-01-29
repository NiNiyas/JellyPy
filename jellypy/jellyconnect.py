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

from __future__ import unicode_literals

import json
import os
import re

import jellypy
from future.builtins import object
from future.builtins import str
from future.moves.urllib.parse import quote, quote_plus
from jellypy import common
from jellypy import helpers
from jellypy import http_handler
from jellypy import libraries
from jellypy import logger
from jellypy import session
from jellypy import users
from jellypy import activity_processor


def get_server_friendly_name():
    logger.info("JellyPy JellyConnect :: Requesting name from server...")
    server_name = JellyConnect().get_server_pref(pref='ServerName')

    # If friendly name is blank
    if not server_name:
        servers_info = JellyConnect().get_servers_info()
        for server in servers_info:
            if server['machine_identifier'] == jellypy.CONFIG.JELLYFIN_IDENTIFIER:
                server_name = server['name']
                break

    if server_name and server_name != jellypy.CONFIG.JELLYFIN_NAME:
        jellypy.CONFIG.__setattr__('JELLYFIN_NAME', server_name)
        jellypy.CONFIG.write()
        logger.info("JellyPy JellyConnect :: Server name retrieved.")

    return server_name


class JellyConnect(object):
    """
    Retrieve data from Jellyfin Server
    """

    def __init__(self, url=None, api_key=None):
        self.url = url
        self.api_key = api_key

        if not self.url and jellypy.CONFIG.JELLYFIN_URL:
            self.url = jellypy.CONFIG.JELLYFIN_URL
        elif not self.url:
            self.url = 'http://{hostname}:{port}'.format(hostname=jellypy.CONFIG.JELLYFIN_IP,
                                                         port=jellypy.CONFIG.JELLYFIN_PORT)
        self.timeout = jellypy.CONFIG.JELLYFIN_TIMEOUT

        if not self.api_key:
            # Check if we should use the admin token, or the guest server token
            if session.get_session_user_id():
                user_data = users.Users()
                user_tokens = user_data.get_tokens(user_id=session.get_session_user_id())
                self.api_key = user_tokens['server_token']
            else:
                self.api_key = jellypy.CONFIG.JELLYFIN_API_KEY

        self.ssl_verify = jellypy.CONFIG.VERIFY_SSL_CERT

        self.request_handler = http_handler.HTTPHandler(urls=self.url,
                                                        api_key=self.api_key,
                                                        timeout=self.timeout,
                                                        ssl_verify=self.ssl_verify)

    def get_sessions(self, output_format=''):
        """
        Return current sessions.

        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/Sessions'
        request = self.request_handler.make_request(uri=uri, request_type='GET', output_format=output_format)

        return request

    def get_sessions_terminate(self, session_id='', reason=''):
        """
        Return current sessions.

        Optional parameters:    output_format { dict, json }

        Output: array
        """
        message_uri = f'/Sessions/{session_id}/Message'
        message_data = {
            "Header": "Stream terminated",
            "Text": reason,
            "TimeoutMs": 6
        }

        self.request_handler.make_request(uri=message_uri, request_type='POST', json=message_data)

        uri = f'/Sessions/{session_id}/Playing/Stop'
        request = self.request_handler.make_request(uri=uri,request_type='POST', return_response=True)

        return request

    def get_metadata(self, rating_key='', output_format=''):
        """
        Return metadata for request item.

        Parameters required:    rating_key { Plex ratingKey }
        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/library/metadata/' + rating_key
        request = self.request_handler.make_request(uri=uri, request_type='GET', utput_format=output_format)

        return request

    def get_metadata_grandchildren(self, rating_key='', output_format=''):
        """
        Return metadata for graandchildren of the request item.

        Parameters required:    rating_key { Plex ratingKey }
        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/library/metadata/' + rating_key + '/grandchildren'
        request = self.request_handler.make_request(uri=uri,
                                                    request_type='GET',
                                                    output_format=output_format)

        return request

    def get_playlist_items(self, rating_key='', output_format=''):
        """
        Return metadata for items of the requested playlist.

        Parameters required:    rating_key { Plex ratingKey }
        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/playlists/' + rating_key + '/items'
        request = self.request_handler.make_request(uri=uri,
                                                    request_type='GET',
                                                    output_format=output_format)

        return request

    def get_library_recently_added(self, section_id='', start='0', count='0', output_format=''):
        """
        Return list of recently added items.

        Parameters required:    count { number of results to return }
        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = f'/Users/{jellypy.CONFIG.JELLYFIN_USER_ID}/Items/Latest?parentId={section_id}'
        request = self.request_handler.make_request(uri=uri, request_type='GET', output_format=output_format)

        return request

    def get_library_recently_added_episodes(self, output_format='', series_id="", season_id="", limit=""):
        """
        Return list of recently added items.

        Parameters required:    count { number of results to return }
        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = f'/Shows/{series_id}/Episodes?seasonId={season_id}&limit={limit}'
        request = self.request_handler.make_request(uri=uri, request_type='GET', output_format=output_format)

        return request["Items"]

    def get_library_recently_added_seasons(self, output_format='', series_id=""):
        """
        Return list of recently added items.

        Parameters required:    count { number of results to return }
        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = f'/Shows/{series_id}/Seasons'
        request = self.request_handler.make_request(uri=uri, request_type='GET', output_format=output_format)

        return request["Items"]

    def get_children_list_related(self, rating_key='', output_format=''):
        """
        Return list of related children in requested collection item.

        Parameters required:    rating_key { ratingKey of parent }
        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/hubs/metadata/' + rating_key + '/related'
        request = self.request_handler.make_request(uri=uri,
                                                    request_type='GET',
                                                    output_format=output_format)

        return request

    def get_childrens_list(self, rating_key='', output_format=''):
        """
        Return list of children in requested library item.

        Parameters required:    rating_key { ratingKey of parent }
        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/library/metadata/' + rating_key + '/allLeaves'
        request = self.request_handler.make_request(uri=uri,
                                                    request_type='GET',
                                                    output_format=output_format)

        return request

    def get_server_list(self, output_format=''):
        """
        Return list of local servers.

        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/servers'
        request = self.request_handler.make_request(uri=uri,
                                                    request_type='GET',
                                                    output_format=output_format)

        return request

    def get_server_prefs(self, output_format=''):
        """
        Return the local servers preferences.

        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/:/prefs'
        request = self.request_handler.make_request(uri=uri,
                                                    request_type='GET',
                                                    output_format=output_format)

        return request

    def get_local_server_identity(self, output_format=''):
        """
        Return the local server identity.

        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/identity'
        request = self.request_handler.make_request(uri=uri,
                                                    request_type='GET',
                                                    output_format=output_format)

        return request

    def get_libraries_list(self, output_format=''):
        """
        Return list of libraries on server.

        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/Library/VirtualFolders'
        request = self.request_handler.make_request(uri=uri, request_type='GET', output_format=output_format)

        return request

    def get_library_list(self, section_id='', output_format=''):
        """
        Return list of items in library on server.

        Optional parameters:    output_format { dict, json }

        Output: array
        """

        uri = f"/Items?isMovie=true&isNews=true&isSports=true&isSeries=true&recursive=true&enableTotalRecordCount=true&enableImages=true&parentId={section_id}"
        request = self.request_handler.make_request(uri=uri, request_type='GET', output_format=output_format)

        return request

    def get_movie_library_list(self, section_id, output_format=''):
        """
        Return list of items in library on server.

        Optional parameters:    output_format { dict, json }

        Output: array
        """

        uri = f"/Items?isMovie=true&isSeries=false&isNews=false&isSports=false&recursive=false&enableTotalRecordCount=true&enableImages=true&parentId={section_id}&userId={jellypy.CONFIG.JELLYFIN_USER_ID}"
        request = self.request_handler.make_request(uri=uri, request_type='GET', output_format=output_format)

        return request

    def get_tv_library_list(self, section_id='', output_format=''):
        """
        Return list of items in library on server.

        Optional parameters:    output_format { dict, json }

        Output: array
        """

        uri = f"/Items?isMovies=false&isNews=false&isSports=false&isSeries=true&recursive=false&enableTotalRecordCount=true&enableImages=true&parentId={section_id}&userId={jellypy.CONFIG.JELLYFIN_USER_ID}"
        request = self.request_handler.make_request(uri=uri, request_type='GET', output_format=output_format)

        return request

    def get_tv_season_library_list(self, section_id='', output_format=''):
        """
        Return list of items in library on server.

        Optional parameters:    output_format { dict, json }

        Output: array
        """

        uri = f"/Items?isMovies=false&isNews=false&isSports=false&isSeries=true&recursive=true&enableTotalRecordCount=true&enableImages=true&parentId={section_id}"
        request = self.request_handler.make_request(uri=uri, request_type='GET', output_format=output_format)

        return request

    def get_tv_episode_library_list(self, section_id='', output_format=''):
        """
        Return list of items in library on server.

        Optional parameters:    output_format { dict, json }

        Output: array
        """

        uri = f"/Items?isMovies=false&isNews=false&isSports=false&isSeries=true&recursive=true&enableTotalRecordCount=true&enableImages=true&parentId={section_id}"
        request = self.request_handler.make_request(uri=uri, request_type='GET', output_format=output_format)

        return request

    def fetch_music_library_list(self, section_id='', count='', output_format=''):
        xml_head = []

        start = 0
        _count = 100

        while True:
            library_data = self.get_library_list(
                section_id=str(section_id),
                output_format=output_format
            )

            try:
                for item in library_data['Items']:
                    if 'MediaType' in item:
                        xml_head.append(item)
                        item["TotalRecordCount"] = library_data["TotalRecordCount"]
                        library_count = len(item)
            except Exception as e:
                logger.warn(f"JellyPy JellyConnect :: Unable to parse JSON for fetch_music_library_list: {e}.")
                return xml_head

            start += _count

            if count or start >= library_count:
                break

        return xml_head

    def fetch_movie_library_list(self, section_id, count='', output_format=''):
        xml_head = []

        start = 0
        _count = 100

        while True:
            library_data = self.get_movie_library_list(section_id=section_id, output_format=output_format)

            try:
                for item in library_data['Items']:
                    xml_head.append(item)
            except Exception as e:
                logger.warn(f"JellyPy JellyConnect :: Unable to parse JSON for fetch_movie_library_list: {e}.")
                return xml_head

            library_count = len(xml_head)

            start += _count

            if count or start >= library_count:
                break

        return xml_head

    def fetch_tv_library_list(self, section_id='', count='', output_format=''):
        xml_head = []

        start = 0
        _count = 100

        while True:
            library_data = self.get_tv_library_list(
                section_id=str(section_id),
                output_format=output_format
            )

            try:
                for item in library_data['Items']:
                    xml_head.append(item)
                    item["TotalRecordCount"] = library_data["TotalRecordCount"]

            except Exception as e:
                logger.warn(f"JellyPy JellyConnect :: Unable to parse JSON for fetch_tv_library_list: {e}.")
                return xml_head

            library_count = len(xml_head)

            start += _count

            if count or start >= library_count:
                break

        return xml_head

    def fetch_tv_season_library_list(self, section_id='', count='', output_format=''):
        xml_head = []

        start = 0
        _count = 100

        while True:
            library_data = self.get_tv_season_library_list(section_id=section_id, output_format=output_format)

            try:
                for item in library_data['Items']:
                    if item["Type"] == "Season":
                        xml_head.append(item)
            except Exception as e:
                logger.warn(f"JellyPy JellyConnect :: Unable to parse JSON for fetch_tv_season_library_list: {e}.")
                return xml_head

            library_count = len(xml_head)

            start += _count

            if count or start >= library_count:
                break

        return xml_head

    def fetch_tv_episode_library_list(self, section_id='', count='', output_format=''):
        xml_head = []

        start = 0
        _count = int(count) if count else 100

        while True:
            library_data = self.get_tv_episode_library_list(section_id=str(section_id), output_format=output_format)

            try:
                for item in library_data['Items']:
                    if item["Type"] == "Episode":
                        xml_head.append(item)
            except Exception as e:
                logger.warn(f"JellyPy JellyConnect :: Unable to parse JSON for fetch_tv_episode_library_list: {e}.")
                return xml_head

            library_count = len(xml_head)

            start += _count

            if count or start >= library_count:
                break

        return xml_head

    def get_library_labels(self, section_id='', output_format=''):
        """
        Return list of labels for a library on server.

        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/library/sections/' + section_id + '/label'
        request = self.request_handler.make_request(uri=uri,
                                                    request_type='GET',
                                                    output_format=output_format)

        return request

    def get_sync_item(self, sync_id='', output_format=''):
        """
        Return sync item details.

        Parameters required:    sync_id { unique sync id for item }
        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/sync/items/' + sync_id
        request = self.request_handler.make_request(uri=uri,
                                                    request_type='GET',
                                                    output_format=output_format)

        return request

    def get_sync_transcode_queue(self, output_format=''):
        """
        Return sync transcode queue.

        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/sync/transcodeQueue'
        request = self.request_handler.make_request(uri=uri,
                                                    request_type='GET',
                                                    output_format=output_format)

        return request

    def get_search(self, query='', limit='', output_format=''):
        """
        Return search results.

        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/hubs/search?query=' + quote(query.encode('utf8')) + '&limit=' + limit + '&includeCollections=1'
        request = self.request_handler.make_request(uri=uri,
                                                    request_type='GET',
                                                    output_format=output_format)

        return request

    def get_account(self, output_format=''):
        """
        Return account details.

        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/myplex/account'
        request = self.request_handler.make_request(uri=uri,
                                                    request_type='GET',
                                                    output_format=output_format)

        return request

    def put_refresh_reachability(self):
        """
        Refresh Plex remote access port mapping.

        Optional parameters:    None

        Output: None
        """
        uri = '/myplex/refreshReachability'
        request = self.request_handler.make_request(uri=uri,
                                                    request_type='PUT')

        return request

    def put_updater(self, output_format=''):
        """
        Refresh updater status.

        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/updater/check?download=0'
        request = self.request_handler.make_request(uri=uri,
                                                    request_type='PUT',
                                                    output_format=output_format)

        return request

    def get_updater(self, output_format=''):
        """
        Return updater status.

        Optional parameters:    output_format { dict, json }

        Output: array
        """
        uri = '/updater/status'
        request = self.request_handler.make_request(uri=uri,
                                                    request_type='GET',
                                                    output_format=output_format)

        return request

    def get_hub_recently_added(self, start='0', count='0', section_id='', other_video=False, output_format=''):
        """
        Return Plex hub recently added.

        Parameters required:    start { item number to start from }
                                count { number of results to return }
                                media_type { str }
        Optional parameters:    output_format { dict, json }

        Output: array
        """
        personal = '&personal=1' if other_video else ''
        uri = f'/Users/{jellypy.CONFIG.JELLYFIN_USER_ID}/Items/Latest?parentId={section_id}'
        request = self.request_handler.make_request(uri=uri, request_type='GET', output_format=output_format)

        return request

    def get_recently_added(self, other_video=False, output_format='', type_="", limit=""):
        """
        Return Plex hub recently added.

        Parameters required:    start { item number to start from }
                                count { number of results to return }
                                media_type { str }
        Optional parameters:    output_format { dict, json }

        Output: array
        """
        personal = '&personal=1' if other_video else ''
        uri = f'/Users/{jellypy.CONFIG.JELLYFIN_USER_ID}/Items/Latest?includeItemTypes={type_}&limit={limit}&groupItems=False'
        request = self.request_handler.make_request(uri=uri, request_type='GET', output_format=output_format)

        return request

    def get_media_details(self, item_id, output_format="json"):
        uri = f'/Users/{jellypy.CONFIG.JELLYFIN_USER_ID}/Items/{item_id}'
        request = self.request_handler.make_request(uri=uri, request_type='GET', output_format=output_format)

        return request

    def get_item_ancestors(self, item_id, output_format="json"):
        uri = f'/Items/{item_id}/Ancestors'
        request = self.request_handler.make_request(uri=uri, request_type='GET', output_format=output_format)

        return request

    def get_recently_added_details(self, start='0', count='0', media_type='', section_id=''):
        """
        Return processed and validated list of recently added items.

        Parameters required:    count { number of results to return }

        Output: array
        """
        if media_type == "movie":
            media_type = "Movie"
        if media_type == "show":
            media_type = "Series"
        # Workaround to display recently added episodes
        if media_type == "episode":
            media_type = "Episode"

        media_types = ('Movie', 'Series', 'artist', 'other_video', 'Episode', 'Season')
        recents_list = []

        if media_type in media_types:
            other_video = False
            if media_type == 'other_video' or media_type == "artist":
                other_video = True
                return {'recently_added': []}
            recent = self.get_recently_added(other_video=other_video, type_=media_type, output_format='json',
                                             limit=count)
        elif section_id:
            recent = self.get_library_recently_added(section_id, start, count, output_format='json')
        else:
            for media_type in media_types:
                recents = self.get_recently_added_details(start, count, media_type)
                recents_list.extend(recents['recently_added'])

            output = {
                'recently_added': sorted(recents_list, key=lambda k: k['added_at'], reverse=True)[:int(count)]
            }
            return output

        try:
            xml_head = recent
        except Exception as e:
            logger.warn(f"JellyPy JellyConnect :: Unable to parse JSON for get_recently_added: {e}.")
            return {
                'recently_added': []
            }

        if xml_head == {}:
            output = {
                'recently_added': []
            }
            return output

        # TODO: Add episodes to recently added group in homepage in TV Shows section instead of a seperate one.

        for a in xml_head:
            recents_main = []
            item_id = a["Id"]

            if a["Type"] == "Movie" or a["Type"] == "Episode":
                recents_main.append(a)

            if a["Type"] == "Series":
                if section_id:
                    result_ = self.get_library_recently_added_episodes(series_id=item_id, output_format="json",
                                                                       limit=count)
                    for result in result_:
                        recents_main.append(result)
                else:
                    recents_main.append(a)

            for m in recents_main:
                directors = []
                writers = []
                actors = []
                genres = []
                labels = []
                collections = []
                guids = []
                studios = []

                details = self.get_media_details(item_id, output_format="json")

                if m["Type"] == "Episode":
                    ancestors = self.get_item_ancestors(m["Id"], output_format="json")
                else:
                    ancestors = self.get_item_ancestors(item_id, output_format="json")

                for director in details["People"]:
                    if director["Role"] == "Director":
                        directors.append(director['Name'])

                for writer in details["People"]:
                    if writer["Type"] == "Writer":
                        writers.append(writer['Name'])

                for actor in details["People"]:
                    if actor["Type"] == "Actor":
                        actors.append(actor['Name'])

                for genre in details["Genres"]:
                    genres.append(genre)

                for studio in details["Studios"]:
                    studios.append(studio['Name'])

                try:
                    if "Tmdb" in details["ProviderIds"]:
                        guids.append(f"tmdb://{details['ProviderIds']['Tmdb']}")
                    if "Imdb" in details["ProviderIds"]:
                        guids.append(f"imdb://{details['ProviderIds']['Imdb']}")
                except KeyError:
                    pass

                recent_item = {
                    'media_type': m["Type"],
                    'section_id': section_id,
                    'library_name': ancestors[0]["Name"],
                    'rating_key': helpers.get_json_attr(m, 'Id'),
                    'parent_rating_key': ancestors[0]["Id"],
                    'grandparent_rating_key': ancestors[1]["Id"],
                    'title': helpers.get_json_attr(m, 'Name'),
                    'parent_title': ancestors[0]["Name"],
                    'grandparent_title': ancestors[1]["Name"],
                    'sort_title': details["SortName"],
                    'media_index': helpers.get_json_attr(m, 'IndexNumber'),
                    'parent_media_index': helpers.get_json_attr(m, 'ParentIndexNumber'),
                    'studio': ", ".join(studios),
                    'content_rating': helpers.get_json_attr(m, 'OfficialRating'),
                    'summary': helpers.get_json_attr(m, 'Overview'),
                    'tagline': ", ".join(details["Taglines"]),
                    'rating': helpers.get_json_attr(m, 'CommunityRating'),
                    'rating_image': helpers.get_json_attr(m, 'ratingImage'),
                    'audience_rating': helpers.get_json_attr(m, 'audienceRating'),
                    'audience_rating_image': helpers.get_json_attr(m, 'audienceRatingImage'),
                    'user_rating': helpers.get_json_attr(m, 'userRating'),
                    'duration': helpers.get_json_attr(m, 'RunTimeTicks'),
                    'year': helpers.get_json_attr(m, 'ProductionYear'),
                    'thumb': f"/Items/{helpers.get_json_attr(m, 'Id')}/Images/Primary",
                    'parent_thumb': f"/Items/{ancestors[0]['Id']}/Images/Primary",
                    'grandparent_thumb': f"/Items/{ancestors[1]['Id']}/Images/Primary",
                    'art': f"/Items/{helpers.get_json_attr(m, 'Id')}/Images/Art",
                    'banner': f"/Items/{helpers.get_json_attr(m, 'Id')}/Images/Banner",
                    'originally_available_at': helpers.get_json_attr(m, 'PremiereDate'),
                    'added_at': helpers.datetime_to_unix(details["DateCreated"]),
                    'updated_at': helpers.datetime_to_unix(details["DateCreated"]),
                    'last_viewed_at': helpers.get_json_attr(m, 'lastViewedAt'),
                    'guid': helpers.get_json_attr(m, 'guid'),
                    'directors': ", ".join(directors),
                    'writers': ", ".join(writers),
                    'actors': ", ".join(actors),
                    'genres': ", ".join(genres),
                    'labels': ", ".join(labels),
                    'collections': ", ".join(collections),
                    'guids': ", ".join(guids),
                    'full_title': helpers.get_json_attr(details, 'Name'),
                    'child_count': helpers.get_json_attr(details, 'ChildCount')
                }

                try:
                    if details["OriginalTitle"]:
                        recent_item["original_title"] = details["OriginalTitle"]
                except KeyError:
                    pass

                recents_list.append(recent_item)

        output = {'recently_added': sorted(recents_list, key=lambda k: k['added_at'], reverse=True)}

        return output

    def get_parent_id(self, item_id, search_term='', output_format="json"):
        uri = f'/Items?isMovie=true&recursive=false&topparentId={item_id}&userId={jellypy.CONFIG.JELLYFIN_USER_ID}&includeItemTypes=CollectionFolder'
        request = self.request_handler.make_request(uri=uri, request_type='GET', output_format=output_format)

        sanitized_text = re.sub(r"[^a-zA-Z0-9 ]", "", search_term)

        try:
            split = sanitized_text.split()
            for item in request["Items"]:
                if re.search(split[0], item["Name"], re.IGNORECASE):
                    return item
        except:
            for item in request["Items"]:
                if search_term in item_id["Name"]:
                    return item

    def get_metadata_details(self, rating_key='', sync_id='', plex_guid='', section_id='',
                             skip_cache=False, cache_key=None, return_cache=False, media_info=True):
        """
        Return processed and validated metadata list for requested item.

        Parameters required:    rating_key { Plex ratingKey }

        Output: array
        """
        metadata = {}

        if not skip_cache and cache_key:
            in_file_folder = os.path.join(jellypy.CONFIG.CACHE_DIR, 'session_metadata')
            in_file_path = os.path.join(in_file_folder, 'metadata-sessionKey-%s.json' % cache_key)

            if not os.path.exists(in_file_folder):
                os.mkdir(in_file_folder)

            try:
                with open(in_file_path, 'r') as inFile:
                    metadata = json.load(inFile)
            except (IOError, ValueError) as e:
                pass

            if metadata:
                _cache_time = metadata.pop('_cache_time', 0)
                # Return cached metadata if less than cache_seconds ago
                if return_cache or helpers.timestamp() - _cache_time <= jellypy.CONFIG.METADATA_CACHE_SECONDS:
                    return metadata

        if rating_key:
            metadata_xml = self.get_media_details(str(rating_key), output_format='json')
        elif sync_id:
            metadata_xml = self.get_sync_item(str(sync_id), output_format='xml')
        elif plex_guid.startswith(('plex://movie', 'plex://episode')):
            rating_key = plex_guid.rsplit('/', 1)[-1]
            plextv_metadata = JellyConnect(url='https://metadata.provider.plex.tv',
                                           token=jellypy.CONFIG.JELLYFIN_API_KEY)
            metadata_xml = plextv_metadata.get_metadata(rating_key, output_format='xml')
        else:
            return metadata

        try:
            xml_head = metadata_xml
        except Exception as e:
            logger.warn("JellyPy JellyConnect :: Unable to parse JSON for get_metadata_details: %s." % e)
            return {}

        if len(xml_head) == 0:
            return metadata

        """if a.getElementsByTagName('Directory'):
                metadata_main_list = a.getElementsByTagName('Directory')
            elif a.getElementsByTagName('Video'):
                metadata_main_list = a.getElementsByTagName('Video')
            elif a.getElementsByTagName('Track'):
                metadata_main_list = a.getElementsByTagName('Track')
            elif a.getElementsByTagName('Photo'):
                metadata_main_list = a.getElementsByTagName('Photo')
            elif a.getElementsByTagName('Playlist'):
                metadata_main_list = a.getElementsByTagName('Playlist')
            else:
                logger.debug("JellyPy JellyConnect :: Metadata fetching failed")
                return {}

            if sync_id and len(metadata_main_list) > 1:
                for metadata_main in metadata_main_list:
                    if helpers.get_xml_attr(metadata_main, 'ratingKey') == rating_key:
                        break
            else:
                metadata_main = metadata_main_list[0]

            if metadata_main.nodeName == 'Directory' and metadata_type == 'photo':
                metadata_type = 'photo_album'

            section_id = helpers.get_xml_attr(a, 'librarySectionID') or section_id
            library_name = helpers.get_xml_attr(a, 'librarySectionTitle')"""

        metadata_type = xml_head["Type"].lower()

        if metadata_type == "series":
            metadata_type = "show"

        if metadata_type == "movie":
            section_id_ = self.get_item_ancestors(xml_head["Id"])
            library_name_ = section_id_[0]["Name"]
        elif metadata_type == "episode":
            section_id_ = self.get_item_ancestors(xml_head["Id"])
            library_name_ = section_id_[2]["Name"]
        elif metadata_type == "show":
            section_id_ = self.get_item_ancestors(xml_head["Id"])
            library_name_ = section_id_[0]["Name"]
        elif metadata_type == "season":
            section_id_ = self.get_item_ancestors(xml_head["Id"])
            library_name_ = section_id_[1]["Name"]

        real_id = self.get_parent_id(xml_head["Id"], library_name_)

        library_name = real_id["Name"]
        section_id = real_id["Id"]

        if not library_name and section_id:
            library_data = libraries.Libraries().get_details(section_id)
            library_name = library_data['section_name']

        directors = []
        writers = []
        actors = []
        genres = []
        labels = []
        collections = []
        guids = []
        studios = []

        details = self.get_media_details(xml_head["Id"], output_format="json")

        ancestors = self.get_item_ancestors(xml_head["Id"], output_format="json")

        for director in details["People"]:
            if director["Role"] == "Director":
                directors.append(director['Name'])

        for writer in details["People"]:
            if writer["Type"] == "Writer":
                writers.append(writer['Name'])

        for actor in details["People"]:
            if actor["Type"] == "Actor":
                actors.append(actor['Name'])

        for genre in details["Genres"]:
            genres.append(genre)

        for studio in details["Studios"]:
            studios.append(studio['Name'])

        try:
            if "Tmdb" in details["ProviderIds"]:
                guids.append(f"tmdb://{details['ProviderIds']['Tmdb']}")
            if "Imdb" in details["ProviderIds"]:
                guids.append(f"imdb://{details['ProviderIds']['Imdb']}")
        except KeyError:
            pass

        """if metadata_main.getElementsByTagName('Director'):
            for director in metadata_main.getElementsByTagName('Director'):
                directors.append(helpers.get_xml_attr(director, 'tag'))

        if metadata_main.getElementsByTagName('Writer'):
            for writer in metadata_main.getElementsByTagName('Writer'):
                writers.append(helpers.get_xml_attr(writer, 'tag'))

        if metadata_main.getElementsByTagName('Role'):
            for actor in metadata_main.getElementsByTagName('Role'):
                actors.append(helpers.get_xml_attr(actor, 'tag'))

        if metadata_main.getElementsByTagName('Genre'):
            for genre in metadata_main.getElementsByTagName('Genre'):
                genres.append(helpers.get_xml_attr(genre, 'tag'))

        if metadata_main.getElementsByTagName('Label'):
            for label in metadata_main.getElementsByTagName('Label'):
                labels.append(helpers.get_xml_attr(label, 'tag'))

        if metadata_main.getElementsByTagName('Collection'):
            for collection in metadata_main.getElementsByTagName('Collection'):
                collections.append(helpers.get_xml_attr(collection, 'tag'))

        if metadata_main.getElementsByTagName('Guid'):
            for guid in metadata_main.getElementsByTagName('Guid'):
                guids.append(helpers.get_xml_attr(guid, 'id'))"""

        try:
            duration = helpers.datetime_to_unix(helpers.convert_ticks(helpers.get_json_attr(xml_head, 'RunTimeTicks')))
        except TypeError:
            duration = ""

        if metadata_type == 'movie':
            metadata = {
                'media_type': metadata_type,
                'section_id': section_id,
                'library_name': library_name,
                'rating_key': xml_head["Id"],
                'parent_rating_key': ancestors[0]["Id"],
                'grandparent_rating_key': ancestors[1]["Id"],
                'title': helpers.get_json_attr(xml_head, 'Name'),
                'parent_title': ancestors[0]["Name"],
                'grandparent_title': ancestors[1]["Name"],
                'sort_title': details["SortName"],
                'edition_title': helpers.get_json_attr(xml_head, 'editionTitle'),
                'media_index': helpers.get_json_attr(xml_head, 'IndexNumber'),
                'parent_media_index': helpers.get_json_attr(xml_head, 'ParentIndexNumber'),
                'studio': ", ".join(studios),
                'content_rating': helpers.get_json_attr(xml_head, 'OfficialRating'),
                'summary': helpers.get_json_attr(xml_head, 'Overview'),
                'tagline': ", ".join(details["Taglines"]),
                'rating': helpers.get_json_attr(xml_head, 'CommunityRating'),
                'rating_image': helpers.get_json_attr(xml_head, 'ratingImage'),
                'audience_rating': helpers.get_json_attr(xml_head, 'audienceRating'),
                'audience_rating_image': helpers.get_json_attr(xml_head, 'audienceRatingImage'),
                'user_rating': helpers.get_json_attr(xml_head, 'userRating'),
                'duration': duration,
                'year': helpers.get_json_attr(xml_head, 'ProductionYear'),
                'parent_year': helpers.get_json_attr(xml_head, 'parentYear'),
                'grandparent_year': helpers.get_json_attr(xml_head, 'grandparentYear'),
                'thumb': f"/Items/{helpers.get_json_attr(xml_head, 'Id')}/Images/Primary",
                'parent_thumb': f"/Items/{ancestors[0]['Id']}/Images/Primary",
                'grandparent_thumb': f"/Items/{ancestors[1]['Id']}/Images/Primary",
                'art': f"/Items/{helpers.get_json_attr(xml_head, 'Id')}/Images/Art",
                'banner': f"/Items/{helpers.get_json_attr(xml_head, 'Id')}/Images/Banner",
                'originally_available_at': helpers.get_json_attr(xml_head, 'PremiereDate'),
                'added_at': helpers.datetime_to_unix(details["DateCreated"]),
                'updated_at': helpers.datetime_to_unix(details["DateCreated"]),
                'last_viewed_at': helpers.get_json_attr(xml_head, 'lastViewedAt'),
                'guid': helpers.get_json_attr(xml_head, 'guid'),
                'parent_guid': helpers.get_json_attr(xml_head, 'parentGuid'),
                'grandparent_guid': helpers.get_json_attr(xml_head, 'grandparentGuid'),
                'directors': directors,
                'writers': writers,
                'actors': actors,
                'genres': genres,
                'labels': labels,
                'collections': collections,
                'guids': guids,
                'parent_guids': [],
                'grandparent_guids': [],
                'full_title': helpers.get_json_attr(xml_head, 'Name'),
                'children_count': helpers.cast_to_int(helpers.get_json_attr(xml_head, 'leafCount')),
                'live': int(helpers.get_json_attr(xml_head, 'live') == '1')
            }

            try:
                if details["OriginalTitle"]:
                    metadata["original_title"] = details["OriginalTitle"]
            except KeyError:
                pass

        elif metadata_type == 'show':
            # Workaround for for duration sometimes reported in minutes for a show

            metadata = {
                'media_type': metadata_type,
                'section_id': section_id,
                'library_name': library_name,
                'rating_key': xml_head["Id"],
                'parent_rating_key': ancestors[0]["Id"],
                'grandparent_rating_key': ancestors[1]["Id"],
                'title': helpers.get_json_attr(xml_head, 'Name'),
                'parent_title': ancestors[0]["Name"],
                'grandparent_title': ancestors[1]["Name"],
                'sort_title': helpers.get_json_attr(xml_head, 'editionTitle'),
                'edition_title': helpers.get_json_attr(xml_head, 'editionTitle'),
                'media_index': helpers.get_json_attr(xml_head, 'IndexNumber'),
                'parent_media_index': helpers.get_json_attr(xml_head, 'ParentIndexNumber'),
                'studio': ", ".join(studios),
                'content_rating': helpers.get_json_attr(xml_head, 'OfficialRating'),
                'summary': helpers.get_json_attr(xml_head, 'Overview'),
                'tagline': ", ".join(details["Taglines"]),
                'rating': helpers.get_json_attr(xml_head, 'CommunityRating'),
                'rating_image': helpers.get_json_attr(xml_head, 'ratingImage'),
                'audience_rating': helpers.get_json_attr(xml_head, 'audienceRating'),
                'audience_rating_image': helpers.get_json_attr(xml_head, 'audienceRatingImage'),
                'user_rating': helpers.get_json_attr(xml_head, 'userRating'),
                'duration': duration,
                'year': helpers.get_json_attr(xml_head, 'ProductionYear'),
                'parent_year': helpers.get_json_attr(xml_head, 'parentYear'),
                'grandparent_year': helpers.get_json_attr(xml_head, 'grandparentYear'),
                'thumb': f"/Items/{helpers.get_json_attr(xml_head, 'Id')}/Images/Primary",
                'parent_thumb': f"/Items/{ancestors[0]['Id']}/Images/Primary",
                'grandparent_thumb': f"/Items/{ancestors[1]['Id']}/Images/Primary",
                'art': f"/Items/{helpers.get_json_attr(xml_head, 'Id')}/Images/Art",
                'banner': f"/Items/{helpers.get_json_attr(xml_head, 'Id')}/Images/Banner",
                'originally_available_at': helpers.get_json_attr(xml_head, 'PremiereDate'),
                'added_at': helpers.datetime_to_unix(details["DateCreated"]),
                'updated_at': helpers.datetime_to_unix(details["DateCreated"]),
                'last_viewed_at': helpers.get_json_attr(xml_head, 'lastViewedAt'),
                'guid': helpers.get_json_attr(xml_head, 'guid'),
                'parent_guid': helpers.get_json_attr(xml_head, 'parentGuid'),
                'grandparent_guid': helpers.get_json_attr(xml_head, 'grandparentGuid'),
                'directors': directors,
                'writers': writers,
                'actors': actors,
                'genres': genres,
                'labels': labels,
                'collections': collections,
                'guids': guids,
                'parent_guids': [],
                'grandparent_guids': [],
                'full_title': helpers.get_json_attr(xml_head, 'Name'),
                'children_count': helpers.cast_to_int(helpers.get_json_attr(xml_head, 'leafCount')),
                'live': int(helpers.get_json_attr(xml_head, 'live') == '1')
            }

            try:
                if details["OriginalTitle"]:
                    metadata["original_title"] = details["OriginalTitle"]
            except KeyError:
                pass

        elif metadata_type == 'season':
            parent_rating_key = ancestors[0]["Id"]
            grandparent_rating_key = ancestors[1]["Id"]

            """parent_guid = helpers.get_xml_attr(metadata_main, 'parentGuid')
            show_details = {}
            if plex_guid and parent_guid:
                show_details = self.get_metadata_details(plex_guid=parent_guid)
            elif not plex_guid and parent_rating_key:
                show_details = self.get_metadata_details(parent_rating_key)"""

            metadata = {
                'media_type': metadata_type,
                'section_id': section_id,
                'library_name': library_name,
                'rating_key': helpers.get_json_attr(xml_head, 'Id'),
                'parent_rating_key': parent_rating_key,
                'grandparent_rating_key': grandparent_rating_key,
                'title': helpers.get_json_attr(xml_head, 'Name'),
                'parent_title': ancestors[0]["Name"],
                'grandparent_title': ancestors[1]["Name"],
                'sort_title': details["SortName"],
                'edition_title': helpers.get_json_attr(xml_head, 'editionTitle'),
                'media_index': helpers.get_json_attr(xml_head, 'IndexNumber'),
                'parent_media_index': helpers.get_json_attr(xml_head, 'ParentIndexNumber'),
                'studio': ", ".join(studios),
                'content_rating': helpers.get_json_attr(xml_head, 'OfficialRating'),
                'summary': helpers.get_json_attr(xml_head, 'Overview'),
                'tagline': ", ".join(details["Taglines"]),
                'rating': helpers.get_json_attr(xml_head, 'CommunityRating'),
                'rating_image': helpers.get_json_attr(xml_head, 'ratingImage'),
                'audience_rating': helpers.get_json_attr(xml_head, 'audienceRating'),
                'audience_rating_image': helpers.get_json_attr(xml_head, 'audienceRatingImage'),
                'user_rating': helpers.get_json_attr(xml_head, 'userRating'),
                'duration': duration,
                'year': helpers.get_json_attr(xml_head, 'ProductionYear'),
                'parent_year': helpers.get_json_attr(ancestors[0], 'ProductionYear'),
                'grandparent_year': helpers.get_json_attr(ancestors[1], 'ProductionYear'),
                'thumb': f"/Items/{helpers.get_json_attr(xml_head, 'Id')}/Images/Primary",
                'parent_thumb': f"/Items/{ancestors[0]['Id']}/Images/Primary",
                'grandparent_thumb': f"/Items/{ancestors[1]['Id']}/Images/Primary",
                'art': f"/Items/{helpers.get_json_attr(xml_head, 'Id')}/Images/Art",
                'banner': f"/Items/{helpers.get_json_attr(xml_head, 'Id')}/Images/Banner",
                'originally_available_at': helpers.get_json_attr(xml_head, 'PremiereDate'),
                'added_at': helpers.datetime_to_unix(details["DateCreated"]),
                'updated_at': helpers.datetime_to_unix(details["DateCreated"]),
                'last_viewed_at': helpers.get_json_attr(xml_head, 'lastViewedAt'),
                'guid': helpers.get_json_attr(xml_head, 'guid'),
                'parent_guid': helpers.get_json_attr(xml_head, 'parentGuid'),
                'grandparent_guid': helpers.get_json_attr(xml_head, 'grandparentGuid'),
                'directors': directors,
                'writers': writers,
                'actors': actors,
                'genres': genres,
                'labels': labels,
                'collections': collections,
                'guids': guids,
                'parent_guids': [],
                'grandparent_guids': [],
                'full_title': f'{helpers.get_json_attr(xml_head, "SeriesName")} - {helpers.get_json_attr(xml_head, "Name")}',
                'children_count': len(xml_head),
                'live': int(helpers.get_json_attr(xml_head, 'live') == '1')
            }

            try:
                if details["OriginalTitle"]:
                    metadata["original_title"] = details["OriginalTitle"]
            except KeyError:
                pass

        elif metadata_type == 'episode':
            """grandparent_guid = helpers.get_xml_attr(metadata_main, 'grandparentGuid')
            show_details = {}
            if plex_guid and grandparent_guid:
                show_details = self.get_metadata_details(plex_guid=grandparent_guid)
            elif not plex_guid and grandparent_rating_key:
                show_details = self.get_metadata_details(grandparent_rating_key)"""

            parent_rating_key = ancestors[0]["Id"]
            grandparent_rating_key = ancestors[1]["Id"]
            parent_media_index = helpers.get_json_attr(xml_head, 'ParentIndexNumber')
            parent_thumb = helpers.get_json_attr(xml_head, 'ParentLogoItemId')
            # season_details = self.get_metadata_details(parent_rating_key) if parent_rating_key else {}

            """if not plex_guid and not parent_rating_key:
                # Try getting the parent_rating_key from the parent_thumb
                if parent_thumb.startswith('/library/metadata/'):
                    parent_rating_key = parent_thumb.split('/')[3]

                # Try getting the parent_rating_key from the grandparent's children
                if not parent_rating_key and grandparent_rating_key:
                    children_list = self.get_item_children(grandparent_rating_key)
                    parent_rating_key = next((c['rating_key'] for c in children_list['children_list']
                                              if c['media_index'] == parent_media_index), '')"""

            metadata = {
                'media_type': metadata_type,
                'section_id': section_id,
                'library_name': library_name,
                'rating_key': xml_head["Id"],
                'parent_rating_key': parent_rating_key,
                'grandparent_rating_key': grandparent_rating_key,
                'title': helpers.get_json_attr(xml_head, 'Name'),
                'parent_title': ancestors[0]["Name"],
                'grandparent_title': ancestors[1]["Name"],
                'sort_title': details["SortName"],
                'edition_title': helpers.get_json_attr(xml_head, 'editionTitle'),
                'media_index': helpers.get_json_attr(xml_head, 'IndexNumber'),
                'parent_media_index': parent_media_index,
                'studio': ", ".join(studios),
                'content_rating': helpers.get_json_attr(xml_head, 'OfficialRating'),
                'summary': helpers.get_json_attr(xml_head, 'Overview'),
                'tagline': ", ".join(details["Taglines"]),
                'rating': helpers.get_json_attr(xml_head, 'CommunityRating'),
                'rating_image': helpers.get_json_attr(xml_head, 'ratingImage'),
                'audience_rating': helpers.get_json_attr(xml_head, 'audienceRating'),
                'audience_rating_image': helpers.get_json_attr(xml_head, 'audienceRatingImage'),
                'user_rating': helpers.get_json_attr(xml_head, 'userRating'),
                'duration': helpers.get_json_attr(xml_head, 'RunTimeTicks'),
                'year': helpers.get_json_attr(xml_head, 'ProductionYear'),
                'parent_year': helpers.get_json_attr(xml_head, 'ProductionYear'),
                'grandparent_year': helpers.get_json_attr(xml_head, 'grandparentYear'),
                'thumb': f"/Items/{helpers.get_json_attr(xml_head, 'Id')}/Images/Primary",
                'parent_thumb': parent_thumb,
                'grandparent_thumb': f"/Items/{ancestors[1]['Id']}/Images/Primary",
                'art': f"/Items/{helpers.get_json_attr(xml_head, 'Id')}/Images/Art",
                'banner': f"/Items/{helpers.get_json_attr(xml_head, 'Id')}/Images/Banner",
                'originally_available_at': helpers.get_json_attr(xml_head, 'PremiereDate'),
                'added_at': helpers.datetime_to_unix(details["DateCreated"]),
                'updated_at': helpers.datetime_to_unix(details["DateCreated"]),
                'last_viewed_at': helpers.get_json_attr(xml_head, 'lastViewedAt'),
                'guid': helpers.get_json_attr(xml_head, 'guid'),
                'parent_guid': helpers.get_json_attr(xml_head, 'parentGuid'),
                'grandparent_guid': helpers.get_json_attr(xml_head, 'grandparentGuid'),
                'directors': directors,
                'writers': writers,
                'actors': actors,
                'genres': genres,
                'labels': labels,
                'collections': collections,
                'guids': guids,
                'parent_guids': [],
                'grandparent_guids': [],
                'full_title': f'{helpers.get_json_attr(xml_head, "SeriesName")} - {helpers.get_json_attr(xml_head, "Name")}',
                'children_count': helpers.cast_to_int(helpers.get_json_attr(xml_head, 'leafCount')),
                'live': int(helpers.get_json_attr(xml_head, 'live') == '1')
            }

            try:
                if details["OriginalTitle"]:
                    metadata["original_title"] = details["OriginalTitle"]
            except KeyError:
                pass

        elif metadata_type == 'artist':
            metadata = {'media_type': metadata_type,
                        'section_id': section_id,
                        'library_name': library_name,
                        'rating_key': helpers.get_xml_attr(metadata_main, 'ratingKey'),
                        'parent_rating_key': helpers.get_xml_attr(metadata_main, 'parentRatingKey'),
                        'grandparent_rating_key': helpers.get_xml_attr(metadata_main, 'grandparentRatingKey'),
                        'title': helpers.get_xml_attr(metadata_main, 'title'),
                        'parent_title': helpers.get_xml_attr(metadata_main, 'parentTitle'),
                        'grandparent_title': helpers.get_xml_attr(metadata_main, 'grandparentTitle'),
                        'original_title': helpers.get_xml_attr(metadata_main, 'originalTitle'),
                        'sort_title': helpers.get_xml_attr(metadata_main, 'titleSort'),
                        'edition_title': helpers.get_xml_attr(metadata_main, 'editionTitle'),
                        'media_index': helpers.get_xml_attr(metadata_main, 'index'),
                        'parent_media_index': helpers.get_xml_attr(metadata_main, 'parentIndex'),
                        'studio': helpers.get_xml_attr(metadata_main, 'studio'),
                        'content_rating': helpers.get_xml_attr(metadata_main, 'contentRating'),
                        'summary': helpers.get_xml_attr(metadata_main, 'summary'),
                        'tagline': helpers.get_xml_attr(metadata_main, 'tagline'),
                        'rating': helpers.get_xml_attr(metadata_main, 'rating'),
                        'rating_image': helpers.get_xml_attr(metadata_main, 'ratingImage'),
                        'audience_rating': helpers.get_xml_attr(metadata_main, 'audienceRating'),
                        'audience_rating_image': helpers.get_xml_attr(metadata_main, 'audienceRatingImage'),
                        'user_rating': helpers.get_xml_attr(metadata_main, 'userRating'),
                        'duration': helpers.get_xml_attr(metadata_main, 'duration'),
                        'year': helpers.get_xml_attr(metadata_main, 'year'),
                        'parent_year': helpers.get_xml_attr(metadata_main, 'parentYear'),
                        'grandparent_year': helpers.get_xml_attr(metadata_main, 'grandparentYear'),
                        'thumb': helpers.get_xml_attr(metadata_main, 'thumb'),
                        'parent_thumb': helpers.get_xml_attr(metadata_main, 'parentThumb'),
                        'grandparent_thumb': helpers.get_xml_attr(metadata_main, 'grandparentThumb'),
                        'art': helpers.get_xml_attr(metadata_main, 'art'),
                        'banner': helpers.get_xml_attr(metadata_main, 'banner'),
                        'originally_available_at': helpers.get_xml_attr(metadata_main, 'originallyAvailableAt'),
                        'added_at': helpers.get_xml_attr(metadata_main, 'addedAt'),
                        'updated_at': helpers.get_xml_attr(metadata_main, 'updatedAt'),
                        'last_viewed_at': helpers.get_xml_attr(metadata_main, 'lastViewedAt'),
                        'guid': helpers.get_xml_attr(metadata_main, 'guid'),
                        'parent_guid': helpers.get_xml_attr(metadata_main, 'parentGuid'),
                        'grandparent_guid': helpers.get_xml_attr(metadata_main, 'grandparentGuid'),
                        'directors': directors,
                        'writers': writers,
                        'actors': actors,
                        'genres': genres,
                        'labels': labels,
                        'collections': collections,
                        'guids': guids,
                        'parent_guids': [],
                        'grandparent_guids': [],
                        'full_title': helpers.get_xml_attr(metadata_main, 'title'),
                        'children_count': helpers.cast_to_int(helpers.get_xml_attr(metadata_main, 'leafCount')),
                        'live': int(helpers.get_xml_attr(metadata_main, 'live') == '1')
                        }

        elif metadata_type == 'album':
            parent_rating_key = helpers.get_xml_attr(metadata_main, 'parentRatingKey')
            artist_details = self.get_metadata_details(parent_rating_key) if parent_rating_key else {}
            metadata = {'media_type': metadata_type,
                        'section_id': section_id,
                        'library_name': library_name,
                        'rating_key': helpers.get_xml_attr(metadata_main, 'ratingKey'),
                        'parent_rating_key': helpers.get_xml_attr(metadata_main, 'parentRatingKey'),
                        'grandparent_rating_key': helpers.get_xml_attr(metadata_main, 'grandparentRatingKey'),
                        'title': helpers.get_xml_attr(metadata_main, 'title'),
                        'parent_title': helpers.get_xml_attr(metadata_main, 'parentTitle'),
                        'grandparent_title': helpers.get_xml_attr(metadata_main, 'grandparentTitle'),
                        'original_title': helpers.get_xml_attr(metadata_main, 'originalTitle'),
                        'sort_title': helpers.get_xml_attr(metadata_main, 'titleSort'),
                        'edition_title': helpers.get_xml_attr(metadata_main, 'editionTitle'),
                        'media_index': helpers.get_xml_attr(metadata_main, 'index'),
                        'parent_media_index': helpers.get_xml_attr(metadata_main, 'parentIndex'),
                        'studio': helpers.get_xml_attr(metadata_main, 'studio'),
                        'content_rating': helpers.get_xml_attr(metadata_main, 'contentRating'),
                        'summary': helpers.get_xml_attr(metadata_main, 'summary') or artist_details.get('summary', ''),
                        'tagline': helpers.get_xml_attr(metadata_main, 'tagline'),
                        'rating': helpers.get_xml_attr(metadata_main, 'rating'),
                        'rating_image': helpers.get_xml_attr(metadata_main, 'ratingImage'),
                        'audience_rating': helpers.get_xml_attr(metadata_main, 'audienceRating'),
                        'audience_rating_image': helpers.get_xml_attr(metadata_main, 'audienceRatingImage'),
                        'user_rating': helpers.get_xml_attr(metadata_main, 'userRating'),
                        'duration': helpers.get_xml_attr(metadata_main, 'duration'),
                        'year': helpers.get_xml_attr(metadata_main, 'year'),
                        'parent_year': helpers.get_xml_attr(metadata_main, 'parentYear'),
                        'grandparent_year': helpers.get_xml_attr(metadata_main, 'grandparentYear'),
                        'thumb': helpers.get_xml_attr(metadata_main, 'thumb'),
                        'parent_thumb': helpers.get_xml_attr(metadata_main, 'parentThumb'),
                        'grandparent_thumb': helpers.get_xml_attr(metadata_main, 'grandparentThumb'),
                        'art': helpers.get_xml_attr(metadata_main, 'art'),
                        'banner': artist_details.get('banner', ''),
                        'originally_available_at': helpers.get_xml_attr(metadata_main, 'originallyAvailableAt'),
                        'added_at': helpers.get_xml_attr(metadata_main, 'addedAt'),
                        'updated_at': helpers.get_xml_attr(metadata_main, 'updatedAt'),
                        'last_viewed_at': helpers.get_xml_attr(metadata_main, 'lastViewedAt'),
                        'guid': helpers.get_xml_attr(metadata_main, 'guid'),
                        'parent_guid': helpers.get_xml_attr(metadata_main, 'parentGuid'),
                        'grandparent_guid': helpers.get_xml_attr(metadata_main, 'grandparentGuid'),
                        'directors': directors,
                        'writers': writers,
                        'actors': actors,
                        'genres': genres,
                        'labels': labels,
                        'collections': collections,
                        'guids': guids,
                        'parent_guids': artist_details.get('guids', []),
                        'grandparent_guids': [],
                        'full_title': '{} - {}'.format(helpers.get_xml_attr(metadata_main, 'parentTitle'),
                                                       helpers.get_xml_attr(metadata_main, 'title')),
                        'children_count': helpers.cast_to_int(helpers.get_xml_attr(metadata_main, 'leafCount')),
                        'live': int(helpers.get_xml_attr(metadata_main, 'live') == '1')
                        }

        elif metadata_type == 'track':
            parent_rating_key = helpers.get_xml_attr(metadata_main, 'parentRatingKey')
            album_details = self.get_metadata_details(parent_rating_key) if parent_rating_key else {}
            track_artist = helpers.get_xml_attr(metadata_main, 'originalTitle') or \
                           helpers.get_xml_attr(metadata_main, 'grandparentTitle')
            metadata = {'media_type': metadata_type,
                        'section_id': section_id,
                        'library_name': library_name,
                        'rating_key': helpers.get_xml_attr(metadata_main, 'ratingKey'),
                        'parent_rating_key': helpers.get_xml_attr(metadata_main, 'parentRatingKey'),
                        'grandparent_rating_key': helpers.get_xml_attr(metadata_main, 'grandparentRatingKey'),
                        'title': helpers.get_xml_attr(metadata_main, 'title'),
                        'parent_title': helpers.get_xml_attr(metadata_main, 'parentTitle'),
                        'grandparent_title': helpers.get_xml_attr(metadata_main, 'grandparentTitle'),
                        'original_title': helpers.get_xml_attr(metadata_main, 'originalTitle'),
                        'sort_title': helpers.get_xml_attr(metadata_main, 'titleSort'),
                        'edition_title': helpers.get_xml_attr(metadata_main, 'editionTitle'),
                        'media_index': helpers.get_xml_attr(metadata_main, 'index'),
                        'parent_media_index': helpers.get_xml_attr(metadata_main, 'parentIndex'),
                        'studio': helpers.get_xml_attr(metadata_main, 'studio'),
                        'content_rating': helpers.get_xml_attr(metadata_main, 'contentRating'),
                        'summary': helpers.get_xml_attr(metadata_main, 'summary'),
                        'tagline': helpers.get_xml_attr(metadata_main, 'tagline'),
                        'rating': helpers.get_xml_attr(metadata_main, 'rating'),
                        'rating_image': helpers.get_xml_attr(metadata_main, 'ratingImage'),
                        'audience_rating': helpers.get_xml_attr(metadata_main, 'audienceRating'),
                        'audience_rating_image': helpers.get_xml_attr(metadata_main, 'audienceRatingImage'),
                        'user_rating': helpers.get_xml_attr(metadata_main, 'userRating'),
                        'duration': helpers.get_xml_attr(metadata_main, 'duration'),
                        'year': album_details.get('year', ''),
                        'parent_year': helpers.get_xml_attr(metadata_main, 'parentYear'),
                        'grandparent_year': helpers.get_xml_attr(metadata_main, 'grandparentYear'),
                        'thumb': helpers.get_xml_attr(metadata_main, 'thumb'),
                        'parent_thumb': helpers.get_xml_attr(metadata_main, 'parentThumb'),
                        'grandparent_thumb': helpers.get_xml_attr(metadata_main, 'grandparentThumb'),
                        'art': helpers.get_xml_attr(metadata_main, 'art'),
                        'banner': album_details.get('banner', ''),
                        'originally_available_at': helpers.get_xml_attr(metadata_main, 'originallyAvailableAt'),
                        'added_at': helpers.get_xml_attr(metadata_main, 'addedAt'),
                        'updated_at': helpers.get_xml_attr(metadata_main, 'updatedAt'),
                        'last_viewed_at': helpers.get_xml_attr(metadata_main, 'lastViewedAt'),
                        'guid': helpers.get_xml_attr(metadata_main, 'guid'),
                        'parent_guid': helpers.get_xml_attr(metadata_main, 'parentGuid'),
                        'grandparent_guid': helpers.get_xml_attr(metadata_main, 'grandparentGuid'),
                        'directors': directors,
                        'writers': writers,
                        'actors': actors,
                        'genres': album_details.get('genres', []),
                        'labels': album_details.get('labels', []),
                        'collections': album_details.get('collections', []),
                        'guids': guids,
                        'parent_guids': album_details.get('guids', []),
                        'grandparent_guids': album_details.get('parent_guids', []),
                        'full_title': '{} - {}'.format(helpers.get_xml_attr(metadata_main, 'title'),
                                                       track_artist),
                        'children_count': helpers.cast_to_int(helpers.get_xml_attr(metadata_main, 'leafCount')),
                        'live': int(helpers.get_xml_attr(metadata_main, 'live') == '1')
                        }

        elif metadata_type == 'photo_album':
            metadata = {'media_type': metadata_type,
                        'section_id': section_id,
                        'library_name': library_name,
                        'rating_key': helpers.get_xml_attr(metadata_main, 'ratingKey'),
                        'parent_rating_key': helpers.get_xml_attr(metadata_main, 'parentRatingKey'),
                        'grandparent_rating_key': helpers.get_xml_attr(metadata_main, 'grandparentRatingKey'),
                        'title': helpers.get_xml_attr(metadata_main, 'title'),
                        'parent_title': helpers.get_xml_attr(metadata_main, 'parentTitle'),
                        'grandparent_title': helpers.get_xml_attr(metadata_main, 'grandparentTitle'),
                        'original_title': helpers.get_xml_attr(metadata_main, 'originalTitle'),
                        'sort_title': helpers.get_xml_attr(metadata_main, 'titleSort'),
                        'edition_title': helpers.get_xml_attr(metadata_main, 'editionTitle'),
                        'media_index': helpers.get_xml_attr(metadata_main, 'index'),
                        'parent_media_index': helpers.get_xml_attr(metadata_main, 'parentIndex'),
                        'studio': helpers.get_xml_attr(metadata_main, 'studio'),
                        'content_rating': helpers.get_xml_attr(metadata_main, 'contentRating'),
                        'summary': helpers.get_xml_attr(metadata_main, 'summary'),
                        'tagline': helpers.get_xml_attr(metadata_main, 'tagline'),
                        'rating': helpers.get_xml_attr(metadata_main, 'rating'),
                        'rating_image': helpers.get_xml_attr(metadata_main, 'ratingImage'),
                        'audience_rating': helpers.get_xml_attr(metadata_main, 'audienceRating'),
                        'audience_rating_image': helpers.get_xml_attr(metadata_main, 'audienceRatingImage'),
                        'user_rating': helpers.get_xml_attr(metadata_main, 'userRating'),
                        'duration': helpers.get_xml_attr(metadata_main, 'duration'),
                        'year': helpers.get_xml_attr(metadata_main, 'year'),
                        'parent_year': helpers.get_xml_attr(metadata_main, 'parentYear'),
                        'grandparent_year': helpers.get_xml_attr(metadata_main, 'grandparentYear'),
                        'thumb': helpers.get_xml_attr(metadata_main, 'thumb'),
                        'parent_thumb': helpers.get_xml_attr(metadata_main, 'parentThumb'),
                        'grandparent_thumb': helpers.get_xml_attr(metadata_main, 'grandparentThumb'),
                        'art': helpers.get_xml_attr(metadata_main, 'art'),
                        'banner': helpers.get_xml_attr(metadata_main, 'banner'),
                        'originally_available_at': helpers.get_xml_attr(metadata_main, 'originallyAvailableAt'),
                        'added_at': helpers.get_xml_attr(metadata_main, 'addedAt'),
                        'updated_at': helpers.get_xml_attr(metadata_main, 'updatedAt'),
                        'last_viewed_at': helpers.get_xml_attr(metadata_main, 'lastViewedAt'),
                        'guid': helpers.get_xml_attr(metadata_main, 'guid'),
                        'parent_guid': helpers.get_xml_attr(metadata_main, 'parentGuid'),
                        'grandparent_guid': helpers.get_xml_attr(metadata_main, 'grandparentGuid'),
                        'directors': directors,
                        'writers': writers,
                        'actors': actors,
                        'genres': genres,
                        'labels': labels,
                        'collections': collections,
                        'guids': guids,
                        'parent_guids': [],
                        'grandparent_guids': [],
                        'full_title': helpers.get_xml_attr(metadata_main, 'title'),
                        'children_count': helpers.cast_to_int(helpers.get_xml_attr(metadata_main, 'leafCount')),
                        'live': int(helpers.get_xml_attr(metadata_main, 'live') == '1')
                        }

        elif metadata_type == 'photo':
            parent_rating_key = helpers.get_xml_attr(metadata_main, 'parentRatingKey')
            photo_album_details = self.get_metadata_details(parent_rating_key) if parent_rating_key else {}
            metadata = {'media_type': metadata_type,
                        'section_id': section_id,
                        'library_name': library_name,
                        'rating_key': helpers.get_xml_attr(metadata_main, 'ratingKey'),
                        'parent_rating_key': helpers.get_xml_attr(metadata_main, 'parentRatingKey'),
                        'grandparent_rating_key': helpers.get_xml_attr(metadata_main, 'grandparentRatingKey'),
                        'title': helpers.get_xml_attr(metadata_main, 'title'),
                        'parent_title': helpers.get_xml_attr(metadata_main, 'parentTitle'),
                        'grandparent_title': helpers.get_xml_attr(metadata_main, 'grandparentTitle'),
                        'original_title': helpers.get_xml_attr(metadata_main, 'originalTitle'),
                        'sort_title': helpers.get_xml_attr(metadata_main, 'titleSort'),
                        'edition_title': helpers.get_xml_attr(metadata_main, 'editionTitle'),
                        'media_index': helpers.get_xml_attr(metadata_main, 'index'),
                        'parent_media_index': helpers.get_xml_attr(metadata_main, 'parentIndex'),
                        'studio': helpers.get_xml_attr(metadata_main, 'studio'),
                        'content_rating': helpers.get_xml_attr(metadata_main, 'contentRating'),
                        'summary': helpers.get_xml_attr(metadata_main, 'summary'),
                        'tagline': helpers.get_xml_attr(metadata_main, 'tagline'),
                        'rating': helpers.get_xml_attr(metadata_main, 'rating'),
                        'rating_image': helpers.get_xml_attr(metadata_main, 'ratingImage'),
                        'audience_rating': helpers.get_xml_attr(metadata_main, 'audienceRating'),
                        'audience_rating_image': helpers.get_xml_attr(metadata_main, 'audienceRatingImage'),
                        'user_rating': helpers.get_xml_attr(metadata_main, 'userRating'),
                        'duration': helpers.get_xml_attr(metadata_main, 'duration'),
                        'year': helpers.get_xml_attr(metadata_main, 'year'),
                        'parent_year': helpers.get_xml_attr(metadata_main, 'parentYear'),
                        'grandparent_year': helpers.get_xml_attr(metadata_main, 'grandparentYear'),
                        'thumb': helpers.get_xml_attr(metadata_main, 'thumb'),
                        'parent_thumb': helpers.get_xml_attr(metadata_main, 'parentThumb'),
                        'grandparent_thumb': helpers.get_xml_attr(metadata_main, 'grandparentThumb'),
                        'art': helpers.get_xml_attr(metadata_main, 'art'),
                        'banner': photo_album_details.get('banner', ''),
                        'originally_available_at': helpers.get_xml_attr(metadata_main, 'originallyAvailableAt'),
                        'added_at': helpers.get_xml_attr(metadata_main, 'addedAt'),
                        'updated_at': helpers.get_xml_attr(metadata_main, 'updatedAt'),
                        'last_viewed_at': helpers.get_xml_attr(metadata_main, 'lastViewedAt'),
                        'guid': helpers.get_xml_attr(metadata_main, 'guid'),
                        'parent_guid': helpers.get_xml_attr(metadata_main, 'parentGuid'),
                        'grandparent_guid': helpers.get_xml_attr(metadata_main, 'grandparentGuid'),
                        'directors': directors,
                        'writers': writers,
                        'actors': actors,
                        'genres': photo_album_details.get('genres', []),
                        'labels': photo_album_details.get('labels', []),
                        'collections': photo_album_details.get('collections', []),
                        'guids': [],
                        'parent_guids': photo_album_details.get('guids', []),
                        'grandparent_guids': [],
                        'full_title': '{} - {}'.format(
                            helpers.get_xml_attr(metadata_main, 'parentTitle') or library_name,
                            helpers.get_xml_attr(metadata_main, 'title')),
                        'children_count': helpers.cast_to_int(helpers.get_xml_attr(metadata_main, 'leafCount')),
                        'live': int(helpers.get_xml_attr(metadata_main, 'live') == '1')
                        }

        elif metadata_type == 'collection':
            metadata = {'media_type': metadata_type,
                        'sub_media_type': helpers.get_xml_attr(metadata_main, 'subtype'),
                        'section_id': section_id,
                        'library_name': library_name,
                        'rating_key': helpers.get_xml_attr(metadata_main, 'ratingKey'),
                        'parent_rating_key': helpers.get_xml_attr(metadata_main, 'parentRatingKey'),
                        'grandparent_rating_key': helpers.get_xml_attr(metadata_main, 'grandparentRatingKey'),
                        'title': helpers.get_xml_attr(metadata_main, 'title'),
                        'parent_title': helpers.get_xml_attr(metadata_main, 'parentTitle'),
                        'grandparent_title': helpers.get_xml_attr(metadata_main, 'grandparentTitle'),
                        'original_title': helpers.get_xml_attr(metadata_main, 'originalTitle'),
                        'sort_title': helpers.get_xml_attr(metadata_main, 'titleSort'),
                        'edition_title': helpers.get_xml_attr(metadata_main, 'editionTitle'),
                        'media_index': helpers.get_xml_attr(metadata_main, 'index'),
                        'parent_media_index': helpers.get_xml_attr(metadata_main, 'parentIndex'),
                        'studio': helpers.get_xml_attr(metadata_main, 'studio'),
                        'content_rating': helpers.get_xml_attr(metadata_main, 'contentRating'),
                        'summary': helpers.get_xml_attr(metadata_main, 'summary'),
                        'tagline': helpers.get_xml_attr(metadata_main, 'tagline'),
                        'rating': helpers.get_xml_attr(metadata_main, 'rating'),
                        'rating_image': helpers.get_xml_attr(metadata_main, 'ratingImage'),
                        'audience_rating': helpers.get_xml_attr(metadata_main, 'audienceRating'),
                        'audience_rating_image': helpers.get_xml_attr(metadata_main, 'audienceRatingImage'),
                        'user_rating': helpers.get_xml_attr(metadata_main, 'userRating'),
                        'duration': helpers.get_xml_attr(metadata_main, 'duration'),
                        'year': helpers.get_xml_attr(metadata_main, 'year'),
                        'parent_year': helpers.get_xml_attr(metadata_main, 'parentYear'),
                        'grandparent_year': helpers.get_xml_attr(metadata_main, 'grandparentYear'),
                        'min_year': helpers.get_xml_attr(metadata_main, 'minYear'),
                        'max_year': helpers.get_xml_attr(metadata_main, 'maxYear'),
                        'thumb': helpers.get_xml_attr(metadata_main, 'thumb').split('?')[0],
                        'parent_thumb': helpers.get_xml_attr(metadata_main, 'parentThumb'),
                        'grandparent_thumb': helpers.get_xml_attr(metadata_main, 'grandparentThumb'),
                        'art': helpers.get_xml_attr(metadata_main, 'art'),
                        'banner': helpers.get_xml_attr(metadata_main, 'banner'),
                        'originally_available_at': helpers.get_xml_attr(metadata_main, 'originallyAvailableAt'),
                        'added_at': helpers.get_xml_attr(metadata_main, 'addedAt'),
                        'updated_at': helpers.get_xml_attr(metadata_main, 'updatedAt'),
                        'last_viewed_at': helpers.get_xml_attr(metadata_main, 'lastViewedAt'),
                        'guid': helpers.get_xml_attr(metadata_main, 'guid'),
                        'parent_guid': helpers.get_xml_attr(metadata_main, 'parentGuid'),
                        'grandparent_guid': helpers.get_xml_attr(metadata_main, 'grandparentGuid'),
                        'child_count': helpers.get_xml_attr(metadata_main, 'childCount'),
                        'directors': directors,
                        'writers': writers,
                        'actors': actors,
                        'genres': genres,
                        'labels': labels,
                        'collections': collections,
                        'guids': guids,
                        'parent_guids': [],
                        'grandparent_guids': [],
                        'full_title': helpers.get_xml_attr(metadata_main, 'title'),
                        'children_count': helpers.cast_to_int(helpers.get_xml_attr(metadata_main, 'childCount')),
                        'live': int(helpers.get_xml_attr(metadata_main, 'live') == '1'),
                        'smart': helpers.cast_to_int(helpers.get_xml_attr(metadata_main, 'smart'))
                        }

        elif metadata_type == 'playlist':
            metadata = {'media_type': metadata_type,
                        'section_id': section_id,
                        'library_name': library_name,
                        'rating_key': helpers.get_xml_attr(metadata_main, 'ratingKey'),
                        'guid': helpers.get_xml_attr(metadata_main, 'guid'),
                        'title': helpers.get_xml_attr(metadata_main, 'title'),
                        'summary': helpers.get_xml_attr(metadata_main, 'summary'),
                        'duration': helpers.get_xml_attr(metadata_main, 'duration'),
                        'composite': helpers.get_xml_attr(metadata_main, 'composite'),
                        'thumb': helpers.get_xml_attr(metadata_main, 'composite'),
                        'added_at': helpers.get_xml_attr(metadata_main, 'addedAt'),
                        'updated_at': helpers.get_xml_attr(metadata_main, 'updatedAt'),
                        'last_viewed_at': helpers.get_xml_attr(metadata_main, 'lastViewedAt'),
                        'children_count': helpers.cast_to_int(helpers.get_xml_attr(metadata_main, 'leafCount')),
                        'smart': helpers.cast_to_int(helpers.get_xml_attr(metadata_main, 'smart')),
                        'playlist_type': helpers.get_xml_attr(metadata_main, 'playlistType'),
                        'live': int(helpers.get_xml_attr(metadata_main, 'live') == '1')
                        }

        elif metadata_type == 'clip':
            metadata = {'media_type': metadata_type,
                        'section_id': section_id,
                        'library_name': library_name,
                        'rating_key': helpers.get_xml_attr(metadata_main, 'ratingKey'),
                        'parent_rating_key': helpers.get_xml_attr(metadata_main, 'parentRatingKey'),
                        'grandparent_rating_key': helpers.get_xml_attr(metadata_main, 'grandparentRatingKey'),
                        'title': helpers.get_xml_attr(metadata_main, 'title'),
                        'parent_title': helpers.get_xml_attr(metadata_main, 'parentTitle'),
                        'grandparent_title': helpers.get_xml_attr(metadata_main, 'grandparentTitle'),
                        'original_title': helpers.get_xml_attr(metadata_main, 'originalTitle'),
                        'sort_title': helpers.get_xml_attr(metadata_main, 'titleSort'),
                        'edition_title': helpers.get_xml_attr(metadata_main, 'editionTitle'),
                        'media_index': helpers.get_xml_attr(metadata_main, 'index'),
                        'parent_media_index': helpers.get_xml_attr(metadata_main, 'parentIndex'),
                        'studio': helpers.get_xml_attr(metadata_main, 'studio'),
                        'content_rating': helpers.get_xml_attr(metadata_main, 'contentRating'),
                        'summary': helpers.get_xml_attr(metadata_main, 'summary'),
                        'tagline': helpers.get_xml_attr(metadata_main, 'tagline'),
                        'rating': helpers.get_xml_attr(metadata_main, 'rating'),
                        'rating_image': helpers.get_xml_attr(metadata_main, 'ratingImage'),
                        'audience_rating': helpers.get_xml_attr(metadata_main, 'audienceRating'),
                        'audience_rating_image': helpers.get_xml_attr(metadata_main, 'audienceRatingImage'),
                        'user_rating': helpers.get_xml_attr(metadata_main, 'userRating'),
                        'duration': helpers.get_xml_attr(metadata_main, 'duration'),
                        'year': helpers.get_xml_attr(metadata_main, 'year'),
                        'parent_year': helpers.get_xml_attr(metadata_main, 'parentYear'),
                        'thumb': helpers.get_xml_attr(metadata_main, 'thumb'),
                        'parent_thumb': helpers.get_xml_attr(metadata_main, 'parentThumb'),
                        'grandparent_thumb': helpers.get_xml_attr(metadata_main, 'grandparentThumb'),
                        'art': helpers.get_xml_attr(metadata_main, 'art'),
                        'banner': helpers.get_xml_attr(metadata_main, 'banner'),
                        'originally_available_at': helpers.get_xml_attr(metadata_main, 'originallyAvailableAt'),
                        'added_at': helpers.get_xml_attr(metadata_main, 'addedAt'),
                        'updated_at': helpers.get_xml_attr(metadata_main, 'updatedAt'),
                        'last_viewed_at': helpers.get_xml_attr(metadata_main, 'lastViewedAt'),
                        'guid': helpers.get_xml_attr(metadata_main, 'guid'),
                        'parent_guid': helpers.get_xml_attr(metadata_main, 'parentGuid'),
                        'grandparent_guid': helpers.get_xml_attr(metadata_main, 'grandparentGuid'),
                        'directors': directors,
                        'writers': writers,
                        'actors': actors,
                        'genres': genres,
                        'labels': labels,
                        'collections': collections,
                        'guids': guids,
                        'parent_guids': [],
                        'grandparent_guids': [],
                        'full_title': helpers.get_xml_attr(metadata_main, 'title'),
                        'extra_type': helpers.get_xml_attr(metadata_main, 'extraType'),
                        'sub_type': helpers.get_xml_attr(metadata_main, 'subtype'),
                        'live': int(helpers.get_xml_attr(metadata_main, 'live') == '1')
                        }

        else:
            return metadata

        # Get additional metadata from metadata.provider.plex.tv
        if not plex_guid and metadata['live']:
            metadata['section_id'] = common.LIVE_TV_SECTION_ID
            metadata['library_name'] = common.LIVE_TV_SECTION_NAME

            plextv_metadata = self.get_metadata_details(plex_guid=metadata['guid'])
            if plextv_metadata:
                keys_to_update = ['summary', 'rating', 'thumb', 'grandparent_thumb', 'duration',
                                  'guid', 'grandparent_guid', 'genres']
                for key in keys_to_update:
                    metadata[key] = plextv_metadata[key]
                metadata['originally_available_at'] = helpers.iso_to_YMD(plextv_metadata['originally_available_at'])

        if metadata and media_info:
            medias = []
            streams = []
            parts = []
            stream_ = {}
            result_ = self.get_media_details(xml_head["Id"], output_format="json")

            try:
                media_stream = result_["MediaSources"][0]["MediaStreams"]
                resolution = f"{result_['Height']}x{result_['Width']}"
                container = result_["MediaSources"][0]["Container"].upper()
                file = result_["MediaSources"][0]["Path"]
                file_size = result_["MediaSources"][0]["Size"]
                for stream in media_stream:
                    try:
                        if stream["Type"] == "Audio":
                            audio_codec = stream["Codec"]
                            audio_channels = stream["Channels"]
                            audio_profile = stream["Profile"]
                        if stream["Type"] == "Video":
                            video_codec = stream["Codec"]
                            framerate = stream["RealFrameRate"]
                            bitrate = stream["BitRate"]
                            color_primaries = stream["ColorPrimaries"]
                            streamType = stream["Type"]
                            bitDepth = stream["BitDepth"]
                            level = stream["Level"]
                            video_profile = stream["Profile"]
                            color_space = stream["ColorSpace"]
                            ref_frames = stream["RefFrames"]
                            aspect_ratio = stream["AspectRatio"]
                    except KeyError:
                        container = ""
                        bitrate = ""
                        video_codec = ""
                        resolution = ""
                        framerate = ""
                        audio_codec = ""
                        audio_channels = ""
                        file = ""
                        file_size = ""
                        color_primaries = ""
                        streamType = ""
                        bitDepth = ""
                        level = ""
                        video_profile = ""
                        color_space = ""
                        ref_frames = ""
                        aspect_ratio = ""
                        audio_profile = ""
                        continue
            except KeyError as e:
                container = ""
                bitrate = ""
                video_codec = ""
                resolution = ""
                framerate = ""
                audio_codec = ""
                audio_channels = ""
                file = ""
                file_size = ""
                color_primaries = ""
                streamType = ""
                bitDepth = ""
                level = ""
                video_profile = ""
                color_space = ""
                ref_frames = ""
                aspect_ratio = ""
                audio_profile = ""

            streams.append(
                {
                    'id': helpers.get_json_attr(stream_, 'id'),
                    'type': streamType,
                    'video_codec': video_codec,
                    'video_codec_level': level,
                    'video_bitrate': bitrate,
                    'video_bit_depth': bitDepth,
                    'video_chroma_subsampling': helpers.get_json_attr(stream_, 'chromaSubsampling'),
                    'video_color_primaries': color_primaries,
                    'video_color_range': helpers.get_json_attr(stream_, 'colorRange'),
                    'video_color_space': color_space,
                    'video_color_trc': helpers.get_json_attr(stream_, 'colorTrc'),
                    # 'video_dynamic_range': self.get_dynamic_range(stream),
                    'video_frame_rate': framerate,
                    'video_ref_frames': ref_frames,
                    'video_height': helpers.get_json_attr(stream_, 'Height'),
                    'video_width': helpers.get_json_attr(stream_, 'Width'),
                    'video_language': helpers.get_json_attr(stream_, 'language'),
                    'video_language_code': helpers.get_json_attr(stream_, 'languageCode'),
                    'video_profile': video_profile,
                    'video_scan_type': helpers.get_json_attr(stream_, 'scanType')
                }
            )

            media_info = {
                'id': helpers.get_json_attr(result_, 'id'),
                'container': container,
                'bitrate': bitrate,
                'height': helpers.get_json_attr(stream_, 'Height'),
                'width': helpers.get_json_attr(stream_, 'Width'),
                'aspect_ratio': aspect_ratio,
                'video_codec': video_codec,
                'video_resolution': "1080p",
                'video_full_resolution': "1080p",
                'video_framerate': framerate,
                'video_profile': video_profile,
                'audio_codec': audio_codec,
                'audio_channels': audio_channels,
                'audio_channel_layout': common.AUDIO_CHANNELS.get(audio_channels, audio_channels),
                'audio_profile': audio_profile,
                'optimized_version': int(helpers.get_json_attr(result_, 'proxyType') == '42'),
                'channel_call_sign': helpers.get_json_attr(result_, 'channelCallSign'),
                'channel_identifier': helpers.get_json_attr(result_, 'channelIdentifier'),
                'channel_thumb': helpers.get_json_attr(result_, 'channelThumb'),
                'parts': parts
            }

            medias.append(media_info)

            metadata['media_info'] = medias

        if metadata:
            if cache_key:
                metadata['_cache_time'] = helpers.timestamp()

                out_file_folder = os.path.join(jellypy.CONFIG.CACHE_DIR, 'session_metadata')
                out_file_path = os.path.join(out_file_folder, 'metadata-sessionKey-%s.json' % cache_key)

                if not os.path.exists(out_file_folder):
                    os.mkdir(out_file_folder)

                try:
                    with open(out_file_path, 'w') as outFile:
                        json.dump(metadata, outFile)
                except (IOError, ValueError) as e:
                    logger.error("JellyPy JellyConnect :: Unable to create cache file for metadata (sessionKey %s): %s"
                                 % (cache_key, e))

            return metadata
        else:
            return metadata

    def fetch_movie_library_list_details(self, rating_key='', get_children=False):
        """
        Return processed and validated metadata list for all children of requested item.

        Parameters required:    rating_key { Plex ratingKey }

        Output: array
        """
        metadata = self.fetch_movie_library_list(str(rating_key), output_format='json')

        try:
            xml_head = metadata.getElementsByTagName('MediaContainer')
        except Exception as e:
            logger.warn("JellyPy JellyConnect :: Unable to parse JSON for fetch_movie_library_list: %s." % e)
            return []

        metadata_list = []

        for a in xml_head:
            if a.getAttribute('size'):
                if a.getAttribute('size') == '0':
                    return metadata_list

            if a.getElementsByTagName('Video'):
                metadata_main = a.getElementsByTagName('Video')
                for item in metadata_main:
                    child_rating_key = helpers.get_xml_attr(item, 'ratingKey')
                    metadata = self.get_metadata_details(str(child_rating_key))
                    if metadata:
                        metadata_list.append(metadata)

            elif a.getElementsByTagName('Track'):
                metadata_main = a.getElementsByTagName('Track')
                for item in metadata_main:
                    child_rating_key = helpers.get_xml_attr(item, 'ratingKey')
                    metadata = self.get_metadata_details(str(child_rating_key))
                    if metadata:
                        metadata_list.append(metadata)

            elif get_children and a.getElementsByTagName('Directory'):
                dir_main = a.getElementsByTagName('Directory')
                metadata_main = [d for d in dir_main if helpers.get_xml_attr(d, 'ratingKey')]
                for item in metadata_main:
                    child_rating_key = helpers.get_xml_attr(item, 'ratingKey')
                    metadata = self.fetch_movie_library_list_details(str(child_rating_key), get_children)
                    if metadata:
                        metadata_list.extend(metadata)

        return metadata_list

    def get_library_metadata_details(self, section_id=''):
        """
        Return processed and validated metadata list for requested library.

        Parameters required:    section_id { Plex library key }

        Output: array
        """
        libraries_data = self.get_libraries_list(output_format='json')

        try:
            xml_head = libraries_data.getElementsByTagName('MediaContainer')
        except Exception as e:
            logger.warn("JellyPy JellyConnect :: Unable to parse JSON for get_library_metadata_details: %s." % e)
            return []

        metadata_list = []

        for a in xml_head:
            if a.getAttribute('size'):
                if a.getAttribute('size') == '0':
                    metadata_list = {'metadata': None}
                    return metadata_list

            if a.getElementsByTagName('Directory'):
                result_data = a.getElementsByTagName('Directory')
                for result in result_data:
                    key = helpers.get_xml_attr(result, 'key')
                    if key == section_id:
                        metadata = {
                            'media_type': 'library',
                            'section_id': helpers.get_xml_attr(result, 'key'),
                            'library': helpers.get_xml_attr(result, 'type'),
                            'title': helpers.get_xml_attr(result, 'title'),
                            'art': helpers.get_xml_attr(result, 'art'),
                            'thumb': helpers.get_xml_attr(result, 'thumb')
                        }
                        if metadata['library'] == 'movie':
                            metadata['section_type'] = 'movie'
                        elif metadata['library'] == 'show':
                            metadata['section_type'] = 'episode'
                        elif metadata['library'] == 'artist':
                            metadata['section_type'] = 'track'

            metadata_list = {'metadata': metadata}

        return metadata_list

    def get_current_activity(self, skip_cache=False):
        """
        Return processed and validated session list.

        Output: array
        """
        session_data = self.get_sessions(output_format='json')

        try:
            xml_head = session_data
        except Exception as e:
            logger.warn(f"JellyPy JellyConnect :: Unable to parse JSON for get_current_activity: {e}.")
            return []

        session_list = []
        stream_count = []

        for a in xml_head:
            if "NowPlayingItem" in a:
                session_output = self.get_session_each(a, skip_cache=skip_cache)
                session_list.append(session_output)
                stream_count.append(len(xml_head))

                """if a.getElementsByTagName('Track'):
                    session_data = a.getElementsByTagName('Track')
                    for session_ in session_data:
                        # Filter out background theme music sessions
                        if helpers.get_xml_attr(session_, 'guid').startswith('library://'):
                            continue
                        session_output = self.get_session_each(session_, skip_cache=skip_cache)
                        session_list.append(session_output)
                if a.getElementsByTagName('Photo'):
                    session_data = a.getElementsByTagName('Photo')
                    for session_ in session_data:
                        session_output = self.get_session_each(session_, skip_cache=skip_cache)
                        session_list.append(session_output)"""

        session_list = sorted(session_list, key=lambda k: k['session_key'])

        output = {
            'stream_count': len(stream_count),
            'sessions': session.mask_session_info(session_list)
        }

        return output

    def get_session_each(self, session=None, skip_cache=False):
        """
        Return selected data from current sessions.
        This function processes and validates session data

        Parameters required:    session { the session dictionary }
        Output: dict
        """

        # Get the source media type
        media_type = session["NowPlayingItem"]["Type"].lower()

        # Get the user details
        user_info = session["UserName"]
        user_id = session["UserId"]
        if user_id == '1':
            user_details = users.Users().get_details(user=helpers.get_xml_attr(user_info, 'title'))
        else:
            user_details = users.Users().get_details(user_id=user_id)

        # Get the player details
        player_info = session['DeviceName']

        # Override platform names
        """platform = helpers.get_json_attr(player_info, 'platform')
        platform = common.PLATFORM_NAME_OVERRIDES.get(platform, platform)
        if not platform and helpers.get_xml_attr(player_info, 'product') == 'DLNA':
            platform = 'DLNA'"""

        # platform_name = next((v for k, v in common.PLATFORM_NAMES.items() if k in platform.lower()), 'default')

        player_details = {
            'ip_address': session["RemoteEndPoint"],
            'ip_address_public': session["RemoteEndPoint"],
            'device': session['DeviceName'],
            'product': session["Client"],
            'product_version': session["ApplicationVersion"],
            'player': player_info,
            'machine_id': session["DeviceId"],
            'local': '1',
        }

        # Get the transcode details
        if session["PlayState"]["PlayMethod"] == "Transcode":
            if session["TranscodingInfo"]:
                transcode_progress = session["TranscodingInfo"]["CompletionPercentage"]

                for reason in session["TranscodingInfo"]["TranscodeReasons"]:
                    if "Video" in reason:
                        video_transcode_decision = "transcode"
                    else:
                        video_transcode_decision = "direct play"

                    if "Audio" in reason:
                        audio_transcode_decision = "transcode"
                    else:
                        audio_transcode_decision = "direct play"

                    if "Subtitle" in reason:
                        sub_transcode_decision = "transcode"
                    else:
                        sub_transcode_decision = "direct play"


                transcode_details = {
                    'transcode_progress': int(round(transcode_progress)),
                    'transcode_audio_channels': session["TranscodingInfo"]["AudioChannels"],
                    'transcode_audio_codec': session["TranscodingInfo"]["AudioCodec"],
                    'transcode_video_codec': session["TranscodingInfo"]["VideoCodec"],
                    'transcode_width': session["TranscodingInfo"]["Width"],
                    'transcode_height': session["TranscodingInfo"]["Height"],
                    'transcode_container': session["TranscodingInfo"]["Container"],
                    'audio_decision': audio_transcode_decision,
                    'video_decision': video_transcode_decision,
                    'subtitle_decision': sub_transcode_decision
                }
        else:
            transcode_details = {
                'transcode_progress': 0,
                'transcode_audio_channels': '',
                'transcode_audio_codec': '',
                'transcode_video_codec': '',
                'transcode_width': '',
                'transcode_height': '',
                'transcode_container': '',
                'audio_decision': 'direct play',
                'video_decision': 'direct play',
                'subtitle_decision': ''
            }


        if session["PlayState"]["PlayMethod"] == "Transcode":
            transcode_decision = "transcode"
            stream_bitrate = session["TranscodingInfo"]["Bitrate"]
        else:
            transcode_decision = "direct play"
            stream_bitrate = session["NowPlayingItem"]["MediaStreams"][0]["BitRate"]


        stream_details = {
            'stream_container': session["FullNowPlayingItem"]["Container"],
            'stream_bitrate': stream_bitrate,
            'stream_aspect_ratio': session["NowPlayingItem"]["MediaStreams"][0]["AspectRatio"],
            'stream_video_framerate': session["NowPlayingItem"]["MediaStreams"][0]["RealFrameRate"],
            'stream_video_resolution': "1080p",
            'stream_duration': helpers.convert_ticks(session["NowPlayingItem"]["RunTimeTicks"] * 1000),
            'stream_container_decision': transcode_decision,
            'transcode_decision': transcode_decision
        }

        ancestors = self.get_item_ancestors(session["NowPlayingItem"]["Id"], output_format="json")

        details = self.get_media_details(session["NowPlayingItem"]["Id"], output_format="json")

        directors = []
        writers = []
        actors = []
        genres = []
        labels = []
        studios = []

        for director in details["People"]:
            if director["Role"] == "Director":
                directors.append(director['Name'])

        for writer in details["People"]:
            if writer["Type"] == "Writer":
                writers.append(writer['Name'])

        for actor in details["People"]:
            if actor["Type"] == "Actor":
                actors.append(actor['Name'])

        for genre in details["Genres"]:
            genres.append(genre)

        for studio in details["Studios"]:
            studios.append(studio['Name'])

        media_stream = details["MediaSources"][0]["MediaStreams"]
        container = details["MediaSources"][0]["Container"].upper()
        for stream in media_stream:
            if stream["Type"] == "Audio":
                audio_codec = stream["Codec"]
                audio_channels = stream["Channels"]
                try:
                    audio_profile = stream["Profile"]
                except KeyError:
                    audio_profile = ""
                audio_bitrate = stream["BitRate"]
            if stream["Type"] == "Video":
                video_codec = stream["Codec"]
                framerate = stream["RealFrameRate"]
                bitrate = stream["BitRate"]
                try:
                    color_primaries = stream["ColorPrimaries"]
                    color_space = stream["ColorSpace"]
                except KeyError:
                    color_primaries = ""
                    color_space = ""
                bitDepth = stream["BitDepth"]
                level = stream["Level"]
                video_profile = stream["Profile"]
                ref_frames = stream["RefFrames"]
                aspect_ratio = stream["AspectRatio"]
                video_range = stream["VideoRange"]
            if stream["Type"] == "Subtitle":
                sub_codec = stream["Codec"]
                try:
                    sub_lan = stream["Language"]
                except KeyError:
                    sub_lan = ""
                sub_forced = stream["IsForced"]

        if media_type == "movie":
            backdrop = f"/Items/{session['NowPlayingItem']['Id']}/Images/Backdrop"
        else:
            backdrop = f"/Items/{ancestors[1]['Id']}/Images/Backdrop"

        metadata_details = {
            'media_type': media_type,
            'section_id': ancestors[0]["Id"],
            'library_name': ancestors[0]["Name"],
            'rating_key': session["NowPlayingItem"]["Id"],
            'parent_rating_key': ancestors[0]["Id"],
            'grandparent_rating_key': ancestors[1]["Id"],
            'title': session["NowPlayingItem"]["Name"],
            'parent_title': ancestors[0]["Name"],
            'grandparent_title': ancestors[1]["Name"],
            'original_title': helpers.get_json_attr(session, 'originalTitle'),
            'sort_title': details["SortName"],
            'media_index': helpers.get_json_attr(session["NowPlayingItem"], 'IndexNumber'),
            'parent_media_index': helpers.get_json_attr(session["NowPlayingItem"], 'ParentIndexNumber'),
            'studio': helpers.get_json_attr(session["NowPlayingItem"], 'SeriesStudio'),
            'content_rating': "helpers.get_xml_attr(session, 'contentRating')",
            'summary': session["NowPlayingItem"]["Overview"],
            'tagline': session["NowPlayingItem"]["Taglines"],
            'rating': session["NowPlayingItem"]["CommunityRating"],
            'rating_image': helpers.get_json_attr(session, 'ratingImage'),
            'audience_rating': helpers.get_json_attr(session, 'ratingImage'),
            'audience_rating_image': helpers.get_json_attr(session, 'ratingImage'),
            'user_rating': helpers.get_json_attr(session, 'ratingImage'),
            'duration': helpers.convert_ticks(session["NowPlayingItem"]["RunTimeTicks"] * 1000),
            'year': session["NowPlayingItem"]["ProductionYear"],
            'thumb': f"/Items/{session['NowPlayingItem']['Id']}/Images/Primary",
            'parent_thumb': f"/Items/{ancestors[0]['Id']}/Images/Primary",
            'grandparent_thumb': f"/Items/{ancestors[1]['Id']}/Images/Primary",
            'art': backdrop,
            'banner': f"/Items/{ancestors[1]['Id']}/Images/Banner",
            'originally_available_at': session["NowPlayingItem"]["PremiereDate"],
            'added_at': helpers.datetime_to_unix(session["NowPlayingItem"]["DateCreated"]),
            'updated_at': helpers.datetime_to_unix(session["NowPlayingItem"]["DateCreated"]),
            'last_viewed_at': helpers.get_json_attr(session, 'lastViewedAt'),
            'guid': helpers.get_json_attr(session, 'guid'),
            'directors': directors,
            'writers': writers,
            'actors': actors,
            'genres': genres,
            'labels': labels,
            'full_title': session["NowPlayingItem"]["Name"],
            'container': container,
            'bitrate': bitrate,
            'height': details['Height'],
            'width': details['Width'],
            'aspect_ratio': aspect_ratio,
            'video_codec': video_codec,
            'video_resolution': "1080",
            'video_full_resolution': "1080",
            'video_framerate': framerate,
            'video_profile': video_profile,
            'audio_codec': audio_codec,
            'audio_channels': audio_channels,
            'audio_channel_layout': common.AUDIO_CHANNELS.get(audio_channels, audio_channels),
            'audio_profile': audio_profile,
            'channel_icon': "",
            'channel_title': "",
            'extra_type': "",
            'sub_type': "",
        }

        source_video_details = {
            'video_codec': video_codec,
            'video_codec_level': level,
            'video_bitrate': bitrate,
            'video_bit_depth': bitDepth,
            'video_chroma_subsampling': '',
            'video_color_primaries': color_primaries,
            'video_color_range': video_range,
            'video_color_space': color_space,
            'video_color_trc': '',
            'video_dynamic_range': video_range,
            'video_frame_rate': framerate,
            'video_ref_frames': ref_frames,
            'video_height': details['Height'],
            'video_width': details['Width'],
            'video_language': '',
            'video_language_code': '',
            'video_scan_type': '',
            'video_profile': video_profile,
            'bandwidth': bitrate,
            'live': 0
        }

        if session["PlayState"]["PlayMethod"] == "Transcode":
            stream_video_decision = "transcode"
        else:
            stream_video_decision = "direct play"

        if session["NowPlayingItem"]["Type"] == "TvChannel":
            channel_stream = 1
        else:
            channel_stream = 0

        if session["PlayState"]["IsPaused"]:
            state = "paused"
        else:
            state = "playing"

        video_details = {
            'stream_video_bitrate': bitrate,
            'stream_video_bit_depth': bitDepth,
            'stream_video_chroma_subsampling': '',
            'stream_video_codec': video_codec,
            'stream_video_codec_level': level,
            'stream_video_color_primaries': color_primaries,
            'stream_video_color_range': video_range,
            'stream_video_color_space': color_space,
            'stream_video_color_trc': '',
            'stream_video_dynamic_range': video_range,
            'stream_video_height': details['Height'],
            'stream_video_width': details['Width'],
            'stream_video_ref_frames': ref_frames,
            'stream_video_language': '',
            'stream_video_language_code': '',
            'stream_video_scan_type': '',
            'stream_video_decision': stream_video_decision,
            'stream_video_full_resolution': '1080p',
            'channel_stream': channel_stream,
            'state': state
        }

        source_audio_details = {
            'audio_codec': audio_codec,
            'audio_bitrate': audio_bitrate,
            'audio_bitrate_mode': '',
            'audio_channels': audio_channels,
            'audio_channel_layout': common.AUDIO_CHANNELS.get(audio_channels, audio_channels),
            'audio_sample_rate': '',
            'audio_language': '',
            'audio_language_code': '',
            'audio_profile': ''
        }

        audio_details = {
            'stream_audio_bitrate': audio_bitrate,
            'stream_audio_bitrate_mode': '',
            'stream_audio_channels': audio_channels,
            'stream_audio_channel_layout': audio_channels,
            'stream_audio_codec': audio_codec,
            'stream_audio_sample_rate': '',
            'stream_audio_language': '',
            'stream_audio_language_code': '',
            'stream_audio_decision': 'direct play'
        }

        source_subtitle_details = {
            'subtitle_codec': sub_codec,
            'subtitle_container': '',
            'subtitle_format': '',
            'subtitle_forced': 0 if not sub_forced else 1,
            'subtitle_location': '',
            'subtitle_language': sub_lan,
            'subtitle_language_code': ''
        }

        subtitle_details = {
            'stream_subtitle_codec': sub_codec,
            'stream_subtitle_container': '',
            'stream_subtitle_format': '',
            'stream_subtitle_forced': 0 if not sub_forced else 1,
            'stream_subtitle_location': '',
            'stream_subtitle_language': sub_lan,
            'stream_subtitle_language_code': '',
            'stream_subtitle_decision': 'direct play',
            'stream_subtitle_transient': 0
        }

        for stream in session["NowPlayingItem"]["MediaStreams"]:
            if stream["Type"] == "Video":
                quality_profile = stream["DisplayTitle"]

        view_offset = round(helpers.convert_ticks(session["PlayState"]["PositionTicks"]) * 1000)

        # Entire session output (single dict for backwards compatibility)
        session_output = {
            'session_key': session["Id"],
            'session_id': session["Id"],
            'media_type': media_type,
            'view_offset': view_offset,
            'progress_percent': round((helpers.convert_ticks(session["PlayState"]["PositionTicks"]) / helpers.convert_ticks(session["NowPlayingItem"]["RunTimeTicks"])) * 100),
            'quality_profile': quality_profile,
            'user': user_details['username'],
        }

        session_output.update(metadata_details)
        session_output.update(source_video_details)
        session_output.update(source_audio_details)
        session_output.update(source_subtitle_details)
        session_output.update(user_details)
        session_output.update(player_details)
        session_output.update(transcode_details)
        session_output.update(stream_details)
        session_output.update(video_details)
        session_output.update(audio_details)
        session_output.update(subtitle_details)

        return session_output

    def terminate_session(self, session_key='', session_id='', message=''):
        """Terminates a streaming session."""

        message = message.encode('utf-8') or 'The server owner has ended the stream.'

        ap = activity_processor.ActivityProcessor()

        if session_key:
            session = ap.get_session_by_key(session_key=session_key)
            if session and not session_id:
                session_id = session['session_id']

        elif session_id:
            session = ap.get_session_by_id(session_id=session_id)
            if session and not session_key:
                session_key = session['session_key']
        else:
            session = session_key = session_id = None

        if not session:
            msg = f'Invalid session_key ({session_key}) or session_id ({session_id})'
            logger.warn(f"JellyPy JellyConnect :: Failed to terminate session: {msg}.")
            return msg

        if session_id:
            logger.info(f"JellyPy JellyConnect :: Terminating session {session_key} (session_id {session_id}).")
            response = self.get_sessions_terminate(session_id=session_id, reason=message)
            return response.ok
        else:
            msg = 'Missing session_id'
            logger.warn(f"JellyPy JellyConnect :: Failed to terminate session: {msg}.")
            return msg

    def get_item_children(self, rating_key="", media_type="", get_grandchildren=False):
        """
        Return processed and validated children list.

        Output: array
        """
        default_return = {
            'children_count': 0,
            'children_list': []
        }

        xml_head = []

        if media_type == 'playlist':
            children_data = self.get_playlist_items(rating_key, output_format='json')
        elif media_type == 'collection':
            children_data = self.fetch_movie_library_list(rating_key, collection=True, output_format='json')
        elif get_grandchildren:
            children_data = self.get_metadata_grandchildren(rating_key, output_format='json')
        elif media_type == 'artist':
            artist_metadata = self.get_metadata_details(rating_key)
            section_id = artist_metadata['section_id']
            sort_type = f'&artist.id={rating_key}&type=9'
            children_data = self.fetch_music_library_list(section_id=str(section_id), sort_type=sort_type,
                                                          output_format='json')
        elif media_type == "show":
            children_data = self.get_library_recently_added_seasons(series_id=str(rating_key), output_format="json")
        else:
            children_data = self.fetch_movie_library_list(rating_key, output_format='json')

        if not xml_head:
            try:
                xml_head = children_data
            except Exception as e:
                logger.warn("JellyPy JellyConnect :: Unable to parse JSON for get_item_children: %s." % e)
                return default_return

        children_list = []

        for a in xml_head:
            result_data = []

            if len(xml_head) == 0:
                logger.debug("JellyPy JellyConnect :: No children data.")
                return default_return

            if a["Type"] == "Movie":
                result_data.append(a)
            elif a["Type"] == "Episode":
                result_data.append(a)
            elif a["Type"] == "Series":
                result_data.append(a)
            elif a["Type"] == "Season":
                result_data.append(a)

            if result_data:
                for m in result_data:
                    media_type = m["Type"].lower()
                    item_id = m["Id"]
                    directors = []
                    writers = []
                    actors = []
                    genres = []
                    labels = []
                    collections = []
                    studios = []

                    details = self.get_media_details(item_id, output_format="json")

                    if m["Type"] == "Episode":
                        ancestors = self.get_item_ancestors(m["Id"], output_format="json")
                    else:
                        ancestors = self.get_item_ancestors(item_id, output_format="json")

                    for director in details["People"]:
                        if director["Role"] == "Director":
                            directors.append(director['Name'])

                    for writer in details["People"]:
                        if writer["Type"] == "Writer":
                            writers.append(writer['Name'])

                    for actor in details["People"]:
                        if actor["Type"] == "Actor":
                            actors.append(actor['Name'])

                    for genre in details["Genres"]:
                        genres.append(genre)

                    for studio in details["Studios"]:
                        studios.append(studio['Name'])

                    """if m.getElementsByTagName('Label'):
                        for label in m.getElementsByTagName('Label'):
                            labels.append(helpers.get_xml_attr(label, 'tag'))

                    if m.getElementsByTagName('Collection'):
                        for collection in m.getElementsByTagName('Collection'):
                            collections.append(helpers.get_xml_attr(collection, 'tag'))"""

                    if media_type == 'photo':
                        media_type = 'photo_album'

                    children_output = {
                        'media_type': media_type,
                        'section_id': rating_key,
                        'library_name': ancestors[0]["Name"],
                        'rating_key': helpers.get_json_attr(m, 'Id'),
                        'parent_rating_key': ancestors[0]["Id"],
                        'grandparent_rating_key': ancestors[1]["Id"],
                        'title': helpers.get_json_attr(m, 'Name'),
                        'parent_title': ancestors[0]["Name"],
                        'grandparent_title': ancestors[1]["Name"],
                        'sort_title': details["SortName"],
                        'media_index': helpers.get_json_attr(m, 'IndexNumber'),
                        'parent_media_index': helpers.get_json_attr(m, 'ParentIndexNumber'),
                        'studio': ", ".join(studios),
                        'content_rating': helpers.get_json_attr(m, 'OfficialRating'),
                        'summary': helpers.get_json_attr(m, 'Overview'),
                        'tagline': ", ".join(details["Taglines"]),
                        'rating': helpers.get_json_attr(m, 'CommunityRating'),
                        'rating_image': helpers.get_json_attr(m, 'ratingImage'),
                        'audience_rating': helpers.get_json_attr(m, 'audienceRating'),
                        'audience_rating_image': helpers.get_json_attr(m, 'audienceRatingImage'),
                        'user_rating': helpers.get_json_attr(m, 'userRating'),
                        'duration': helpers.get_json_attr(m, 'RunTimeTicks'),
                        'year': helpers.get_json_attr(m, 'ProductionYear'),
                        'thumb': f"/Items/{helpers.get_json_attr(m, 'Id')}/Images/Primary",
                        'parent_thumb': f"/Items/{ancestors[0]['Id']}/Images/Primary",
                        'grandparent_thumb': f"/Items/{ancestors[1]['Id']}/Images/Primary",
                        'art': f"/Items/{helpers.get_json_attr(m, 'Id')}/Images/Art",
                        'banner': f"/Items/{helpers.get_json_attr(m, 'Id')}/Images/Banner",
                        'originally_available_at': helpers.get_json_attr(m, 'PremiereDate'),
                        'added_at': helpers.datetime_to_unix(details["DateCreated"]),
                        'updated_at': helpers.datetime_to_unix(details["DateCreated"]),
                        'last_viewed_at': helpers.get_json_attr(m, 'lastViewedAt'),
                        'guid': helpers.get_json_attr(m, 'guid'),
                        'directors': ", ".join(directors),
                        'writers': ", ".join(writers),
                        'actors': ", ".join(actors),
                        'genres': ", ".join(genres),
                        'labels': ", ".join(labels),
                        'collections': collections,
                        'full_title': helpers.get_json_attr(m, 'Name'),
                    }

                    try:
                        if details["OriginalTitle"]:
                            children_output["original_title"] = details["OriginalTitle"]
                    except KeyError:
                        pass

                    children_list.append(children_output)

        output = {
            'children_count': len(xml_head),
            'children_type': helpers.get_json_attr(a, 'viewGroup'),
            'title': a["Name"],
            'children_list': children_list
        }

        return output

    def get_item_children_related(self, rating_key=''):
        """
        Return processed and validated children list.

        Output: array
        """
        children_data = self.get_children_list_related(rating_key, output_format='xml')

        try:
            xml_head = children_data.getElementsByTagName('MediaContainer')
        except Exception as e:
            logger.warn("JellyPy JellyConnect :: Unable to parse JSON for get_item_children_related: %s." % e)
            return []

        children_results_list = {'movie': [],
                                 'show': [],
                                 'season': [],
                                 'episode': [],
                                 'artist': [],
                                 'album': [],
                                 'track': [],
                                 }

        for a in xml_head:
            section_id = helpers.get_xml_attr(a, 'librarySectionID')
            hubs = a.getElementsByTagName('Hub')

            for h in hubs:
                size = helpers.get_xml_attr(h, 'size')
                media_type = helpers.get_xml_attr(h, 'type')
                title = helpers.get_xml_attr(h, 'title')
                hub_identifier = helpers.get_xml_attr(h, 'hubIdentifier')

                if size == '0' or not hub_identifier.startswith('collection.related') or \
                        media_type not in children_results_list:
                    continue

                result_data = []

                if h.getElementsByTagName('Video'):
                    result_data = h.getElementsByTagName('Video')
                if h.getElementsByTagName('Directory'):
                    result_data = h.getElementsByTagName('Directory')
                if h.getElementsByTagName('Track'):
                    result_data = h.getElementsByTagName('Track')

                for result in result_data:
                    children_output = {'section_id': section_id,
                                       'rating_key': helpers.get_xml_attr(result, 'ratingKey'),
                                       'parent_rating_key': helpers.get_xml_attr(result, 'parentRatingKey'),
                                       'media_index': helpers.get_xml_attr(result, 'index'),
                                       'title': helpers.get_xml_attr(result, 'title'),
                                       'parent_title': helpers.get_xml_attr(result, 'parentTitle'),
                                       'year': helpers.get_xml_attr(result, 'year'),
                                       'thumb': helpers.get_xml_attr(result, 'thumb'),
                                       'parent_thumb': helpers.get_xml_attr(a, 'thumb'),
                                       'duration': helpers.get_xml_attr(result, 'duration')
                                       }
                    children_results_list[media_type].append(children_output)

            output = {'results_count': sum(len(v) for k, v in children_results_list.items()),
                      'results_list': children_results_list,
                      }

            return output

    def get_servers_info(self):
        """
        Return the list of local servers.

        Output: array
        """
        recent = self.get_server_list(output_format='xml')

        try:
            xml_head = recent.getElementsByTagName('Server')
        except Exception as e:
            logger.warn("JellyPy JellyConnect :: Unable to parse JSON for get_server_list: %s." % e)
            return []

        server_info = []
        for a in xml_head:
            output = {"name": helpers.get_xml_attr(a, 'name'),
                      "machine_identifier": helpers.get_xml_attr(a, 'machineIdentifier'),
                      "host": helpers.get_xml_attr(a, 'host'),
                      "port": helpers.get_xml_attr(a, 'port'),
                      "version": helpers.get_xml_attr(a, 'version')
                      }

            server_info.append(output)

        return server_info

    def get_server_identity(self):
        """
        Return the local machine identity.

        Output: dict
        """
        identity = self.get_local_server_identity(output_format='xml')

        try:
            xml_head = identity.getElementsByTagName('MediaContainer')
        except Exception as e:
            logger.warn("JellyPy JellyConnect :: Unable to parse JSON for get_local_server_identity: %s." % e)
            return {}

        server_identity = {}
        for a in xml_head:
            server_identity = {"machine_identifier": helpers.get_xml_attr(a, 'machineIdentifier'),
                               "version": helpers.get_xml_attr(a, 'version')
                               }

        return server_identity

    def get_server_pref(self, pref=None):
        """
        Return a specified server preference.

        Parameters required:    pref { name of preference }

        Output: string
        """
        if pref:
            prefs = self.get_server_prefs(output_format='json')

            try:
                xml_head = prefs.getElementsByTagName('Setting')
            except Exception as e:
                logger.warn("JellyPy JellyConnect :: Unable to parse JSON for get_local_server_name: %s." % e)
                return ''

            pref_value = 'None'
            for a in xml_head:
                if helpers.get_xml_attr(a, 'id') == pref:
                    pref_value = helpers.get_xml_attr(a, 'value')
                    break

            return pref_value
        else:
            logger.debug("JellyPy JellyConnect :: Server preferences queried but no parameter received.")
            return None

    def get_server_children(self):
        """
        Return processed and validated server libraries list.

        Output: array
        """
        libraries_data = self.get_libraries_list(output_format='json')

        try:
            xml_head = libraries_data
        except Exception as e:
            logger.warn("JellyPy JellyConnect :: Unable to parse JSON for get_libraries_list: %s." % e)
            return []

        libraries_list = []

        for a in xml_head:
            if not a['LibraryOptions']['PathInfos']:
                logger.debug("JellyPy JellyConnect :: No libraries data.")
                libraries_list = {
                    'libraries_count': '0',
                    'libraries_list': []
                }
                return libraries_list
            else:
                libraries_output = {
                    'section_id': a['ItemId'],
                    'section_type': a['CollectionType'],
                    'section_name': a['Name'],
                    'agent': a['LibraryOptions']['TypeOptions'][0]['MetadataFetchers'][0],
                    # 'art': helpers.get_xml_attr(result, 'art')
                }

                if libraries_output["section_type"] == "tvshows":
                    libraries_output["section_type"] = "show"

                if libraries_output["section_type"] == "movies":
                    libraries_output["section_type"] = "movie"

                try:
                    if a['PrimaryImageItemId']:
                        libraries_output["thumb"] = f"/Items/{a['PrimaryImageItemId']}/Images/Primary"
                except KeyError:
                    pass

                libraries_list.append(libraries_output)

        output = {
            'libraries_count': len(xml_head),
            'title': xml_head[0]['Name'],
            'libraries_list': libraries_list
        }

        return output

    def get_library_children_details(self, section_id='', section_type='', count='', item_id='', get_media_info=False):
        """
        Return processed and validated server library items list.

        Parameters required:    section_type { movie, show, episode, artist }
                                section_id { unique library key }

        Output: array
        """

        if section_type == 'movie':
            sort_type = '&type=1'
        elif section_type == 'show':
            sort_type = '&type=2'
        elif section_type == 'season':
            sort_type = '&type=3'
        elif section_type == 'episode':
            sort_type = '&type=4'
        elif section_type == 'artist':
            sort_type = '&type=8'
        elif section_type == 'album':
            sort_type = '&type=9'
        elif section_type == 'track':
            sort_type = '&type=10'
        elif section_type == 'photo':
            sort_type = ''
        elif section_type == 'photo_album':
            sort_type = '&type=14'
        elif section_type == 'picture':
            sort_type = '&type=13&clusterZoomLevel=1'
        elif section_type == 'clip':
            sort_type = '&type=12&clusterZoomLevel=1'
        else:
            sort_type = ''

        if section_type == "Episode":
            section_type = "episode"

        if section_type == "movie":
            library_data = self.fetch_movie_library_list(section_id=section_id, output_format='json')

            try:
                xml_head = library_data
            except Exception as e:
                logger.warn(f"JellyPy JellyConnect :: Unable to parse JSON for get_library_children_details: {e}.")
                return []

        elif section_type == "show":
            library_data = self.fetch_tv_library_list(section_id=section_id, output_format='json', count=count)

            try:
                xml_head = library_data
            except Exception as e:
                logger.warn(f"JellyPy JellyConnect :: Unable to parse JSON for get_library_children_details: {e}.")
                return []

        elif section_type == "season":
            try:
                library_data = self.get_library_recently_added_seasons(series_id=item_id, output_format='json')
            except (TypeError, KeyError):
                library_data = self.fetch_tv_season_library_list(section_id=section_id, output_format='json',
                                                                 count=count)

            try:
                xml_head = library_data
            except Exception as e:
                logger.warn(f"JellyPy JellyConnect :: Unable to parse JSON for get_library_children_details: {e}.")

        elif section_type == "episode":
            try:
                series_id = self.get_media_details(item_id)
                series_id = series_id["ParentId"]
                library_data = self.get_library_recently_added_episodes(series_id=series_id, output_format='json',
                                                                        season_id=item_id, limit=count)
            except (TypeError, KeyError):
                library_data = self.fetch_tv_episode_library_list(section_id=section_id, output_format='json',
                                                                  count=count)

            try:
                xml_head = library_data
            except Exception as e:
                logger.warn(f"JellyPy JellyConnect :: Unable to parse JSON for get_library_children_details: {e}.")

        elif section_type == 'album':
            if section_type == 'album' and item_id:
                sort_type += '&artist.id=' + str(item_id)

            xml_head = self.fetch_music_library_list(section_id=str(section_id), count=count, output_format='json')

        else:
            logger.warn(
                "JellyPy JellyConnect :: get_library_children called by invalid section_id or rating_key provided.")
            return []

        library_count = '0'
        children_list = []

        for a in xml_head:
            if len(xml_head) == 0:
                logger.debug("JellyPy JellyConnect :: No library data.")
                children_list = {
                    'library_count': '0',
                    'children_list': []
                }
                return children_list

            library_count = len(xml_head)

            # Get show/season info from xml_head
            item_main = []

            if a["Type"] == "Movie":
                item_main.append(a)
            elif a["Type"] == "Episode":
                item_main.append(a)
            elif a["Type"] == "Series":
                item_main.append(a)
            elif a["Type"] == "Season":
                item_main.append(a)

            for item in item_main:
                media_type = item["Type"].lower()
                if item["IsFolder"] and media_type == 'photo':
                    media_type = 'photo_album'
                item_id_ = item["Id"]

                result_ = self.get_media_details(item_id_, output_format="json")

                item_info = {
                    'section_id': result_["ParentId"],
                    'media_type': media_type,
                    'added_at': helpers.datetime_to_unix(result_["DateCreated"]),
                    'title': result_["Name"],
                    'sort_title': result_["SortName"],
                    'thumb': f"/Items/{result_['Id']}/Images/Primary",
                    'rating_key': result_['Id'],
                    'grandparent_thumb': helpers.get_json_attr(item, 'grandparentThumb'),
                    'media_index': helpers.get_json_attr(item, 'index'),
                    'parent_media_index': helpers.get_json_attr(item, 'parentIndex'),
                    'parent_title': helpers.get_json_attr(item, 'parentTitle'),
                    'grandparent_title': helpers.get_json_attr(item, 'grandparentTitle'),
                    'parent_rating_key': result_["ParentId"],
                    'grandparent_rating_key': result_["ParentId"],
                }

                if item_info["media_type"] == "series":
                    item_info["media_type"] = "show"

                try:
                    if result_["ImageTags"]["ParentId"]:
                        item_info[
                            "parent_thumb"] = f"/Items/{result_['ParentId']}/Images/Primary"
                except KeyError:
                    pass

                try:
                    if result_["ProductionYear"]:
                        item_info["year"] = result_["ProductionYear"]
                except KeyError:
                    pass

                try:
                    if result_["OriginalTitle"]:
                        item_info["original_title"] = result_["OriginalTitle"]
                except KeyError:
                    pass

                if get_media_info:
                    result_ = self.get_media_details(item["Id"], output_format="json")

                    try:
                        media_stream = result_["MediaSources"][0]["MediaStreams"]
                        resolution = f"{result_['Height']}x{result_['Width']}"
                        container = result_["MediaSources"][0]["Container"].upper()
                        file = result_["MediaSources"][0]["Path"]
                        file_size = result_["MediaSources"][0]["Size"]
                        for stream in media_stream:
                            if stream["Type"] == "Audio":
                                audio_codec = stream["Codec"]
                                audio_channels = stream["Channels"]
                            if stream["Type"] == "Video":
                                video_codec = stream["Codec"]
                                framerate = stream["RealFrameRate"]
                                bitrate = stream["BitRate"]
                    except KeyError:
                        container = ""
                        bitrate = ""
                        video_codec = ""
                        resolution = ""
                        framerate = ""
                        audio_codec = ""
                        audio_channels = ""
                        file = ""
                        file_size = ""

                    media_info = {
                        'container': container,
                        'bitrate': bitrate,
                        'video_codec': video_codec.upper(),
                        'video_resolution': resolution,
                        'video_framerate': framerate,
                        'audio_codec': audio_codec.upper(),
                        'audio_channels': audio_channels,
                        'file': file,
                        'file_size': file_size
                    }
                    item_info.update(media_info)

                children_list.append(item_info)

        output = {'library_count': library_count,
                  'children_list': children_list
                  }

        return output

    def get_library_details(self):
        """
        Return processed and validated library statistics.

        Output: array
        """
        server_libraries = self.get_server_children()

        server_library_stats = []

        if server_libraries and server_libraries['libraries_count'] != '0':
            libraries_list = server_libraries['libraries_list']

            for library in libraries_list:
                section_type = library['section_type']
                section_id = library['section_id']
                children_list = self.get_library_children_details(section_id=section_id, section_type=section_type,
                                                                  count='1')

                if children_list:
                    library_stats = {
                        'section_id': section_id,
                        'section_name': library['section_name'],
                        'section_type': section_type,
                        'agent': library['agent'],
                        'count': children_list['library_count'],
                        'is_active': 1
                    }

                    try:
                        if library["thumb"]:
                            library_stats["thumb"] = library['thumb']
                    except KeyError:
                        pass

                    try:
                        if library["art"]:
                            library_stats["art"] = library['art']
                    except KeyError:
                        pass

                    if children_list["children_list"][0]["media_type"] == 'show':
                        parent_list = self.get_library_children_details(section_id=section_id, section_type='season',
                                                                        count='1')

                        if parent_list:
                            parent_stats = {'parent_count': parent_list['library_count']}
                            library_stats.update(parent_stats)

                        child_list = self.get_library_children_details(section_id=section_id, section_type='episode',
                                                                       count='1')
                        if child_list:
                            child_stats = {'child_count': child_list['library_count']}
                            library_stats.update(child_stats)

                    if section_type == 'artist':
                        parent_list = self.get_library_children_details(section_id=section_id, section_type='album',
                                                                        count='1')
                        if parent_list:
                            parent_stats = {'parent_count': parent_list['library_count']}
                            library_stats.update(parent_stats)

                        child_list = self.get_library_children_details(section_id=section_id, section_type='track',
                                                                       count='1')
                        if child_list:
                            child_stats = {'child_count': child_list['library_count']}
                            library_stats.update(child_stats)

                    if section_type == 'photo':
                        parent_list = self.get_library_children_details(section_id=section_id, section_type='picture',
                                                                        count='1')
                        if parent_list:
                            parent_stats = {'parent_count': parent_list['library_count']}
                            library_stats.update(parent_stats)

                        child_list = self.get_library_children_details(section_id=section_id, section_type='clip',
                                                                       count='1')
                        if child_list:
                            child_stats = {'child_count': child_list['library_count']}
                            library_stats.update(child_stats)

                    server_library_stats.append(library_stats)

        return server_library_stats

    def get_library_label_details(self, section_id=''):
        labels_data = self.get_library_labels(section_id=str(section_id), output_format='xml')

        try:
            xml_head = labels_data.getElementsByTagName('MediaContainer')
        except Exception as e:
            logger.warn("JellyPy JellyConnect :: Unable to parse JSON for get_library_label_details: %s." % e)
            return None

        labels_list = []

        for a in xml_head:
            if a.getAttribute('size'):
                if a.getAttribute('size') == '0':
                    logger.debug("JellyPy JellyConnect :: No labels data.")
                    return labels_list

            if a.getElementsByTagName('Directory'):
                labels_main = a.getElementsByTagName('Directory')
                for item in labels_main:
                    label = {'label_key': helpers.get_xml_attr(item, 'key'),
                             'label_title': helpers.get_xml_attr(item, 'title')
                             }
                    labels_list.append(label)

        return labels_list

    def get_image(self, img=None, width=1000, height=1500, opacity=None, background=None, blur=None,
                  img_format='png', clip=False, refresh=False, **kwargs):
        """
        Return image data as array.
        Array contains the image content type and image binary

        Parameters required:    img { Plex image location }
        Optional parameters:    width { the image width }
                                height { the image height }
                                opacity { the image opacity 0-100 }
                                background { the image background HEX }
                                blur { the image blur 0-100 }
        Output: array
        """

        width = width or 1000
        height = height or 1500

        uri = f'{self.url}{img}?width={width}&height={height}&blur={blur}&backgroundColor={background}&blur={opacity}'

        result = self.request_handler.make_request(uri=uri, request_type='GET', return_type=True)

        if result is None:
            return
        else:
            return result[0], result[1]

    def get_search_results(self, query='', limit=''):
        """
        Return processed list of search results.

        Output: array
        """
        search_results = self.get_search(query=query, limit=limit, output_format='xml')

        try:
            xml_head = search_results.getElementsByTagName('MediaContainer')
        except Exception as e:
            logger.warn("JellyPy JellyConnect :: Unable to parse JSON for get_search_result: %s." % e)
            return []

        search_results_list = {
            'movie': [],
            'show': [],
            'season': [],
            'episode': [],
            'artist': [],
            'album': [],
            'track': [],
            'collection': []
        }

        for a in xml_head:
            hubs = a.getElementsByTagName('Hub')

            for h in hubs:
                if helpers.get_xml_attr(h, 'size') == '0' or \
                        helpers.get_xml_attr(h, 'type') not in search_results_list:
                    continue

                if h.getElementsByTagName('Video'):
                    result_data = h.getElementsByTagName('Video')
                    for result in result_data:
                        rating_key = helpers.get_xml_attr(result, 'ratingKey')
                        metadata = self.get_metadata_details(rating_key=rating_key)
                        search_results_list[metadata['media_type']].append(metadata)

                if h.getElementsByTagName('Directory'):
                    result_data = h.getElementsByTagName('Directory')
                    for result in result_data:
                        rating_key = helpers.get_xml_attr(result, 'ratingKey')
                        metadata = self.get_metadata_details(rating_key=rating_key)
                        search_results_list[metadata['media_type']].append(metadata)

                        if metadata['media_type'] == 'show':
                            show_seasons = self.get_item_children(rating_key=metadata['rating_key'])
                            if show_seasons['children_count'] != 0:
                                for season in show_seasons['children_list']:
                                    if season['rating_key']:
                                        metadata = self.get_metadata_details(rating_key=season['rating_key'])
                                        search_results_list['season'].append(metadata)

                if h.getElementsByTagName('Track'):
                    result_data = h.getElementsByTagName('Track')
                    for result in result_data:
                        rating_key = helpers.get_xml_attr(result, 'ratingKey')
                        metadata = self.get_metadata_details(rating_key=rating_key)
                        search_results_list[metadata['media_type']].append(metadata)

        output = {'results_count': sum(len(s) for s in search_results_list.values()),
                  'results_list': search_results_list
                  }

        return output

    def get_rating_keys_list(self, rating_key='', media_type=''):
        """
        Return processed list of grandparent/parent/child rating keys.

        Output: array
        """

        if media_type == 'movie':
            key_list = {0: {'rating_key': int(rating_key)}}
            return key_list

        if media_type == 'artist' or media_type == 'album' or media_type == 'track':
            match_type = 'title'
        else:
            match_type = 'index'

        section_id = None
        library_name = None

        # get grandparent rating key
        if media_type == 'season' or media_type == 'album':
            try:
                metadata = self.get_metadata_details(rating_key=rating_key)
                rating_key = metadata['parent_rating_key']
                section_id = metadata['section_id']
                library_name = metadata['library_name']
            except Exception as e:
                logger.warn(
                    "JellyPy JellyConnect :: Unable to get parent_rating_key for get_rating_keys_list: %s." % e)
                return {}

        elif media_type == 'episode' or media_type == 'track':
            try:
                metadata = self.get_metadata_details(rating_key=rating_key)
                rating_key = metadata['grandparent_rating_key']
                section_id = metadata['section_id']
                library_name = metadata['library_name']
            except Exception as e:
                logger.warn(
                    "JellyPy JellyConnect :: Unable to get grandparent_rating_key for get_rating_keys_list: %s." % e)
                return {}

        elif media_type == 'artist':
            try:
                metadata = self.get_metadata_details(rating_key=rating_key)
                section_id = metadata['section_id']
                library_name = metadata['library_name']
            except Exception as e:
                logger.warn(
                    "JellyPy JellyConnect :: Unable to get grandparent_rating_key for get_rating_keys_list: %s." % e)
                return {}

        # get parent_rating_keys
        if media_type in ('artist', 'album', 'track'):
            sort_type = f'&artist.id={rating_key}&type=9'
            xml_head = self.fetch_music_library_list(
                section_id=str(section_id),
                sort_type=sort_type,
                output_format='xml'
            )
        else:
            metadata = self.fetch_movie_library_list(str(rating_key), output_format='xml')

            try:
                xml_head = metadata.getElementsByTagName('MediaContainer')
            except Exception as e:
                logger.warn("JellyPy JellyConnect :: Unable to parse JSON for get_rating_keys_list: %s." % e)
                return {}

        for a in xml_head:
            if a.getAttribute('size'):
                if a.getAttribute('size') == '0':
                    return {}

            title = helpers.get_xml_attr(a, 'title2')

            if a.getElementsByTagName('Directory'):
                parents_metadata = a.getElementsByTagName('Directory')
            else:
                parents_metadata = []

            parents = {}
            for item in parents_metadata:
                parent_rating_key = helpers.get_xml_attr(item, 'ratingKey')
                parent_index = helpers.get_xml_attr(item, 'index')
                parent_title = helpers.get_xml_attr(item, 'title')

                if parent_rating_key:
                    # get rating_keys
                    metadata = self.fetch_movie_library_list(str(parent_rating_key), output_format='xml')

                    try:
                        xml_head = metadata.getElementsByTagName('MediaContainer')
                    except Exception as e:
                        logger.warn("JellyPy JellyConnect :: Unable to parse JSON for get_rating_keys_list: %s." % e)
                        return {}

                    for a in xml_head:
                        if a.getAttribute('size'):
                            if a.getAttribute('size') == '0':
                                return {}

                        if a.getElementsByTagName('Video'):
                            children_metadata = a.getElementsByTagName('Video')
                        elif a.getElementsByTagName('Track'):
                            children_metadata = a.getElementsByTagName('Track')
                        else:
                            children_metadata = []

                        children = {}
                        for item in children_metadata:
                            child_rating_key = helpers.get_xml_attr(item, 'ratingKey')
                            child_index = helpers.get_xml_attr(item, 'index')
                            child_title = helpers.get_xml_attr(item, 'title')

                            if child_rating_key:
                                key = int(child_index) if child_index else child_title
                                children.update({key: {'rating_key': int(child_rating_key)}})

                    key = int(parent_index) if match_type == 'index' else str(parent_title).lower()
                    parents.update({key:
                                        {'rating_key': int(parent_rating_key),
                                         'children': children}
                                    })

        key = 0 if match_type == 'index' else str(title).lower()
        key_list = {key: {'rating_key': int(rating_key),
                          'children': parents},
                    'section_id': section_id,
                    'library_name': library_name
                    }

        return key_list

    def get_server_response(self):
        account_data = self.get_account(output_format='xml')

        try:
            xml_head = account_data.getElementsByTagName('MyPlex')
        except Exception as e:
            logger.warn("JellyPy JellyConnect :: Unable to parse JSON for get_server_response: %s." % e)
            return None

        server_response = {}

        for a in xml_head:
            server_response = {
                'mapping_state': helpers.get_xml_attr(a, 'mappingState'),
                               'mapping_error': helpers.get_xml_attr(a, 'mappingError'),
                               'sign_in_state': helpers.get_xml_attr(a, 'signInState'),
                               'public_address': helpers.get_xml_attr(a, 'publicAddress'),
                               'public_port': helpers.get_xml_attr(a, 'publicPort'),
                               'private_address': helpers.get_xml_attr(a, 'privateAddress'),
                               'private_port': helpers.get_xml_attr(a, 'privatePort')
                               }

            if server_response['mapping_state'] == 'unknown':
                server_response['reason'] = 'Plex remote access port mapping unknown'
            elif server_response['mapping_state'] not in ('mapped', 'waiting'):
                server_response['reason'] = 'Plex remote access port not mapped'
            elif server_response['mapping_error'] == 'unreachable':
                server_response['reason'] = 'Plex remote access port mapped, ' \
                                            'but the port is unreachable from Plex.tv'
            elif server_response['mapping_error'] == 'publisherror':
                server_response['reason'] = 'Plex remote access port mapped, ' \
                                            'but failed to publish the port to Plex.tv'
            else:
                server_response['reason'] = ''

        return server_response

    def get_update_staus(self):
        # Refresh the Plex updater status first
        self.put_updater()
        updater_status = self.get_updater(output_format='xml')

        try:
            xml_head = updater_status.getElementsByTagName('MediaContainer')
        except Exception as e:
            logger.warn("JellyPy JellyConnect :: Unable to parse JSON for get_update_staus: %s." % e)

            # Catch the malformed XML on certain PMX version.
            # XML parser helper returns empty list if there is an error parsing XML
            if updater_status == []:
                logger.warn(
                    "Plex API updater XML is broken on the current PMS version. Please update your PMS manually.")
                logger.info("JellyPy is unable to check for Plex updates. Disabling check for Plex updates.")

                # Disable check for Plex updates
                jellypy.CONFIG.MONITOR_JELLYFIN_UPDATES = 0
                jellypy.initialize_scheduler()
                jellypy.CONFIG.write()

            return {}

        updater_info = {}
        for a in xml_head:
            if a.getElementsByTagName('Release'):
                release = a.getElementsByTagName('Release')
                for item in release:
                    updater_info = {'can_install': helpers.get_xml_attr(a, 'canInstall'),
                                    'download_url': helpers.get_xml_attr(a, 'downloadURL'),
                                    'version': helpers.get_xml_attr(item, 'version'),
                                    'state': helpers.get_xml_attr(item, 'state'),
                                    'changelog': helpers.get_xml_attr(item, 'fixed')
                                    }

        return updater_info

    def set_server_version(self):
        identity = self.get_server_identity()
        version = identity.get('version', jellypy.CONFIG.JELLYFIN_VERSION)

        jellypy.CONFIG.__setattr__('JELLYFIN_VERSION', version)
        jellypy.CONFIG.write()

    def get_server_update_channel(self):
        if jellypy.CONFIG.JELLYFIN_UPDATE_CHANNEL == 'stable':
            update_channel_value = self.get_server_pref('ButlerUpdateChannel')

            if update_channel_value == '8':
                return 'beta'
            else:
                return 'public'

        return jellypy.CONFIG.JELLYFIN_UPDATE_CHANNEL

    @staticmethod
    def get_dynamic_range(stream):
        extended_display_title = helpers.get_xml_attr(stream, 'extendedDisplayTitle')
        bit_depth = helpers.cast_to_int(helpers.get_xml_attr(stream, 'bitDepth'))
        color_space = helpers.get_xml_attr(stream, 'colorSpace')
        DOVI_profile = helpers.get_xml_attr(stream, 'DOVIProfile')

        HDR = bool(bit_depth > 8 and 'bt2020' in color_space)
        DV = bool(DOVI_profile)

        if not HDR and not DV:
            return 'SDR'

        video_dynamic_range = []

        # HDR details got introduced with PMS version 1.25.6.5545
        if helpers.version_to_tuple(jellypy.CONFIG.JELLYFIN_VERSION) >= helpers.version_to_tuple('1.25.6.5545'):
            if 'Dolby Vision' in extended_display_title or 'DoVi' in extended_display_title:
                video_dynamic_range.append('Dolby Vision')
            if 'HLG' in extended_display_title:
                video_dynamic_range.append('HLG')
            if 'HDR10' in extended_display_title:
                video_dynamic_range.append('HDR10')
            elif 'HDR' in extended_display_title:
                video_dynamic_range.append('HDR')
        else:
            if DV:
                video_dynamic_range.append('Dolby Vision')
            elif HDR:
                # Exact HDR version needs PMS version 1.25.6.5545 or newer
                video_dynamic_range.append('HDR')

        if not video_dynamic_range:
            return 'SDR'
        return '/'.join(video_dynamic_range)
