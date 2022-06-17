from base64 import b64encode
from requests import utils as rutils, get as rget
from re import match as re_match, search as re_search, split as re_split
from time import sleep, time
from os import path as ospath, remove as osremove, listdir, walk
from shutil import rmtree
from threading import Thread
from subprocess import run as srun
from pathlib import PurePath
from html import escape
from telegram.ext import CommandHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from bot import bot, Interval, INDEX_URL, BUTTON_FOUR_NAME, BUTTON_FOUR_URL, BUTTON_FIVE_NAME, BUTTON_FIVE_URL, \
                BUTTON_SIX_NAME, BUTTON_SIX_URL, VIEW_LINK, aria2, QB_SEED, dispatcher, DOWNLOAD_DIR, FSUB_CHANNEL_ID,\
                LEECH_LOG_LINK, MAKE_OWNER_AND_SUDO_ANONYMOUS, OWNER_ID, SUDO_USERS, FSUB, FSUB_CHANNELLINK, ACTIVE_TASK_LIMIT, \
                download_dict, download_dict_lock, TG_SPLIT_SIZE, LOGGER, DB_URI, INCOMPLETE_TASK_NOTIFIER, MEGAREST, LEECH_LOG, MIRROR_LOGS, \
                LEECH_PM, SUDO_ONLY_MIRROR, SUDO_ONLY_LEECH
from bot.helper.ext_utils.bot_utils import is_url, is_magnet, is_gdtot_link, is_mega_link, is_gdrive_link, get_content_type
from bot.helper.ext_utils.fs_utils import get_base_name, get_path_size, split_file, clean_download
from bot.helper.ext_utils.shortenurl import short_url
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException, NotSupportedExtractionArchive
from bot.helper.mirror_utils.download_utils.aria2_download import add_aria2c_download
from bot.helper.mirror_utils.download_utils.gd_downloader import add_gd_download
from bot.helper.mirror_utils.download_utils.qbit_downloader import QbDownloader
from bot.helper.mirror_utils.download_utils.mega_downloader import add_mega_download
from bot.helper.mirror_utils.download_utils.megarestsdkhelper import MegaDownloadeHelper
from bot.helper.mirror_utils.download_utils.direct_link_generator import direct_link_generator
from bot.helper.mirror_utils.download_utils.telegram_downloader import TelegramDownloadHelper
from bot.helper.mirror_utils.status_utils.extract_status import ExtractStatus
from bot.helper.mirror_utils.status_utils.zip_status import ZipStatus
from bot.helper.mirror_utils.status_utils.split_status import SplitStatus
from bot.helper.mirror_utils.status_utils.upload_status import UploadStatus
from bot.helper.mirror_utils.status_utils.tg_upload_status import TgUploadStatus
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.mirror_utils.upload_utils.pyrogramEngine import TgUploader
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, delete_all_messages, update_all_messages, auto_delete_message
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.db_handler import DbManger


class MirrorListener:
    def __init__(self, bot, message, isZip=False, extract=False, isQbit=False, isLeech=False, pswd=None, tag=None):
        self.bot = bot
        self.message = message
        self.uid = self.message.message_id
        self.extract = extract
        self.isZip = isZip
        self.isQbit = isQbit
        self.isLeech = isLeech
        self.pswd = pswd
        self.tag = tag
        self.isPrivate = self.message.chat.type in ['private', 'group']
        self.user_id = self.message.from_user.id

    def clean(self):
        try:
            aria2.purge()
            Interval[0].cancel()
            del Interval[0]
            delete_all_messages()
        except IndexError:
            pass

    def onDownloadStart(self):
        if not self.isPrivate and INCOMPLETE_TASK_NOTIFIER and DB_URI is not None:
            DbManger().add_incomplete_task(self.message.chat.id, self.message.link, self.tag)

    def onDownloadComplete(self):
        with download_dict_lock:
            LOGGER.info(f"Download completed: {download_dict[self.uid].name()}")
            download = download_dict[self.uid]
            name = str(download.name()).replace('/', '')
            gid = download.gid()
            size = download.size_raw()
            if name == "None" or self.isQbit or not ospath.exists(f'{DOWNLOAD_DIR}{self.uid}/{name}'):
                name = listdir(f'{DOWNLOAD_DIR}{self.uid}')[-1]
            m_path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
        if self.isZip:
            try:
                with download_dict_lock:
                    download_dict[self.uid] = ZipStatus(name, m_path, size)
                path = m_path + ".zip"
                LOGGER.info(f'Zip: orig_path: {m_path}, zip_path: {path}')
                if self.pswd is not None:
                    if self.isLeech and int(size) > TG_SPLIT_SIZE:
                        srun(["7z", f"-v{TG_SPLIT_SIZE}b", "a", "-mx=0", f"-p{self.pswd}", path, m_path])
                    else:
                        srun(["7z", "a", "-mx=0", f"-p{self.pswd}", path, m_path])
                elif self.isLeech and int(size) > TG_SPLIT_SIZE:
                    srun(["7z", f"-v{TG_SPLIT_SIZE}b", "a", "-mx=0", path, m_path])
                else:
                    srun(["7z", "a", "-mx=0", path, m_path])
            except FileNotFoundError:
                LOGGER.info('File to archive not found!')
                self.onUploadError('Internal error occurred!!')
                return
            if not self.isQbit or not QB_SEED or self.isLeech:
                try:
                    rmtree(m_path)
                except:
                    osremove(m_path)
        elif self.extract:
            try:
                if ospath.isfile(m_path):
                    path = get_base_name(m_path)
                LOGGER.info(f"Extracting: {name}")
                with download_dict_lock:
                    download_dict[self.uid] = ExtractStatus(name, m_path, size)
                if ospath.isdir(m_path):
                    for dirpath, subdir, files in walk(m_path, topdown=False):
                        for file_ in files:
                            if file_.endswith(".zip") or re_search(r'\.part0*1\.rar$|\.7z\.0*1$|\.zip\.0*1$', file_) \
                               or (file_.endswith(".rar") and not re_search(r'\.part\d+\.rar$', file_)):
                                m_path = ospath.join(dirpath, file_)
                                if self.pswd is not None:
                                    result = srun(["7z", "x", f"-p{self.pswd}", m_path, f"-o{dirpath}", "-aot"])
                                else:
                                    result = srun(["7z", "x", m_path, f"-o{dirpath}", "-aot"])
                                if result.returncode != 0:
                                    LOGGER.error('Unable to extract archive!')
                        for file_ in files:
                            if file_.endswith((".rar", ".zip")) or re_search(r'\.r\d+$|\.7z\.\d+$|\.z\d+$|\.zip\.\d+$', file_):
                                del_path = ospath.join(dirpath, file_)
                                osremove(del_path)
                    path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
                else:
                    if self.pswd is not None:
                        result = srun(["bash", "pextract", m_path, self.pswd])
                    else:
                        result = srun(["bash", "extract", m_path])
                    if result.returncode == 0:
                        LOGGER.info(f"Extracted Path: {path}")
                        osremove(m_path)
                    else:
                        LOGGER.error('Unable to extract archive! Uploading anyway')
                        path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
            except NotSupportedExtractionArchive:
                LOGGER.info("Not any valid archive, uploading file as it is.")
                path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
        else:
            path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
        up_name = PurePath(path).name
        up_path = f'{DOWNLOAD_DIR}{self.uid}/{up_name}'
        if self.isLeech and not self.isZip:
            checked = False
            for dirpath, subdir, files in walk(f'{DOWNLOAD_DIR}{self.uid}', topdown=False):
                for file_ in files:
                    f_path = ospath.join(dirpath, file_)
                    f_size = ospath.getsize(f_path)
                    if int(f_size) > TG_SPLIT_SIZE:
                        if not checked:
                            checked = True
                            with download_dict_lock:
                                download_dict[self.uid] = SplitStatus(up_name, up_path, size)
                            LOGGER.info(f"Splitting: {up_name}")
                        split_file(f_path, f_size, file_, dirpath, TG_SPLIT_SIZE)
                        osremove(f_path)
        if self.isLeech:
            size = get_path_size(f'{DOWNLOAD_DIR}{self.uid}')
            LOGGER.info(f"Leech Name: {up_name}")
            tg = TgUploader(up_name, self)
            tg_upload_status = TgUploadStatus(tg, size, gid, self)
            with download_dict_lock:
                download_dict[self.uid] = tg_upload_status
            update_all_messages()
            tg.upload()
        else:
            size = get_path_size(up_path)
            LOGGER.info(f"Upload Name: {up_name}")
            drive = GoogleDriveHelper(up_name, self)
            upload_status = UploadStatus(drive, size, gid, self)
            with download_dict_lock:
                download_dict[self.uid] = upload_status
            update_all_messages()
            drive.upload(up_name)

    def onDownloadError(self, error):
        error = error.replace('<', ' ').replace('>', ' ')
        clean_download(f'{DOWNLOAD_DIR}{self.uid}')
        with download_dict_lock:
            try:
                del download_dict[self.uid]
            except Exception as e:
                LOGGER.error(str(e))
            count = len(download_dict)
        msg = f"{self.tag} your download has been stopped due to: {error}"
        sendMessage(msg, self.bot, self.message)
        if count == 0:
            self.clean()
        else:
            update_all_messages()

        if not self.isPrivate and INCOMPLETE_TASK_NOTIFIER and DB_URI is not None:
            DbManger().rm_complete_task(self.message.link)

    def onUploadComplete(self, link: str, size, files, folders, typ, name: str):
        uname = f'<a href="tg://user?id={self.message.from_user.id}">{self.message.from_user.first_name}</a>'
        if not self.isPrivate and INCOMPLETE_TASK_NOTIFIER and DB_URI is not None:
            DbManger().rm_complete_task(self.message.link)
        msg = f"<b>Name: </b><code>{escape(name)}</code>\n\n<b>Size: </b>{size}"
        logmsg = f"<b>Name: </b><code>{escape(name)}</code>\n\n<b>Size: </b>{size}"
        mesg2 = self.message.text.split('\n')
        messageargs2 = mesg2[0].split(' ', maxsplit=1)
        replyto = self.message.reply_to_message
        if self.isLeech:
            user_id = self.message.from_user.id
            bot_d = bot.get_me()
            bot_username = bot_d.username
            checkbot = f"http://t.me/{bot_username}"
            leechloginvite = f"{LEECH_LOG_LINK}"

            leechresult = f"\n<b><i>{uname}</i></b>\n"
            leechresult += f"<b><i>Your File's Are Successfully Leeched And Sent To Your PM And Leech Log Chat.</i></b>"
            leechresult += f"\n<b><i>Click Below Button To Join Leech Log Chat or Check Your PM</i></b>"

            leechlogbutton = ButtonMaker()
            leechlogbutton.buildbutton("Log Chat", f"{leechloginvite}")
            leechlogbutton.buildbutton("Check PM", f"{checkbot}")
            
            user_id = self.message.from_user.id
            if user_id == OWNER_ID:
                ownerorsudo = f"Owner"
            else:
                ownerorsudo = f"Sudo User"
            ownerleechresult = f"<b>Dear {ownerorsudo} I Have Sent Your #Leeched File's In Your PM</b>"
            ownerleechbutton = ButtonMaker()
            ownerleechbutton.buildbutton("Check Now", checkbot)

            msg += f'\n\n<b>Total Files: </b>{folders}'
            logmsg += f'\n\n<b>Total Files: </b>{folders}'
            if typ != 0:
                msg += f'\n<b>Corrupted Files: </b>{typ}'
                logmsg += f'\n<b>Corrupted Files: </b>{typ}'
            if MAKE_OWNER_AND_SUDO_ANONYMOUS:
                            user_id = self.message.from_user.id
                            if (
                               user_id in SUDO_USERS or user_id == OWNER_ID
                            ):
                              msg += f'\n\n<b>cc:</b> <b><i><a href="tg://settings/">Anonymous</a></i></b>\n\n'
                              logmsg += f'\n\n<b>cc:</b> <b><i><a href="tg://settings/">Anonymous</a></i></b>'
                            else:
                              msg += f'\n\n<b>cc: </b>{self.tag}\n\n'
                              logmsg += f'\n\n<b>cc:</b> <b><a href="{self.message.link}">{self.message.from_user.first_name}</a></b>'
                              pass    
            else:
                msg += f'\n\n<b>cc: </b>{self.tag}\n\n'
                logmsg += f'\n\n<b>cc:</b> <b><a href="{self.message.link}">{self.message.from_user.first_name}</a></b>'
            
            if not files:
                if MAKE_OWNER_AND_SUDO_ANONYMOUS:
                    user_id = self.message.from_user.id
                    if (
                        user_id in SUDO_USERS or user_id == OWNER_ID
                        ):
                          LOGGER.info(f'Anonymous owner turned on and Files are Leeched by owner i wont send them on chat')
                          owner = sendMarkup(ownerleechresult, self.bot, self.message, InlineKeyboardMarkup(ownerleechbutton.build_menu(1)))
                          Thread(target=auto_delete_message, args=(self.bot, self.message, owner)).start()
                          try:
                              sendMessage(self.message.from_user.id, msg, self.bot, self.message)
                          except:
                              pass
                    else:
                        fmsglink = sendMessage(msg, self.bot, self.message) 
                        result = sendMarkup(leechresult, self.bot, self.message, InlineKeyboardMarkup(leechlogbutton.build_menu(1)))
                        Thread(target=auto_delete_message, args=(self.bot, self.message, result)).start()
                else:
                    fmsglink = sendMessage(msg, self.bot, self.message) 
                    result = sendMarkup(leechresult, self.bot, self.message, InlineKeyboardMarkup(leechlogbutton.build_menu(1)))
                    Thread(target=auto_delete_message, args=(self.bot, self.message, result)).start()
                    pass

            else:
                fmsg = ''
                for index, (link, name) in enumerate(files.items(), start=1):
                    fmsg += f"🚩 {index}. <a href='{link}'>{name}</a>\n"
                    if len(fmsg.encode() + msg.encode()) > 4000:
                        if MAKE_OWNER_AND_SUDO_ANONYMOUS:
                            user_id = self.message.from_user.id
                            if (
                            user_id in SUDO_USERS or user_id == OWNER_ID
                            ):
                              LOGGER.info(f'Anonymous owner turned on and Files are Leeched by owner i wont send them on chat ')
                              owner = sendMarkup(ownerleechresult, self.bot, self.message, InlineKeyboardMarkup(ownerleechbutton.build_menu(1)))
                              Thread(target=auto_delete_message, args=(self.bot, self.message, owner)).start()
                              try:
                                  sendMessage(self.message.from_user.id, msg, self.bot, self.message)
                              except:
                                    pass
                            else:
                                 fmsglink = sendMessage(msg + fmsg, self.bot, self.message)
                                 result = sendMarkup(leechresult, self.bot, self.message, InlineKeyboardMarkup(leechlogbutton.build_menu(1)))
                                 Thread(target=auto_delete_message, args=(self.bot, self.message, result)).start()
                                 pass
                        else:
                            fmsglink = sendMessage(msg + fmsg, self.bot, self.message)
                            result = sendMarkup(leechresult, self.bot, self.message, InlineKeyboardMarkup(leechlogbutton.build_menu(1)))
                            Thread(target=auto_delete_message, args=(self.bot, self.message, result)).start()
                            sleep(1)
                            pass
                        fmsg = ''
                if fmsg != '':
                    if MAKE_OWNER_AND_SUDO_ANONYMOUS:
                            user_id = self.message.from_user.id
                            if (
                               user_id in SUDO_USERS or user_id == OWNER_ID
                               ):
                                LOGGER.info(f'Anonymous owner turned on and Files are Leeched by owner i wont send them on chat')
                                owner = sendMarkup(ownerleechresult, self.bot, self.message, InlineKeyboardMarkup(ownerleechbutton.build_menu(1)))
                                Thread(target=auto_delete_message, args=(self.bot, self.message, owner)).start()
                                pass
                                try:
                                  sendMessage(self.message.from_user.id, msg, self.bot, self.message)
                                except:
                                      pass
                            else:
                                fmsglink = sendMessage(msg + fmsg, self.bot, self.message)
                                result = sendMarkup(leechresult, self.bot, self.message, InlineKeyboardMarkup(leechlogbutton.build_menu(1)))
                                Thread(target=auto_delete_message, args=(self.bot, self.message, result)).start()
                                pass
                    else:
                        sendMessage(msg + fmsg, self.bot, self.message)
                        result = sendMarkup(leechresult, self.bot, self.message, InlineKeyboardMarkup(leechlogbutton.build_menu(1)))
                        Thread(target=auto_delete_message, args=(self.bot, self.message, result)).start()
                        pass
            if MIRROR_LOGS:
                if MAKE_OWNER_AND_SUDO_ANONYMOUS:
                    user_id = self.message.from_user.id
                    if (
                        user_id in SUDO_USERS or user_id == OWNER_ID
                        ):
                        LOGGER.info(f'Anonymous owner turned on and Files are Leeched by owner i wont send indexfmsg on mirror logs')
                        pass
                    else:
                        try:
                            inndexmsglink = fmsglink.link
                            sourcelink = messageargs2[1]
                            sourceleechmsg = f"<b>#Leeched</b>\n"
                            sourceleechmsg += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                            sourceleechmsg += f"ㅤㅤ ㅤ <b>«Leeched Info»</b>\n"
                            msg1 = f'\n{logmsg}'
                            msg1 += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                            if sourcelink.startswith('magnet:'):
                                sourceleechbutton = f'http://t.me/share/url?url={sourcelink}'
                            else:
                                sourceleechbutton = f'{sourcelink}'
                            sourcebuttons = ButtonMaker()
                            sourcebuttons.buildbutton("Source", f"{sourceleechbutton}")
                            sourcebuttons.buildbutton("All Files", f"{inndexmsglink}")
                            sourcelinkbutton = InlineKeyboardMarkup(sourcebuttons.build_menu(1))
                            for i in MIRROR_LOGS:
                                bot.sendMessage(i, text=sourceleechmsg + msg1, reply_markup=sourcelinkbutton, parse_mode=ParseMode.HTML)
                        except IndexError:
                            pass
                        if replyto is not None:
                            try:
                                reply_text = replyto.text
                                if is_url(reply_text):
                                    inndexmsglink = fmsglink.link
                                    source_link = reply_text.strip()
                                    sourceleechmsg2 = f"<b>#Leeched</b>\n"
                                    sourceleechmsg2 += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                                    sourceleechmsg2 += f"ㅤㅤ ㅤ <b>«Leeched Info»</b>\n"
                                    msg2 = f'\n{logmsg} '
                                    msg2 += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                                    if source_link.startswith('magnet:'):
                                       sourceleechbutton = f'http://t.me/share/url?url={source_link}'
                                    else:
                                       sourceleechbutton = f'{source_link}'
                                    sourcebuttons = ButtonMaker()
                                    sourcebuttons.buildbutton("Source", f"{sourceleechbutton}")
                                    sourcebuttons.buildbutton("All Files", f"{inndexmsglink}")
                                    sourcelinkbutton2 = InlineKeyboardMarkup(sourcebuttons.build_menu(1))
                                    for i in MIRROR_LOGS:
                                        bot.sendMessage(i, text=sourceleechmsg2 + msg2, reply_markup=sourcelinkbutton2, parse_mode=ParseMode.HTML)
                                        pass
                            except:
                                  for i in MIRROR_LOGS:
                                      inndexmsglink = fmsglink.link
                                      sourcefile_link = self.message.link
                                      sourceleechmsg4 = f"<b>#Leeched</b>\n"
                                      sourceleechmsg4 += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                                      sourceleechmsg4 += f"ㅤㅤ ㅤ <b>«Leeched Info»</b>\n"
                                      msg3 = f'\n{logmsg}'
                                      msg3 += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                                      sourcebuttons = ButtonMaker()
                                      sourcebuttons.buildbutton("Source", f"{sourcefile_link}")
                                      sourcebuttons.buildbutton("All Files", f"{inndexmsglink}")
                                      sourcelinkbutton3 = InlineKeyboardMarkup(sourcebuttons.build_menu(1))
                                      bot.sendMessage(chat_id=i, text=sourceleechmsg4 + msg3, reply_markup=sourcelinkbutton3, parse_mode=ParseMode.HTML)
                                      pass
                else:
                    user_id = self.message.from_user.id
                    inndexmsglink = fmsglink.link
                    try:
                        sourcelink = messageargs2[1]
                        sourceleechmsg = f"<b>#Leeched</b>\n"
                        sourceleechmsg += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                        sourceleechmsg += f"ㅤㅤ ㅤ <b>«Leeched Info»</b>\n"
                        msg1 = f'\n{logmsg}'
                        msg1 += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                        if sourcelink.startswith('magnet:'):
                            sourceleechbutton = f'http://t.me/share/url?url={sourcelink}'
                        else:
                            sourceleechbutton = f'{sourcelink}'
                        sourcebuttons = ButtonMaker()
                        sourcebuttons.buildbutton("Source", f"{sourceleechbutton}")
                        sourcebuttons.buildbutton("All Files", f"{inndexmsglink}")
                        sourcelinkbutton = InlineKeyboardMarkup(sourcebuttons.build_menu(1))
                        for i in MIRROR_LOGS:
                            bot.sendMessage(i, text=sourceleechmsg + msg1, reply_markup=sourcelinkbutton, parse_mode=ParseMode.HTML)
                    except IndexError:
                        pass
                    if replyto is not None:
                            try:
                               reply_text = replyto.text
                               if is_url(reply_text): 
                                  source_link = reply_text.strip()
                                  sourceleechmsg2 = f"<b>#Leeched</b>\n"
                                  sourceleechmsg2 += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                                  sourceleechmsg2 += f"ㅤㅤ ㅤ <b>«Leeched Info»</b>\n"
                                  msg2 = f'\n{logmsg} '
                                  msg2 += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                                  if source_link.startswith('magnet:'):
                                     sourceleechbutton = f'http://t.me/share/url?url={source_link}'
                                  else:
                                     sourceleechbutton = f'{source_link}'
                                  sourcebuttons = ButtonMaker()
                                  sourcebuttons.buildbutton("Source", f"{sourceleechbutton}")
                                  sourcebuttons.buildbutton("All Files", f"{inndexmsglink}")
                                  sourcelinkbutton2 = InlineKeyboardMarkup(sourcebuttons.build_menu(1))
                                  for i in MIRROR_LOGS:
                                      bot.sendMessage(i, text=sourceleechmsg2 + msg2, reply_markup=sourcelinkbutton2, parse_mode=ParseMode.HTML)
                                      pass
                            except:
                                  for i in MIRROR_LOGS:
                                      sourcefile_link = self.message.link
                                      sourceleechmsg4 = f"<b>#Leeched</b>\n"
                                      sourceleechmsg4 += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                                      sourceleechmsg4 += f"ㅤㅤ ㅤ <b>«Leeched Info»</b>\n\n"
                                      sourcebuttons = ButtonMaker()
                                      sourcebuttons.buildbutton("Source", f"{sourcefile_link}")
                                      sourcebuttons.buildbutton("All Files", f"{inndexmsglink}")
                                      sourcelinkbutton3 = InlineKeyboardMarkup(sourcebuttons.build_menu(1))
                                      bot.sendMessage(chat_id=i, text=sourceleechmsg4 + logmsg, reply_markup=sourcelinkbutton3, parse_mode=ParseMode.HTML)
                                      pass
        else:
            msg += f'\n\n<b>Type: </b>{typ}'
            logmsg += f'\n\n<b>Type: </b>{typ}'
            user_id = self.message.from_user.id
            if ospath.isdir(f'{DOWNLOAD_DIR}{self.uid}/{name}'):
                msg += f'\n<b>SubFolders: </b>{folders}'
                logmsg += f'\n<b>SubFolders: </b>{folders}'
                msg += f'\n<b>Files: </b>{files}'
                logmsg += f'\n<b>Files: </b>{files}'
            if MAKE_OWNER_AND_SUDO_ANONYMOUS:
                            user_id = self.message.from_user.id
                            if (
                              user_id in SUDO_USERS or user_id == OWNER_ID
                              ):
                                msg += f'\n\n<b>cc:</b> <b><i><a href="tg://settings/">Anonymous</a></i></b>'
                                logmsg += f'\n\n<b>cc:</b> <b><i><a href="tg://settings/">Anonymous</a></i></b>'
                                pass
                            else:
                                msg += f'\n\n<b>cc: </b>{self.tag}'
                                logmsg += f'\n\n<b>cc:</b> <b><a href="{self.message.link}">{self.message.from_user.first_name}</a></b>' 
                                pass
            else:
                msg += f'\n\n<b>cc: </b>{self.tag}'
                logmsg += f'\n\n<b>cc:</b> <b><a href="{self.message.link}">{self.message.from_user.first_name}</a></b>'

            buttons = ButtonMaker()
            link = short_url(link)
            buttons.buildbutton("☁️ Drive Link", link)
            LOGGER.info(f'Done Uploading {name}')
            if INDEX_URL is not None:
                url_path = rutils.quote(f'{name}')
                share_url = f'{INDEX_URL}/{url_path}'
                if ospath.isdir(f'{DOWNLOAD_DIR}/{self.uid}/{name}'):
                    share_url += '/'
                    share_url = short_url(share_url)
                    buttons.buildbutton("⚡ Index Link", share_url)
                else:
                    share_url = short_url(share_url)
                    buttons.buildbutton("⚡ Index Link", share_url)
                    if VIEW_LINK:
                        share_urls = f'{INDEX_URL}/{url_path}?a=view'
                        share_urls = short_url(share_urls)
                        buttons.buildbutton("🌐 View Link", share_urls)
            if BUTTON_FOUR_NAME is not None and BUTTON_FOUR_URL is not None:
                buttons.buildbutton(f"{BUTTON_FOUR_NAME}", f"{BUTTON_FOUR_URL}")
            if BUTTON_FIVE_NAME is not None and BUTTON_FIVE_URL is not None:
                buttons.buildbutton(f"{BUTTON_FIVE_NAME}", f"{BUTTON_FIVE_URL}")
            if BUTTON_SIX_NAME is not None and BUTTON_SIX_URL is not None:
                buttons.buildbutton(f"{BUTTON_SIX_NAME}", f"{BUTTON_SIX_URL}")

            mesg = self.message.text.split('\n')
            message_args = mesg[0].split(' ', maxsplit=1)
            reply_to = self.message.reply_to_message
            bot_d = bot.get_me()
            bot_username = bot_d.username
            checkbot = f"http://t.me/{bot_username}"

            user_id = self.message.from_user.id
            if user_id == OWNER_ID:
               ownerorsudo = f"Owner"
            else:
               ownerorsudo = f"Sudo User"

            ownerresult = f"<b>Dear {ownerorsudo} I Have Sent Your #Mirrored Link's In Your PM</b>"
            ownerbutton = ButtonMaker()
            ownerbutton.buildbutton("Check Now", checkbot)
            
            if MIRROR_LOGS:
                user_id = self.message.from_user.id
                if MAKE_OWNER_AND_SUDO_ANONYMOUS:
                    if (
                        user_id in SUDO_USERS or user_id == OWNER_ID
                        ):
                        LOGGER.info(f'Anonymous owner turned on and Files are Mirrored by owner i wont send them on mirror logs')
                        pass
                    else:
                        try:
                              sourcelink = message_args[1]
                              sourcemirrormsg = f"<b>#Mirrored</b>\n"
                              sourcemirrormsg += f"\n━━━━━━━━━━━━━━━━━━━━"
                              if sourcelink.startswith('magnet:'):
                                  sourcemirrormsg += f'\n<b>Source Url</b>: <b>Share Magnet To</b> <b><a href="http://t.me/share/url?url={sourcelink}">Telegram</a></b>'
                              else:
                                  sourcemirrormsg += f'\n<b>Source Url</b>: <b><a href="{sourcelink}">Here</a></b>'
                              sourcemirrormsg += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                              sourcemirrormsg += f"ㅤㅤ ㅤ  «<b>Mirrored info</b>»\n"
                              msg1 = f'\n{logmsg} '
                              msg1 += f'\n━━━━━━━━━━━━━━━━━━━━'
                              for i in MIRROR_LOGS:
                                  logmirresult = bot.sendMessage(i, text=sourcemirrormsg + msg1, reply_markup=InlineKeyboardMarkup(buttons.build_menu(2)), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                                  logmirresultlink = f'<a href="{logmirresult.link}">Log group</a>'
                                  mirresult = f"{msg}\n"
                                  mirresult += f"\n<b><i>This message saved in my</i></b> "
                                  mirresult += f"<b><i>{logmirresultlink}</i></b>"
                        except IndexError:
                            pass
                        if reply_to is not None:
                            try:
                                reply_text = reply_to.text
                                if is_url(reply_text):
                                   source_link = reply_text.strip()
                                   sourcemirrormsg2 = f"<b>#Mirrored</b>\n"
                                   sourcemirrormsg2 += f"\n━━━━━━━━━━━━━━━━━━━━"
                                   if source_link.startswith('magnet:'):
                                      sourcemirrormsg2 += f'\n<b>Source Url</b>: <b>Share Magnet To</b> <b><a href="http://t.me/share/url?url={source_link}">Telegram</a></b>'
                                   else:
                                      sourcemirrormsg2 += f'\n<b>Source Url</b>: <b><a href="{source_link}">Here</a></b>'
                                   sourcemirrormsg2 += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                                   sourcemirrormsg2 += f"ㅤㅤ ㅤ  «<b>Mirrored info</b>»\n"
                                   msg2 = f'\n{logmsg} '
                                   msg2 += f'\n━━━━━━━━━━━━━━━━━━━━'
                                   for i in MIRROR_LOGS:
                                       logmirresult = bot.sendMessage(chat_id=i, text=sourcemirrormsg2 + msg2, reply_markup=InlineKeyboardMarkup(buttons.build_menu(2)), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                                       logmirresultlink = f'<a href="{logmirresult.link}">Log group</a>'
                                       mirresult = f"{msg}\n"
                                       mirresult += f"\n<b><i>This message saved in my</i></b> "
                                       mirresult += f"<b><i>{logmirresultlink}</i></b>"
                            except:
                                   for i in MIRROR_LOGS:
                                       sourcefile_link = self.message.link
                                       sourcemirrormsg3 = f"<b>#Mirrored</b>\n"
                                       sourcemirrormsg3 += f"\n━━━━━━━━━━━━━━━━━━━━"
                                       sourcemirrormsg3 += f'\n<b>Source File:</b> <b><a href="{sourcefile_link}">Here</a></b>'
                                       sourcemirrormsg3 += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                                       sourcemirrormsg3 += f"ㅤㅤ ㅤ  «<b>Mirrored info</b>»\n"
                                       msg3 = f'\n{logmsg} '
                                       msg3 += f'\n━━━━━━━━━━━━━━━━━━━━'
                                       logmirresult = bot.sendMessage(chat_id=i, text=sourcemirrormsg3 + msg3, reply_markup=InlineKeyboardMarkup(buttons.build_menu(2)), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                                       logmirresultlink = f'<a href="{logmirresult.link}">Log group</a>'
                                       mirresult = f"{msg}\n"
                                       mirresult += f"\n<b><i>This message saved in my</i></b> "
                                       mirresult += f"<b><i>{logmirresultlink}</i></b>"
                                       pass
                else:
                    user_id = self.message.from_user.id
                    try:
                       sourcelink = message_args[1]
                       sourcemirrormsg = f"<b>#Mirrored</b>\n"
                       sourcemirrormsg += f"\n━━━━━━━━━━━━━━━━━━━━"
                       if sourcelink.startswith('magnet:'):
                           sourcemirrormsg += f'\n<b>Source Url</b>: <b>Share Magnet To</b> <b><a href="http://t.me/share/url?url={sourcelink}">Telegram</a></b>'
                       else:
                           sourcemirrormsg += f'\n<b>Source Url</b>: <b><a href="{sourcelink}">Here</a></b>'
                       sourcemirrormsg += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                       sourcemirrormsg += f"ㅤㅤ ㅤ  «<b>Mirrored info</b>»\n"
                       msg1 = f'\n{logmsg} '
                       msg1 += f'\n━━━━━━━━━━━━━━━━━━━━'
                       for i in MIRROR_LOGS:
                           logmirresult = bot.sendMessage(i, text=sourcemirrormsg + msg1, reply_markup=InlineKeyboardMarkup(buttons.build_menu(2)), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                           logmirresultlink = f'<a href="{logmirresult.link}">Log group</a>'
                           mirresult = f"{msg}\n"
                           mirresult += f"\n<b><i>This message saved in my</i></b> "
                           mirresult += f"<b><i>{logmirresultlink}</i></b>"
                    except IndexError:
                      pass
                    if reply_to is not None:
                        try:
                            reply_text = reply_to.text
                            if is_url(reply_text):
                               source_link = reply_text.strip()
                               sourcemirrormsg2 = f"<b>#Mirrored</b>\n"
                               sourcemirrormsg2 += f"\n━━━━━━━━━━━━━━━━━━━━"
                               if source_link.startswith('magnet:'):
                                  sourcemirrormsg2 += f'\n<b>Source Url</b>: <b>Share Magnet To</b> <b><a href="http://t.me/share/url?url={source_link}">Telegram</a></b>'
                               else:
                                  sourcemirrormsg2 += f'\n<b>Source Url</b>: <b><a href="{source_link}">Here</a></b>'
                               sourcemirrormsg2 += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                               sourcemirrormsg2 += f"ㅤㅤ ㅤ  «<b>Mirrored info</b>»\n"
                               msg2 = f'\n{logmsg} '
                               msg2 += f'\n━━━━━━━━━━━━━━━━━━━━'
                               for i in MIRROR_LOGS:
                                   logmirresult = bot.sendMessage(chat_id=i, text=sourcemirrormsg2 + msg2, reply_markup=InlineKeyboardMarkup(buttons.build_menu(2)), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                                   logmirresultlink = f'<a href="{logmirresult.link}">Log group</a>'
                                   mirresult = f"{msg}\n"
                                   mirresult += f"\n<b><i>This message saved in my</i></b> "
                                   mirresult += f"<b><i>{logmirresultlink}</i></b>"
                        except:
                               for i in MIRROR_LOGS:
                                   sourcefile_link = self.message.link
                                   sourcemirrormsg3 = f"<b>#Mirrored</b>\n"
                                   sourcemirrormsg3 += f"\n━━━━━━━━━━━━━━━━━━━━"
                                   sourcemirrormsg3 += f'\n<b>Source File:</b> <b><a href="{sourcefile_link}">Here</a></b>'
                                   sourcemirrormsg3 += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                                   sourcemirrormsg3 += f"ㅤㅤ ㅤ  «<b>Mirrored info</b>»\n"
                                   msg3 = f'\n{logmsg} '
                                   msg3 += f'\n━━━━━━━━━━━━━━━━━━━━'
                                   logmirresult = bot.sendMessage(chat_id=i, text=sourcemirrormsg3 + msg3, reply_markup=InlineKeyboardMarkup(buttons.build_menu(2)), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                                   logmirresultlink = f'<a href="{logmirresult.link}">Log group</a>'
                                   mirresult = f"{msg}\n"
                                   mirresult += f"\n<b><i>This message saved in my</i></b> "
                                   mirresult += f"<b><i>{logmirresultlink}</i></b>"
                                   pass
                if MAKE_OWNER_AND_SUDO_ANONYMOUS:
                    user_id = self.message.from_user.id
                    if (
                       user_id in SUDO_USERS or user_id == OWNER_ID
                      ):
                        bot.sendMessage(chat_id=self.message.from_user.id, text=msg,
                                                reply_markup=InlineKeyboardMarkup(buttons.build_menu(2)),
                                                parse_mode=ParseMode.HTML)
                        checkpmmsg = sendMarkup(ownerresult, self.bot, self.message, InlineKeyboardMarkup(ownerbutton.build_menu(1)))
                        Thread(target=auto_delete_message, args=(self.bot, self.message, checkpmmsg)).start()
                    else:
                         sendMarkup(mirresult, self.bot, self.message, InlineKeyboardMarkup(buttons.build_menu(2)))
                else:
                    sendMarkup(mirresult, self.bot, self.message, InlineKeyboardMarkup(buttons.build_menu(2)))
            else:
                user_id = self.message.from_user.id
                if MAKE_OWNER_AND_SUDO_ANONYMOUS:
                    if (
                        user_id in SUDO_USERS or user_id == OWNER_ID
                        ):
                         bot.sendMessage(chat_id=self.message.from_user.id, text=msg,
                                                reply_markup=InlineKeyboardMarkup(buttons.build_menu(2)),
                                                parse_mode=ParseMode.HTML)
                         checkpmmsg = sendMarkup(ownerresult, self.bot, self.message, InlineKeyboardMarkup(ownerbutton.build_menu(1)))
                         Thread(target=auto_delete_message, args=(self.bot, self.message, checkpmmsg)).start()
                    else:
                         sendMarkup(msg, self.bot, self.message, InlineKeyboardMarkup(buttons.build_menu(2)))
                else:
                    sendMarkup(msg, self.bot, self.message, InlineKeyboardMarkup(buttons.build_menu(2)))
                    pass

            if self.isQbit and QB_SEED and not self.extract:
                if self.isZip:
                    try:
                        osremove(f'{DOWNLOAD_DIR}{self.uid}/{name}')
                    except:
                        pass
                return
        clean_download(f'{DOWNLOAD_DIR}{self.uid}')
        with download_dict_lock:
            try:
                del download_dict[self.uid]
            except Exception as e:
                LOGGER.error(str(e))
            count = len(download_dict)
        if count == 0:
            self.clean()
        else:
            update_all_messages()

    def onUploadError(self, error):
        e_str = error.replace('<', '').replace('>', '')
        clean_download(f'{DOWNLOAD_DIR}{self.uid}')
        with download_dict_lock:
            try:
                del download_dict[self.uid]
            except Exception as e:
                LOGGER.error(str(e))
            count = len(download_dict)
        sendMessage(f"{self.tag} {e_str}", self.bot, self.message)
        if count == 0:
            self.clean()
        else:
            update_all_messages()

        if not self.isPrivate and INCOMPLETE_TASK_NOTIFIER and DB_URI is not None:
            DbManger().rm_complete_task(self.message.link)

def _mirror(bot, message, isZip=False, extract=False, isQbit=False, isLeech=False, pswd=None, multi=0):
    uname = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>'
    tasks = len(download_dict)
    user_id = message.from_user.id

    if user_id == OWNER_ID:
        ownerorsudo = f"Owner"
    else:
        ownerorsudo = f"Sudo User"

    bot_d = bot.get_me()
    bot_username = bot_d.username
    length_of_leechlog = len(LEECH_LOG)
    
    if ACTIVE_TASK_LIMIT is not None:
        if tasks == ACTIVE_TASK_LIMIT or tasks > ACTIVE_TASK_LIMIT:
            if OWNER_ID != user_id and user_id not in SUDO_USERS:
                   if isLeech:
                       leechormirror = "Leech"
                   else:
                       leechormirror = "Mirror"
                   msg2 = f"{uname}\n\n<b>You Can't #{leechormirror} Now\nBecause Max Tasks Limit Is</b> <b><i>{ACTIVE_TASK_LIMIT}</i></b>\n\n<b>Try Later</b>"
                   sendmsg = sendMessage(msg2, bot, message)
                   Thread(target=auto_delete_message, args=(bot, message, sendmsg)).start()
                   return
            else:
                 msg4 =  f"{ownerorsudo} detected Task Limit won't effect them."
                 sendmsg = sendMessage(msg4, bot, message)
                 Thread(target=auto_delete_message, args=(bot, message, sendmsg)).start()
                 pass

    if isLeech and length_of_leechlog == 0:
        try:
            text = "<b>Leech Functionality will not work\nLeech Log var is empty.</b>\n"
            msg = sendMessage(text, bot, message)
            LOGGER.error("Leech Log var is Empty\nKindly add Chat id in Leech log to use Leech Functionality\n")
            Thread(target=auto_delete_message, args=(bot, message, msg)).start()
            return
        except Exception as err:
            LOGGER.error(f"Error:\n{err}")
            pass
    if LEECH_PM and isLeech:
        try:
           msg1 = f'Testing if you Started me or not\n'
           send = bot.sendMessage(message.from_user.id, text=msg1, )
           send.delete()
        except Exception as e:
            LOGGER.warning(e)
            startmsg = f"<b>{uname}</b>,\n\n<b>I found that you haven't started me in PM (Private Chat) yet.</b>\n\n<b><i>if you won't start me then i can't send you #Leeched files in your pm</i></b>\n\n<b><i>Start Me And Try Again</i></b>"
            startbutton = f"http://t.me/{bot_username}"
            button = ButtonMaker()
            button.buildbutton("Start Me", startbutton)
            sendmsg = sendMarkup(startmsg, bot, message, InlineKeyboardMarkup(button.build_menu(1)))
            Thread(target=auto_delete_message, args=(bot, message, sendmsg)).start()
            return
    else:
        pass

    if MAKE_OWNER_AND_SUDO_ANONYMOUS:
        if (user_id in SUDO_USERS or user_id == OWNER_ID):
             try:
                 msg1 = f'.\n'
                 send = bot.sendMessage(message.from_user.id, text=msg1,)
                 send.delete()
             except Exception as e:
                  LOGGER.warning(e)
 
                  startmsg = f"<b>Dear {ownerorsudo}</b>,\n\n<b>I found that you haven't started me in PM (Private Chat) yet.</b>\n\n<b>if you won't start me then i can't send you mirrored files in your pm</b>"
                  startbutton = f"http://t.me/{bot_username}"
                  button = ButtonMaker()
                  button.buildbutton("Start Me", startbutton)
                  sendmsg = sendMarkup(str(startmsg, bot, message, InlineKeyboardMarkup(button.build_menu(1))))
                  Thread(target=auto_delete_message, args=(bot, message, sendmsg)).start()
                  return
        else:
            pass

    if FSUB:
        try:
            user = bot.get_chat_member(f"{FSUB_CHANNEL_ID}", message.from_user.id)
            LOGGER.error(user.status)
            if user.status not in ('member', 'creator', 'administrator'):
                buttons = ButtonMaker()
                buttons.buildbutton("Updates Channel", f"{FSUB_CHANNELLINK}")
                reply_markup = InlineKeyboardMarkup(buttons.build_menu(1))
                mess = sendMarkup(
                    str(f"<b>{uname}</b> \n<b>You Think you can use without joining my updates channel?.</b>\n<b>Leave This group if you can't even subscribe a channel,</b>\n<b>We providing you mirror things for free and what you can't even subscribe our update channel.</b>\n\n<b>Subscribe channel to use me.</b>"),
                    bot, message, reply_markup)
                Thread(target=auto_delete_message, args=(bot, message, mess)).start()
                return
        except:
            pass

    mesg = message.text.split('\n')
    message_args = mesg[0].split(' ', maxsplit=1)
    name_args = mesg[0].split('|', maxsplit=1)
    qbitsel = False
    is_gdtot = False
    try:
        link = message_args[1]
        if link.startswith("s ") or link == "s":
            qbitsel = True
            message_args = mesg[0].split(' ', maxsplit=2)
            link = message_args[2].strip()
        elif link.isdigit():
            multi = int(link)
            raise IndexError
        if link.startswith(("|", "pswd: ")):
            raise IndexError
    except:
        link = ''
    try:
        name = name_args[1]
        name = name.split(' pswd: ')[0]
        name = name.strip()
    except:
        name = ''
    link = re_split(r"pswd:| \|", link)[0]
    link = link.strip()
    pswdMsg = mesg[0].split(' pswd: ')
    if len(pswdMsg) > 1:
        pswd = pswdMsg[1]

    if message.from_user.username:
        tag = f"@{message.from_user.username}"
    else:
        tag = message.from_user.mention_html(message.from_user.first_name)

    reply_to = message.reply_to_message
    if reply_to is not None:
        file = None
        media_array = [reply_to.document, reply_to.video, reply_to.audio]
        for i in media_array:
            if i is not None:
                file = i
                break

        if not reply_to.from_user.is_bot:
            if reply_to.from_user.username:
                tag = f"@{reply_to.from_user.username}"
            else:
                tag = reply_to.from_user.mention_html(reply_to.from_user.first_name)

        if not is_url(link) and not is_magnet(link) or len(link) == 0:
            if file is None:
                reply_text = reply_to.text
                if is_url(reply_text) or is_magnet(reply_text):
                    link = reply_text.strip()
            elif file.mime_type != "application/x-bittorrent" and not isQbit:
                listener = MirrorListener(bot, message, isZip, extract, isQbit, isLeech, pswd, tag)
                Thread(target=TelegramDownloadHelper(listener).add_download, args=(message, f'{DOWNLOAD_DIR}{listener.uid}/', name)).start()
                if multi > 1:
                    sleep(4)
                    nextmsg = type('nextmsg', (object, ), {'chat_id': message.chat_id, 'message_id': message.reply_to_message.message_id + 1})
                    nextmsg = sendMessage(message_args[0], bot, nextmsg)
                    nextmsg.from_user.id = message.from_user.id
                    multi -= 1
                    sleep(4)
                    Thread(target=_mirror, args=(bot, nextmsg, isZip, extract, isQbit, isLeech, pswd, multi)).start()
                return
            else:
                link = file.get_file().file_path

    if not is_url(link) and not is_magnet(link) and not ospath.exists(link):
        help_msg = "<b>Send link along with command line:</b>"
        help_msg += "\n<code>/command</code> {link} |newname pswd: xx [zip/unzip]"
        help_msg += "\n\n<b>By replying to link or file:</b>"
        help_msg += "\n<code>/command</code> |newname pswd: xx [zip/unzip]"
        help_msg += "\n\n<b>Direct link authorization:</b>"
        help_msg += "\n<code>/command</code> {link} |newname pswd: xx\nusername\npassword"
        help_msg += "\n\n<b>Qbittorrent selection:</b>"
        help_msg += "\n<code>/qbcommand</code> <b>s</b> {link} or by replying to {file/link}"
        help_msg += "\n\n<b>Multi links only by replying to first link or file:</b>"
        help_msg += "\n<code>/command</code> 10(number of links/files)"
        return sendMessage(help_msg, bot, message)

    LOGGER.info(link)

    if not is_mega_link(link) and not isQbit and not is_magnet(link) \
        and not is_gdrive_link(link) and not link.endswith('.torrent'):
        content_type = get_content_type(link)
        if content_type is None or re_match(r'text/html|text/plain', content_type):
            try:
                is_gdtot = is_gdtot_link(link)
                link = direct_link_generator(link)
                LOGGER.info(f"Generated link: {link}")
            except DirectDownloadLinkException as e:
                LOGGER.info(str(e))
                if str(e).startswith('ERROR:'):
                    return sendMessage(str(e), bot, message)
    elif isQbit and not is_magnet(link) and not ospath.exists(link):
        if link.endswith('.torrent') or "https://api.telegram.org/file/" in link:
            content_type = None
        else:
            content_type = get_content_type(link)
        if content_type is None or re_match(r'application/x-bittorrent|application/octet-stream', content_type):
            try:
                resp = rget(link, timeout=10, headers = {'user-agent': 'Wget/1.12'})
                if resp.status_code == 200:
                    file_name = str(time()).replace(".", "") + ".torrent"
                    with open(file_name, "wb") as t:
                        t.write(resp.content)
                    link = str(file_name)
                else:
                    return sendMessage(f"{tag} ERROR: link got HTTP response: {resp.status_code}", bot, message)
            except Exception as e:
                error = str(e).replace('<', ' ').replace('>', ' ')
                if error.startswith('No connection adapters were found for'):
                    link = error.split("'")[1]
                else:
                    LOGGER.error(str(e))
                    return sendMessage(tag + " " + error, bot, message)
        else:
            msg = "Qb commands for torrents only. if you are trying to dowload torrent then report."
            return sendMessage(msg, bot, message)


    listener = MirrorListener(bot, message, isZip, extract, isQbit, isLeech, pswd, tag)

    if is_gdrive_link(link):
        if not isZip and not extract and not isLeech:
            gmsg = f"Use /{BotCommands.CloneCommand} to clone Google Drive file/folder\n\n"
            gmsg += f"Use /{BotCommands.ZipMirrorCommand} to make zip of Google Drive folder\n\n"
            gmsg += f"Use /{BotCommands.UnzipMirrorCommand} to extracts Google Drive archive file"
            sendMessage(gmsg, bot, message)
        else:
            Thread(target=add_gd_download, args=(link, listener, is_gdtot)).start()
    elif is_mega_link(link):
        if MEGAREST:
            mega_dl = MegaDownloadeHelper(listener).add_download
        else:
            mega_dl = add_mega_download
        Thread(target=mega_dl, args=(link, f'{DOWNLOAD_DIR}{listener.uid}/', listener)).start()
    elif isQbit and (is_magnet(link) or ospath.exists(link)):
        Thread(target=QbDownloader(listener).add_qb_torrent, args=(link, f'{DOWNLOAD_DIR}{listener.uid}', qbitsel)).start()
    else:
        if len(mesg) > 1:
            try:
                ussr = mesg[1]
            except:
                ussr = ''
            try:
                pssw = mesg[2]
            except:
                pssw = ''
            auth = f"{ussr}:{pssw}"
            auth = "Basic " + b64encode(auth.encode()).decode('ascii')
        else:
            auth = ''
        Thread(target=add_aria2c_download, args=(link, f'{DOWNLOAD_DIR}{listener.uid}', listener, name, auth)).start()

    if multi > 1:
        sleep(4)
        nextmsg = type('nextmsg', (object, ), {'chat_id': message.chat_id, 'message_id': message.reply_to_message.message_id + 1})
        msg = message_args[0]
        if len(mesg) > 2:
            msg += '\n' + mesg[1] + '\n' + mesg[2]
        nextmsg = sendMessage(msg, bot, nextmsg)
        nextmsg.from_user.id = message.from_user.id
        multi -= 1
        sleep(4)
        Thread(target=_mirror, args=(bot, nextmsg, isZip, extract, isQbit, isLeech, pswd, multi)).start()


def mirror(update, context):
    _mirror(context.bot, update.message)

def unzip_mirror(update, context):
    _mirror(context.bot, update.message, extract=True)

def zip_mirror(update, context):
    _mirror(context.bot, update.message, True)

def qb_mirror(update, context):
    _mirror(context.bot, update.message, isQbit=True)

def qb_unzip_mirror(update, context):
    _mirror(context.bot, update.message, extract=True, isQbit=True)

def qb_zip_mirror(update, context):
    _mirror(context.bot, update.message, True, isQbit=True)

def leech(update, context):
    _mirror(context.bot, update.message, isLeech=True)

def unzip_leech(update, context):
    _mirror(context.bot, update.message, extract=True, isLeech=True)

def zip_leech(update, context):
    _mirror(context.bot, update.message, True, isLeech=True)

def qb_leech(update, context):
    _mirror(context.bot, update.message, isQbit=True, isLeech=True)

def qb_unzip_leech(update, context):
    _mirror(context.bot, update.message, extract=True, isQbit=True, isLeech=True)

def qb_zip_leech(update, context):
    _mirror(context.bot, update.message, True, isQbit=True, isLeech=True)

if SUDO_ONLY_MIRROR:
   allow_mirror = CustomFilters.owner_filter | CustomFilters.sudo_user
else:
   allow_mirror = CustomFilters.authorized_chat | CustomFilters.authorized_user

if SUDO_ONLY_LEECH:
    allow_leech = CustomFilters.owner_filter | CustomFilters.sudo_user
else:
    allow_leech = CustomFilters.authorized_chat | CustomFilters.authorized_user

mirror_handler = CommandHandler(BotCommands.MirrorCommand, mirror,
                                filters=allow_mirror, run_async=True)
unzip_mirror_handler = CommandHandler(BotCommands.UnzipMirrorCommand, unzip_mirror,
                                filters=allow_mirror, run_async=True)
zip_mirror_handler = CommandHandler(BotCommands.ZipMirrorCommand, zip_mirror,
                                filters=allow_mirror, run_async=True)
qb_mirror_handler = CommandHandler(BotCommands.QbMirrorCommand, qb_mirror,
                                filters=allow_mirror, run_async=True)
qb_unzip_mirror_handler = CommandHandler(BotCommands.QbUnzipMirrorCommand, qb_unzip_mirror,
                                filters=allow_mirror, run_async=True)
qb_zip_mirror_handler = CommandHandler(BotCommands.QbZipMirrorCommand, qb_zip_mirror,
                                filters=allow_mirror, run_async=True)
leech_handler = CommandHandler(BotCommands.LeechCommand, leech,
                                filters=allow_leech, run_async=True)
unzip_leech_handler = CommandHandler(BotCommands.UnzipLeechCommand, unzip_leech,
                                filters=allow_leech, run_async=True)
zip_leech_handler = CommandHandler(BotCommands.ZipLeechCommand, zip_leech,
                                filters=allow_leech, run_async=True)
qb_leech_handler = CommandHandler(BotCommands.QbLeechCommand, qb_leech,
                                filters=allow_leech, run_async=True)
qb_unzip_leech_handler = CommandHandler(BotCommands.QbUnzipLeechCommand, qb_unzip_leech,
                                filters=allow_leech, run_async=True)
qb_zip_leech_handler = CommandHandler(BotCommands.QbZipLeechCommand, qb_zip_leech,
                                filters=allow_leech, run_async=True)

dispatcher.add_handler(mirror_handler)
dispatcher.add_handler(unzip_mirror_handler)
dispatcher.add_handler(zip_mirror_handler)
dispatcher.add_handler(qb_mirror_handler)
dispatcher.add_handler(qb_unzip_mirror_handler)
dispatcher.add_handler(qb_zip_mirror_handler)
dispatcher.add_handler(leech_handler)
dispatcher.add_handler(unzip_leech_handler)
dispatcher.add_handler(zip_leech_handler)
dispatcher.add_handler(qb_leech_handler)
dispatcher.add_handler(qb_unzip_leech_handler)
dispatcher.add_handler(qb_zip_leech_handler)
