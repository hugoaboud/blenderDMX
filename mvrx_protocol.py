import bpy
from dmx.mvrxchange import mvrxchange_client as mvrx_client
from dmx.mvrxchange import mvrxchange_server as mvrx_server
from dmx.logging import DMX_Log
import os
import time
import pathlib
from dmx import bl_info as application_info
import uuid as py_uuid


class DMX_MVR_X_Client:
    _instance = None

    def __init__(self):
        super(DMX_MVR_X_Client, self).__init__()
        self._dmx = bpy.context.scene.dmx
        self.client = None
        self.selected_client = None

        addon_name = pathlib.Path(__file__).parent.parts[-1]
        prefs = bpy.context.preferences.addons[addon_name].preferences
        application_uuid = prefs.get("application_uuid", str(py_uuid.uuid4()))  # must never be 0
        self.application_uuid = application_uuid
        # print("bl info", application_info) # TODO: use this in the future

    @staticmethod
    def callback(data):
        if "StationUUID" not in data:
            print("Bad response", data)
            return
        uuid = data["StationUUID"]
        if "Commits" in data:
            DMX_MVR_X_Client._instance._dmx.createMVR_Commits(data["Commits"], uuid)
        if "FileUUID" in data:
            DMX_MVR_X_Client._instance._dmx.createMVR_Commits([data], uuid)
        if "Provider" in data:
            provider = data["Provider"]
            DMX_MVR_X_Client._instance._dmx.updateMVR_Client(provider=provider, station_uuid=uuid)
        if "file_downloaded" in data:
            DMX_MVR_X_Client._instance._dmx.fetched_mvr_downloaded_file(data["file_downloaded"])

        msg_type = data.get("Type", "")
        msg_ok = data.get("OK", "")
        if msg_type == "MVR_JOIN_RET" and msg_ok is False:
            DMX_Log.log.error("MVR-xchange client refused our connection")
            dmx = bpy.context.scene.dmx
            dmx.mvrx_enabled = False

    @staticmethod
    def request_file(commit):
        if not DMX_MVR_X_Client._instance:
            return
        if DMX_MVR_X_Client._instance.client:
            ADDON_PATH = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(ADDON_PATH, "assets", "mvrs", f"{commit.commit_uuid}.mvr")
            try:
                DMX_MVR_X_Client.connect()
                DMX_MVR_X_Client._instance.client.request_file(commit, path)
            except Exception as e:
                print("problem requesting file", e)
                return
            DMX_Log.log.info("Requesting file")

    @staticmethod
    def re_join():
        if not DMX_MVR_X_Client._instance:
            return
        if DMX_MVR_X_Client._instance.client:
            try:
                DMX_MVR_X_Client.connect()
                DMX_MVR_X_Client._instance.client.join_mvr()
            except Exception as e:
                print("problem re_joining", e)
                return

    @staticmethod
    def connect():
        if not DMX_MVR_X_Client._instance:
            return
        try:
            client = DMX_MVR_X_Client._instance.selected_client
            print("Connecting to MVR-xchange client", client.ip_address, client.port)
            DMX_MVR_X_Client._instance.client = mvrx_client.client(client.ip_address, client.port, timeout=0, callback=DMX_MVR_X_Client.callback, application_uuid=DMX_MVR_X_Client._instance.application_uuid)

        except Exception as e:
            print("Cannot connect to host", e)
            return
        DMX_MVR_X_Client._instance.client.start()
        print("thread started")

    @staticmethod
    def join(client):
        DMX_MVR_X_Client._instance = DMX_MVR_X_Client()
        DMX_MVR_X_Client._instance.selected_client = client
        DMX_MVR_X_Client.connect()
        DMX_MVR_X_Client._instance.client.join_mvr()
        # TODO do only if we get OK ret
        DMX_Log.log.info("Joining")

    @staticmethod
    def disable():
        if DMX_MVR_X_Client._instance:
            print("stop one")
            if DMX_MVR_X_Client._instance.client:
                print("stop two")
                DMX_MVR_X_Client._instance.client.stop()
            DMX_MVR_X_Client._instance = None
            print("stopped")
            DMX_Log.log.info("Disabling MVR")
        print("i am gone")

    @staticmethod
    def leave():
        if DMX_MVR_X_Client._instance:
            if DMX_MVR_X_Client._instance.client:
                DMX_MVR_X_Client.connect()
                DMX_MVR_X_Client._instance.client.leave_mvr()
                time.sleep(0.3)
                DMX_MVR_X_Client._instance.client.stop()
            DMX_MVR_X_Client._instance = None
            DMX_Log.log.info("Disabling MVR")


class DMX_MVR_X_Server:
    _instance = None

    def __init__(self):
        super(DMX_MVR_X_Server, self).__init__()
        self._dmx = bpy.context.scene.dmx
        self.server = None

        addon_name = pathlib.Path(__file__).parent.parts[-1]
        prefs = bpy.context.preferences.addons[addon_name].preferences
        application_uuid = prefs.get("application_uuid", str(py_uuid.uuid4()))  # must never be 0
        self.application_uuid = application_uuid
        # print("bl info", application_info) # TODO: use this in the future

    @staticmethod
    def callback(json_data, data):
        print("callback", json_data, data)
        addr, port = data.addr

        if "StationUUID" not in json_data:
            print("Bad response", json_data)
            return
        uuid = json_data["StationUUID"]
        if "Commits" in json_data:
            DMX_MVR_X_Server._instance._dmx.createMVR_Commits(json_data["Commits"], uuid)
        if "FileUUID" in json_data:
            DMX_MVR_X_Server._instance._dmx.createMVR_Commits([json_data], uuid)
        if "Provider" in json_data:
            provider = json_data["Provider"]
            station_name = ""
            if "StationName" in json_data:
                station_name = json_data["StationName"]
            DMX_MVR_X_Server._instance._dmx.createMVR_Client(station_name = station_name, station_uuid=uuid, service_name = None, ip_address=addr, port=port, provider = provider)
        if "file_downloaded" in json_data:
            DMX_MVR_X_Server._instance._dmx.fetched_mvr_downloaded_file(json_data["file_downloaded"])

    @staticmethod
    def request_file(commit):
        if DMX_MVR_X_Server._instance:
            if DMX_MVR_X_Server._instance.DMX_MVR_X_Server:
                ADDON_PATH = os.path.dirname(os.path.abspath(__file__))
                path = os.path.join(ADDON_PATH, "assets", "mvrs", f"{commit.commit_uuid}.mvr")
                try:
                    DMX_MVR_X_Server._instance.server.request_file(commit, path)
                except:
                    print("problem requesting file")
                    return
                DMX_Log.log.info("Requesting file")

    @staticmethod
    def enable():
        if DMX_MVR_X_Server._instance:
            return
        DMX_MVR_X_Server._instance = DMX_MVR_X_Server()
        try:
            DMX_MVR_X_Server._instance.server = mvrx_server.server(callback=DMX_MVR_X_Server.callback, uuid=DMX_MVR_X_Server._instance.application_uuid)

        except Exception as e:
            print("Cannot connect to host", e)
            return
        DMX_MVR_X_Server._instance.server.start()

    @staticmethod
    def get_port():
        if DMX_MVR_X_Server._instance:
            return DMX_MVR_X_Server._instance.server.get_port()

    @staticmethod
    def disable():
        if DMX_MVR_X_Server._instance:
            if DMX_MVR_X_Server._instance.server:
                DMX_MVR_X_Server._instance.server.stop()
            DMX_MVR_X_Server._instance = None
            DMX_Log.log.info("Disabling MVR")
