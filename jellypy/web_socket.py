# This file is part of Tautulli.
#
#  Tautulli is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Tautulli is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Tautulli.  If not, see <http://www.gnu.org/licenses/>.

# Mostly borrowed from https://github.com/trakt/Jellyfin-Trakt-Scrobbler

from __future__ import unicode_literals

import json
import ssl
import threading
import time

import certifi
import jellypy
import websocket
from future.builtins import str
from jellypy import activity_handler
from jellypy import activity_pinger
from jellypy import activity_processor
from jellypy import database
from jellypy import logger

name = 'websocket'
opcode_data = (websocket.ABNF.OPCODE_TEXT, websocket.ABNF.OPCODE_BINARY)
ws_shutdown = False
pong_timer = None
pong_count = 0


def start_thread():
    try:
        # Check for any existing sessions on start up
        activity_pinger.check_active_sessions(ws_request=True)
    except Exception as e:
        logger.error(f"JellyPy WebSocket :: Failed to check for active sessions: {e}.")
        logger.warn("JellyPy WebSocket :: Attempt to fix by flushing temporary sessions...")
        database.delete_sessions()

    # Start the websocket listener on it's own thread
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()


def on_connect():
    if jellypy.JELLYFIN_SERVER_UP is None:
        jellypy.JELLYFIN_SERVER_UP = True

    if not jellypy.JELLYFIN_SERVER_UP:
        logger.info("JellyPy WebSocket :: The Jellyfin Media Server is back up.")
        jellypy.JELLYFIN_SERVER_UP = True

        if activity_handler.ACTIVITY_SCHED.get_job('on_intdown'):
            logger.debug("JellyPy WebSocket :: Cancelling scheduled Jellyfin server down callback.")
            activity_handler.schedule_callback('on_intdown', remove_job=True)
        else:
            on_intup()

    jellypy.initialize_scheduler()
    if jellypy.CONFIG.WEBSOCKET_MONITOR_PING_PONG:
        send_ping()


def on_disconnect():
    if jellypy.JELLYFIN_SERVER_UP is None:
        jellypy.JELLYFIN_SERVER_UP = False

    if jellypy.JELLYFIN_SERVER_UP:
        logger.info("JellyPy WebSocket :: Unable to get a response from the server, Jellyfin server is down.")
        jellypy.JELLYFIN_SERVER_UP = False

        logger.debug(
            f"JellyPy WebSocket :: Scheduling Jellyfin server down callback in {jellypy.CONFIG.NOTIFY_SERVER_CONNECTION_THRESHOLD} seconds.")
        activity_handler.schedule_callback('on_intdown', func=on_intdown,
                                           seconds=jellypy.CONFIG.NOTIFY_SERVER_CONNECTION_THRESHOLD)

    activity_processor.ActivityProcessor().set_temp_stopped()
    jellypy.initialize_scheduler()


def on_intdown():
    jellypy.NOTIFY_QUEUE.put({'notify_action': 'on_intdown'})


def on_intup():
    jellypy.NOTIFY_QUEUE.put({'notify_action': 'on_intup'})


def reconnect():
    close()
    logger.info("JellyPy WebSocket :: Reconnecting websocket...")
    start_thread()


def shutdown():
    global ws_shutdown
    ws_shutdown = True
    close()


def close():
    logger.info("JellyPy WebSocket :: Disconnecting websocket...")
    jellypy.WEBSOCKET.close()
    jellypy.WS_CONNECTED = False


def send_ping():
    if jellypy.WS_CONNECTED:
        # logger.debug("JellyPy WebSocket :: Sending KeepAlive message.")

        global pong_timer
        pong_timer = threading.Timer(30, send_msg)
        pong_timer.daemon = True
        pong_timer.start()


def wait_pong():
    global pong_count
    pong_count += 1

    logger.warn(f"JellyPy WebSocket :: Failed to receive pong from websocket, ping attempt {str(pong_count)}.")

    if pong_count >= jellypy.CONFIG.WEBSOCKET_CONNECTION_ATTEMPTS:
        pong_count = 0
        close()


def send_msg():
    if jellypy.WS_CONNECTED:
        # jellypy.WEBSOCKET.send(json.dumps({'MessageType': 'KeepAlive', 'Data': ''}))
        jellypy.WEBSOCKET.send(json.dumps({"MessageType":"SessionsStart", "Data": "0,1000"}))


def receive_pong():
    # logger.debug("JellyPy WebSocket :: Received pong.")
    global pong_timer
    global pong_count
    if pong_timer:
        pong_timer = pong_timer.cancel()
        pong_count = 0


def run():
    from websocket import create_connection

    user_token = jellypy.CONFIG.JELLYFIN_ACCESS_TOKEN
    device_id = jellypy.CONFIG.JELLYFIN_DEVICE_ID

    if jellypy.CONFIG.JELLYFIN_SSL and jellypy.CONFIG.JELLYFIN_URL[:5] == 'https':
        uri = jellypy.CONFIG.JELLYFIN_URL.replace('https://', 'wss://') + '/socket'
        secure = 'secure '
        if jellypy.CONFIG.VERIFY_SSL_CERT:
            sslopt = {'ca_certs': certifi.where()}
        else:
            sslopt = {'cert_reqs': ssl.CERT_NONE}
    else:
        uri = f'ws://{jellypy.CONFIG.JELLYFIN_IP}:{jellypy.CONFIG.JELLYFIN_PORT}/socket'
        secure = ''
        sslopt = None

    timeout = jellypy.CONFIG.JELLYFIN_TIMEOUT

    global ws_shutdown
    ws_shutdown = False
    reconnects = 0

    header = {
        'Authorization': f'MediaBrowser Client=python-requests, Device={jellypy.CONFIG.JELLYFIN_DEVICE_NAME}, DeviceId={device_id}, Version={jellypy.version.JELLYPY_VERSION}, Token={user_token}'
    }

    # Try an open the websocket connection
    logger.info(f"JellyPy WebSocket :: Opening {secure}websocket.")
    try:
        jellypy.WEBSOCKET = create_connection(uri, sslopt=sslopt, header=header, timeout=timeout)
        logger.info("JellyPy WebSocket :: Websocket connection successful.")
        jellypy.WS_CONNECTED = True
    except (websocket.WebSocketException, IOError, Exception) as e:
        logger.error(f"JellyPy WebSocket :: {e}.")

    if jellypy.WS_CONNECTED:
        on_connect()

    while jellypy.WS_CONNECTED:
        try:
            process(*receive(jellypy.WEBSOCKET))

            # successfully received data, reset reconnects counter
            reconnects = 0

        except websocket.WebSocketConnectionClosedException:
            if ws_shutdown:
                break

            if reconnects == 0:
                logger.warn("JellyPy WebSocket :: Connection has closed.")

            if not reconnects < jellypy.CONFIG.WEBSOCKET_CONNECTION_ATTEMPTS:
                reconnects += 1

                # Sleep 5 between connection attempts
                if reconnects > 1:
                    time.sleep(jellypy.CONFIG.WEBSOCKET_CONNECTION_TIMEOUT)

                logger.warn(f"JellyPy WebSocket :: Reconnection attempt {str(reconnects)}.")

                try:
                    jellypy.WEBSOCKET = create_connection(uri, timeout=timeout, sslopt=sslopt, header=header)
                    logger.info("JellyPy WebSocket :: Ready")
                    jellypy.WS_CONNECTED = True
                except (websocket.WebSocketException, IOError, Exception) as e:
                    logger.error(f"JellyPy WebSocket :: {e}.")

            else:
                close()
                break

        except (websocket.WebSocketException, Exception) as e:
            if ws_shutdown:
                break

            logger.error(f"JellyPy WebSocket :: {e}.")
            close()
            break

    if not jellypy.WS_CONNECTED and not ws_shutdown:
        on_disconnect()

    logger.debug("JellyPy WebSocket :: Leaving thread.")


def receive(ws):
    frame = ws.recv_frame()

    if not frame:
        raise websocket.WebSocketException(f"Not a valid frame {frame}.")
    elif frame.opcode in opcode_data:
        return frame.opcode, frame.data
    elif frame.opcode == websocket.ABNF.OPCODE_CLOSE:
        ws.send_close()
        return frame.opcode, None
    elif frame.opcode == websocket.ABNF.OPCODE_PING:
        # logger.debug("JellyPy WebSocket :: Received ping, sending pong.")
        ws.pong("Hi!")
    elif frame.opcode == websocket.ABNF.OPCODE_PONG:
        receive_pong()

    return None, None


def process(opcode, data):
    if opcode not in opcode_data:
        return False

    try:
        data = data.decode('utf-8')
        logger.websocket_debug(data)
        event = json.loads(data)
    except Exception as e:
        logger.warn(f"JellyPy WebSocket :: Error decoding message from websocket: {e}")
        logger.websocket_error(data)
        return False

    event_type = event["MessageType"]

    print(f"event: {event}")

    if not event_type:
        return False

    if event_type == "ForceKeepAlive":
        jellypy.WEBSOCKET.send(json.dumps({'MessageType': 'KeepAlive', 'Data': ''}))

    if event_type == 'playing':
        event_data = event.get('PlaySessionStateNotification', event.get('_children', {}))

        if not event_data:
            logger.debug("JellyPy WebSocket :: Session event found but unable to get websocket data.")
            return False

        try:
            activity = activity_handler.ActivityHandler(timeline=event_data[0])
            activity.process()
        except Exception as e:
            logger.exception(f"JellyPy WebSocket :: Failed to process session data: {e}.")

    if event_type == 'timeline':
        event_data = event.get('TimelineEntry', event.get('_children', {}))

        if not event_data:
            logger.debug("JellyPy WebSocket :: Timeline event found but unable to get websocket data.")
            return False

        try:
            activity = activity_handler.TimelineHandler(timeline=event_data[0])
            activity.process()
        except Exception as e:
            logger.exception(f"JellyPy WebSocket :: Failed to process timeline data: {e}.")

    if event_type == 'reachability':
        event_data = event.get('ReachabilityNotification', event.get('_children', {}))

        if not event_data:
            logger.debug("JellyPy WebSocket :: Reachability event found but unable to get websocket data.")
            return False

        try:
            activity = activity_handler.ReachabilityHandler(data=event_data[0])
            activity.process()
        except Exception as e:
            logger.exception(f"JellyPy WebSocket :: Failed to process reachability data: {e}.")

    return True
