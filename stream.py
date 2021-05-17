import youtube_dl
from JJMumbleBot.lib.plugin_template import PluginBase
from JJMumbleBot.lib.utils.plugin_utils import PluginUtilityService
from JJMumbleBot.lib.utils.logging_utils import log
from JJMumbleBot.lib.utils.print_utils import PrintMode
from JJMumbleBot.lib.utils import dir_utils
from JJMumbleBot.lib.audio.audio_api import TrackInfo, TrackType, AudioLibrary
from JJMumbleBot.settings import global_settings as gs
from JJMumbleBot.settings import runtime_settings
from JJMumbleBot.lib.resources.strings import *
import warnings
import os
from bs4 import BeautifulSoup


class Plugin(PluginBase):
    def __init__(self):
        super().__init__()
        from json import loads
        self.plugin_name = os.path.basename(__file__).rsplit('.')[0]
        self.metadata = PluginUtilityService.process_metadata(f'plugins/extensions/{self.plugin_name}')
        self.plugin_cmds = loads(self.metadata.get(C_PLUGIN_INFO, P_PLUGIN_CMDS))
        self.is_running = True
        dir_utils.make_directory(f'{gs.cfg[C_MEDIA_SETTINGS][P_TEMP_MED_DIR]}/{self.plugin_name}/')
        dir_utils.clear_directory(f'{dir_utils.get_temp_med_dir()}/{self.plugin_name}')
        warnings.filterwarnings("ignore", category=UserWarning, module='bs4')
        log(
            INFO,
            f"{self.metadata[C_PLUGIN_INFO][P_PLUGIN_NAME]} v{self.metadata[C_PLUGIN_INFO][P_PLUGIN_VERS]} Plugin Initialized.",
            origin=L_STARTUP,
            print_mode=PrintMode.REG_PRINT.value
        )

    def quit(self):
        if gs.aud_interface.check_dni_is_mine(self.plugin_name):
            gs.aud_interface.stop()
            gs.audio_dni = None
        dir_utils.clear_directory(f'{dir_utils.get_temp_med_dir()}/{self.plugin_name}')
        self.is_running = False
        log(
            INFO,
            f"Exiting {self.plugin_name} plugin...",
            origin=L_SHUTDOWN,
            print_mode=PrintMode.REG_PRINT.value
        )

    def stop(self):
        if self.is_running:
            self.quit()

    def start(self):
        if not self.is_running:
            self.__init__()

    def cmd_stream(self, data):
        if gs.aud_interface.check_dni(self.plugin_name):
            gs.aud_interface.set_dni(self.plugin_name, self.metadata[C_PLUGIN_INFO][P_PLUGIN_NAME])
        else:
            return

        all_data = data.message.strip().split(' ', 1)
        sender = gs.mumble_inst.users[data.actor]['name']
        stripped_url = BeautifulSoup(all_data[1], features='html.parser').get_text()

        if "youtube.com" in stripped_url or "youtu.be" in stripped_url:
            stream_data = self.get_stream_info(stripped_url, "bestaudio/best")
        elif "twitch.tv" in stripped_url:
            stream_data = self.get_stream_info(stripped_url, "audio_only")
        else:
            gs.gui_service.quick_gui(
                "Only twitch and youtube are supported at this time.",
                text_type='header',
                box_align='left')
            gs.aud_interface.clear_dni()
            return

        track_obj = TrackInfo(
            uri=stream_data['main_url'],
            name=stream_data['main_title'],
            sender=sender,
            track_type=TrackType.STREAM,
            quiet=False
        )

        gs.aud_interface.enqueue_track(
            track_obj=track_obj,
            to_front=True
        )

        if "twitch.tv" in stripped_url:
            gs.aud_interface.play(audio_lib=AudioLibrary.FFMPEG)
        else:
            gs.aud_interface.play(audio_lib=AudioLibrary.VLC)

    def get_stream_info(self, stream_url, format):
        # Update the audio interface status with the media mrl, duration, and video title.
        try:
            ydl_opts = {
                'quiet': True,
                'format': format,
                'noplaylist': True,
                'skip_download': True,
                'proxy': gs.cfg[C_MEDIA_SETTINGS][P_MEDIA_PROXY_URL]
            }
            if runtime_settings.use_logging:
                ydl_opts['logger'] = gs.log_service
            if len(gs.cfg[C_MEDIA_SETTINGS][P_MEDIA_COOKIE_FILE]) > 0:
                ydl_opts['cookiefile'] = gs.cfg[C_MEDIA_SETTINGS][P_MEDIA_COOKIE_FILE]

            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.cache.remove()
                info_dict = ydl.extract_info(stream_url, download=False)

                prep_struct = {
                    'std_url': stream_url,
                    'main_url': info_dict['url'],
                    'main_title': info_dict['title']
                }
                return prep_struct
        except youtube_dl.utils.DownloadError as e:
            log(ERROR, f"Encountered a youtube_dl download error while retrieving the stream information for {stream_url}.\n{e}",
                origin=L_GENERAL, print_mode=PrintMode.VERBOSE_PRINT.value)
            return None
