from random import SystemRandom
from string import ascii_letters, digits
from telegram.ext import CommandHandler
from threading import Thread
from time import sleep
from telegram import InlineKeyboardMarkup, ParseMode, InlineKeyboardButton
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, deleteMessage, delete_all_messages, update_all_messages, sendStatusMessage, auto_delete_message
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.mirror_utils.status_utils.clone_status import CloneStatus
from bot import bot, dispatcher, LOGGER, CLONE_LIMIT, STOP_DUPLICATE, download_dict, download_dict_lock, Interval, MIRROR_LOGS, FSUB_CHANNEL_ID,\
    FSUB, FSUB_CHANNELLINK, MAKE_OWNER_AND_SUDO_ANONYMOUS,  OWNER_ID, SUDO_USERS, SUDO_ONLY_MIRROR , ACTIVE_TASK_LIMIT
from bot.helper.ext_utils.bot_utils import get_readable_file_size,is_url, is_gdrive_link, is_gdtot_link, new_thread
from bot.helper.mirror_utils.download_utils.direct_link_generator import (
    appdrive,
    drivebuzz_dl,
    drivefire_dl,
    gadrive_dl,
    gdtot,
    hubdrive_dl,
    jiodrive_dl,
    katdrive_dl,
    kolop_dl,
    sharerpw_dl,
)
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException
from telegram import ParseMode

def _clone(message, bot, multi=0):

    uname = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>'
    tasks = len(download_dict)
    user_id = message.from_user.id

    if user_id == OWNER_ID:
        ownerorsudo = f"Owner"
    else:
        ownerorsudo = f"Sudo User"

    if ACTIVE_TASK_LIMIT is not None:
        if tasks == ACTIVE_TASK_LIMIT or tasks > ACTIVE_TASK_LIMIT:
            if OWNER_ID != user_id and user_id not in SUDO_USERS:
                   msg2 = f"{uname}\n\n<b>You Can't #Clone Now\nBecause Max Tasks Limit Is</b> <b><i>{ACTIVE_TASK_LIMIT}</i></b>\n\n<b>Try Later</b>"
                   sendmsg = sendMessage(msg2, bot, message)
                   Thread(target=auto_delete_message, args=(bot, message, sendmsg)).start()
                   return
            else:
                 msg4 =  f"{ownerorsudo} detected Task Limit won't effect them."
                 sendmsg = sendMessage(msg4, bot, message)
                 Thread(target=auto_delete_message, args=(bot, message, sendmsg)).start()
                 pass

    if MAKE_OWNER_AND_SUDO_ANONYMOUS:
        user_id = message.from_user.id
        if (user_id in SUDO_USERS or user_id == OWNER_ID):
             try:
                 msg1 = f'.\n'
                 send = bot.sendMessage(message.from_user.id, text=msg1, )
                 send.delete()
             except Exception as e:
                  LOGGER.warning(e)
                  bot_d = bot.get_me()
                  bot_username = bot_d.username
                  startmsg = f"<b>Dear {ownerorsudo} </b>,\n\n<b>I found that you haven't started me in PM (Private Chat) yet.</b>\n\n<b>if you won't start me then i can't send you mirrored files in your pm</b>"
                  startbutton = f"http://t.me/{bot_username}"
                  button = ButtonMaker()
                  button.buildbutton("Start Me", startbutton)
                  sendmsg = sendMarkup(startmsg, bot, message, InlineKeyboardMarkup(button.build_menu(1)))
                  Thread(target=auto_delete_message, args=(bot, message, sendmsg)).start()
                  return
        else:
            pass
    if FSUB:
        try:
            uname = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>'
            user = bot.get_chat_member(f"{FSUB_CHANNEL_ID}", message.from_user.id)
            LOGGER.error(user.status)
            if user.status not in ('member', 'creator', 'administrator'):
                buttons = ButtonMaker()
                buttons.buildbutton("Join updates Channel", f"{FSUB_CHANNELLINK}")
                reply_markup = InlineKeyboardMarkup(buttons.build_menu(1))
                mess = sendMarkup(str(f"<b>{uname}</b> \n<b>You Think you can use without joining my updates channel?.</b>\n<b>Leave This group if you can't even subscribe a channel,</b>\n<b>We providing you mirror things for free and what you can't even subscribe our  channel.</b>\n\n<b>Subscribe channel to use me.</b>"), bot, message, reply_markup)
                Thread(target=auto_delete_message, args=(bot, mess)).start()
                return
        except:
            pass
    args = message.text.split(" ", maxsplit=1)
    reply_to = message.reply_to_message
    link = ''
    if len(args) > 1:
        link = args[1]
        if link.isdigit():
            multi = int(link)
            link = ''
        elif message.from_user.username:
            tag = f"@{message.from_user.username}"
        else:
            tag = message.from_user.mention_html(message.from_user.first_name)
    if reply_to is not None:
        if len(link) == 0:
            link = reply_to.text
        if reply_to.from_user.username:
            tag = f"@{reply_to.from_user.username}"
        else:
            tag = reply_to.from_user.mention_html(reply_to.from_user.first_name)
    is_gdtot = is_gdtot_link(link)
    is_driveapp = True if "driveapp" in link else False
    is_appdrive = True if "appdrive" in link else False
    is_hubdrive = True if "hubdrive" in link else False
    is_drivehub = True if "drivehub" in link else False
    is_kolop = True if "kolop" in link else False
    is_drivebuzz = True if "drivebuzz" in link else False
    is_gdflix = True if "gdflix" in link else False
    is_drivesharer = True if "drivesharer" in link else False
    is_drivebit = True if "drivebit" in link else False
    is_drivelink = True if "drivelink" in link else False
    is_driveace = True if "driveace" in link else False
    is_drivepro = True if "drivepro" in link else False
    is_katdrive = True if "katdrive" in link else False
    is_gadrive = True if "gadrive" in link else False
    is_jiodrive = True if "jiodrive" in link else False
    is_drivefire = True if "drivefire" in link else False
    is_sharerpw = True if "sharer.pw" in link else False

    if is_driveapp:
        try:
            msg = sendMessage(
                f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐃𝐫𝐢𝐯𝐞𝐀𝐩𝐩: <code>{link}</code>", bot, message)
            link = appdrive(link)
            deleteMessage(bot, msg)
            if not is_gdrive_link(link):
                return sendMessage("GDrive Link Not Found", bot, message)
            else:
                pass
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)
    if is_hubdrive:
        try:
            msg = sendMessage(
                f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐇𝐮𝐛𝐃𝐫𝐢𝐯𝐞: <code>{link}</code>", bot, message)
            link = hubdrive_dl(link)
            deleteMessage(bot, msg)
            if not is_gdrive_link(link):
                return sendMessage("GDrive Link Not Found", bot, message)
            else:
                pass
        except DirectDownloadLinkException as e:

            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)
    if is_drivehub:
        try:
            msg = sendMessage(
                f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐃𝐫𝐢𝐯𝐞𝐇𝐮𝐛: <code>{link}</code>", bot, message)
            link = appdrive(link)
            deleteMessage(bot, msg)
            if not is_gdrive_link(link):
                return sendMessage("GDrive Link Not Found", bot, message)
            else:
                pass
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)
    if is_kolop:
        try:
            msg = sendMessage(
                f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐊𝐨𝐥𝐨𝐩: <code>{link}</code>", bot, message)
            link = kolop_dl(link)
            deleteMessage(bot, msg)
            if not is_gdrive_link(link):
                return sendMessage("GDrive Link Not Found", bot, message)
            else:
                pass
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e),  bot, message)
    if is_drivebuzz:
        try:
            msg = sendMessage(
                f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐃𝐫𝐢𝐯𝐞𝐁𝐮𝐳𝐳: <code>{link}</code>", bot, message)
            link = drivebuzz_dl(link)
            deleteMessage(bot, msg)
            if not is_gdrive_link(link):
                return sendMessage("GDrive Link Not Found", bot, message)
            else:
                pass
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)
        
    if is_gdflix:
        try:
            msg = sendMessage(
                f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐆𝐃𝐅𝐥𝐢𝐱: <code>{link}</code>",  bot, message)
            link = appdrive(link)
            deleteMessage(bot, msg)
            if not is_gdrive_link(link):
                return sendMessage("GDrive Link Not Found",  bot, message)
            else:
                pass
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e),  bot, message)

    if is_drivebit:
        try:
            msg = sendMessage(
                f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐃𝐫𝐢𝐯𝐞𝐁𝐢𝐭: <code>{link}</code>", bot, message
            )
            link = appdrive(link)
            deleteMessage(bot, msg)
            if not is_gdrive_link(link):
                return sendMessage("GDrive Link Not Found", bot, message)
            else:
                pass
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)
    if is_drivelink:
        try:
            msg = sendMessage(
                f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐃𝐫𝐢𝐯𝐞𝐋𝐢𝐧𝐤: <code>{link}</code>",
                bot, message)
            link = appdrive(link)
            deleteMessage(bot, msg)
            if not is_gdrive_link(link):
                return sendMessage("GDrive Link Not Found", bot, message)
            else:
                pass
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)
    if is_driveace:
        try:
            msg = sendMessage(
                f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐃𝐫𝐢𝐯𝐞𝐚𝐜𝐞: <code>{link}</code>", bot, message)
            link = appdrive(link)
            deleteMessage(bot, msg)
            if not is_gdrive_link(link):
                return sendMessage("GDrive Link Not Found", bot, message)
            else:
                pass
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)
    if is_drivepro:
        try:
            msg = sendMessage(
                f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐃𝐫𝐢𝐯𝐞𝐏𝐫𝐨: <code>{link}</code>", bot, message)
            link = appdrive(link)
            deleteMessage(bot, msg)
            if not is_gdrive_link(link):
                return sendMessage("GDrive Link Not Found", bot, message)
            else:
                pass
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)
    if is_katdrive:
        try:
            msg = sendMessage(
                f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐊𝐚𝐭𝐃𝐫𝐢𝐯𝐞: <code>{link}</code>", bot, message)
            link = katdrive_dl(link)
            deleteMessage(bot, msg)
            if not is_gdrive_link(link):
                return sendMessage("GDrive Link Not Found", bot, message)
            else:
                pass
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)
    if is_gadrive:
        try:
            msg = sendMessage(
                f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐆𝐚𝐃𝐫𝐢𝐯𝐞: <code>{link}</code>", bot, message)
            link = gadrive_dl(link)
            deleteMessage(bot, msg)
            if not is_gdrive_link(link):
                return sendMessage("GDrive Link Not Found", bot, message)
            else:
                pass
        except DirectDownloadLinkException as e:

            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)
    if is_jiodrive:
        try:
            msg = sendMessage(
                f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐉𝐢𝐨𝐃𝐫𝐢𝐯𝐞: <code>{link}</code>", bot, message)
            link = jiodrive_dl(link)
            deleteMessage(bot, msg)
            if not is_gdrive_link(link):
                return sendMessage("GDrive Link Not Found", bot, message)
            else:
                pass
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)
    if is_drivefire:
        try:
            msg = sendMessage(
                f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐃𝐫𝐢𝐯𝐞𝐅𝐢𝐫𝐞: <code>{link}</code>", bot, message)
            link = drivefire_dl(link)
            deleteMessage(bot, msg)
            if not is_gdrive_link(link):
                return sendMessage("GDrive Link Not Found", bot, message)
            else:
                pass
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)
    if is_sharerpw:
        try:
            msg = sendMessage(
                f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐒𝐡𝐚𝐫𝐞𝐫𝐏𝐖: <code>{link}</code>", bot, message)
            link = sharerpw_dl(link)
            deleteMessage(bot, msg)
            if not is_gdrive_link(link):
                return sendMessage("GDrive Link Not Found", bot, message)
            else:
                pass
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)

    if is_gdtot:
        try:
            msg = sendMessage(f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐆𝐃𝐓𝐎𝐓: <code>{link}</code>", bot, message)
            link = gdtot(link)
            deleteMessage(bot, msg)
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)
    if is_appdrive:
        try:
            msg = sendMessage(
                f"⚙️ 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐀𝐩𝐩𝐃𝐫𝐢𝐯𝐞: <code>{link}</code>", bot, message)
            link = appdrive(link)
            deleteMessage(bot, msg)
            if not is_gdrive_link(link):
                return sendMessage("GDrive Link Not Found", bot, message)
            else:
                pass
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)
    if is_gdrive_link(link):
        gd = GoogleDriveHelper()
        res, size, name, files = gd.helper(link)
        if res != "":
            return sendMessage(res, bot, message)
        if STOP_DUPLICATE:
            LOGGER.info('Checking File/Folder if already in Drive...')
            smsg, button = gd.drive_list(name, True, True)
            if smsg:
                msg3 = "File/Folder is already available in Drive.\nHere are the search results:"
                return sendMarkup(msg3, bot, message, button)
        if CLONE_LIMIT is not None:
            LOGGER.info('Checking File/Folder Size...')
            if size > CLONE_LIMIT * 1024**3:
                msg2 = f'Failed, Clone limit is {CLONE_LIMIT}GB.\nYour File/Folder size is {get_readable_file_size(size)}.'
                return sendMessage(msg2, bot, message)
        if multi > 1:
            sleep(4)
            nextmsg = type('nextmsg', (object, ), {'chat_id': message.chat_id, 'message_id': message.reply_to_message.message_id + 1})
            nextmsg = sendMessage(args[0], bot, nextmsg)
            nextmsg.from_user.id = message.from_user.id
            multi -= 1
            sleep(4)
            Thread(target=_clone, args=(nextmsg, bot, multi)).start()
        if files <= 20:
            msg = sendMessage(f"⚙️ 𝐂𝐥𝐨𝐧𝐢𝐧𝐠: <code>{link}</code>", bot, message)
            result, button = gd.clone(link)
            deleteMessage(bot, msg)
        else:
            drive = GoogleDriveHelper(name)
            gid = ''.join(SystemRandom().choices(ascii_letters + digits, k=12))
            clone_status = CloneStatus(drive, size, message, gid)
            with download_dict_lock:
                download_dict[message.message_id] = clone_status
            sendStatusMessage(message, bot)
            result, button = drive.clone(link)
            with download_dict_lock:
                del download_dict[message.message_id]
                count = len(download_dict)
            try:
                if count == 0:
                    Interval[0].cancel()
                    del Interval[0]
                    delete_all_messages()
                else:
                    update_all_messages()
            except IndexError:
                pass
        if MAKE_OWNER_AND_SUDO_ANONYMOUS:
                    if (
                        message.from_user.id != OWNER_ID
                        ):
                        cc = f'\n\n<b>cc: </b>{tag}'
                        logmsg = f'\n\n<b>cc:</b> <b><a href="{message.link}">{message.from_user.first_name}</a></b>'
                    else:
                         cc = f'\n\n<b>cc:</b> <b><i><a href="tg://settings/">Anonymous</a></i></b>'
                         logmsg = f'\n\n<b>cc:</b> <b><i><a href="tg://settings/">Anonymous</a></i></b>'
        else:
            cc = f'\n\n<b>cc: </b>{tag}'
            logmsg = f'\n\n<b>cc:</b> <b><a href="{message.link}">{message.from_user.first_name}</a></b>'
         # Clone Logs
        mesg = message.text.split('\n')
        message_args = mesg[0].split(' ', maxsplit=1)
        if MIRROR_LOGS:
            if MAKE_OWNER_AND_SUDO_ANONYMOUS:
                    user_id = message.from_user.id
                    if (
                        user_id in SUDO_USERS or user_id == OWNER_ID
                        ):
                        LOGGER.info(f'Anonymous owner turned on and Files are Cloned by owner i wont send them on mirror logs')
                    else:
                        try:
                             source_link = message_args[1]
                             reply_to = message.reply_to_message
                             sourceclonemsg = f"<b>#Cloned</b>\n"
                             sourceclonemsg += f"\n━━━━━━━━━━━━━━━━━━━━"
                             sourceclonemsg += f'\n<b>Source Url</b>: <b><a href="{source_link}">Here</a></b>'
                             sourceclonemsg += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                             sourceclonemsg += f"ㅤㅤ ㅤ   <b>«Cloned info»</b>\n"
                             msg1 = f'\n{result} '
                             msg1 += f'{logmsg}\n━━━━━━━━━━━━━━━━━━━━'
                             for i in MIRROR_LOGS:
                                   clonelogmsg = bot.sendMessage(i, text=sourceclonemsg + msg1, reply_markup=button, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                                   logclonesultlink = f'<a href="{clonelogmsg.link}">Log group</a>'
                                   cloneresult = f"\n\n<b><i>This message saved in my</i></b> "
                                   cloneresult += f"<b><i>{logclonesultlink}</i></b>"
                        except IndexError:
                            pass
                             
                        if reply_to is not None:
                            try:
                                reply_text = reply_to.text
                                if is_url(reply_text):
                                    sourcelink = reply_text.strip()
                                    sourceclonemsg2 = f'<b>#Cloned</b>\n'
                                    sourceclonemsg2 += f"━━━━━━━━━━━━━━━━━━━━"
                                    sourceclonemsg2 += f'\n<b>Source Url</b>: <b><a href="{sourcelink}">Here</a></b>'
                                    sourceclonemsg2 += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                                    sourceclonemsg2 += f"ㅤㅤ ㅤ   <b>«Cloned info»</b>\n"
                                    msg2 = f'\n{result} '
                                    msg2 += f'{logmsg}\n━━━━━━━━━━━━━━━━━━━━'
                                    for i in MIRROR_LOGS:
                                        clonelogmsg = bot.sendMessage(chat_id=i, text=sourceclonemsg2 + msg2 , reply_markup=button, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                                        logclonesultlink = f'<a href="{clonelogmsg.link}">Log group</a>'
                                        cloneresult = f"\n\n<b><i>This message saved in my</i></b> "
                                        cloneresult += f"<b><i>{logclonesultlink}</i></b>"
                            except TypeError:
                                pass
            else:
                try:
                    source_link = message_args[1]
                    reply_to = message.reply_to_message
                    sourceclonemsg = f"<b>#Cloned</b>\n"
                    sourceclonemsg += f"\n━━━━━━━━━━━━━━━━━━━━"
                    sourceclonemsg += f'\n<b>Source Url</b>: <b><a href="{source_link}">Here</a></b>'
                    sourceclonemsg += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                    sourceclonemsg += f"ㅤㅤ ㅤ   <b>«Cloned info»</b>\n"
                    msg1 = f'\n{result} '
                    msg1 += f'{logmsg}\n━━━━━━━━━━━━━━━━━━━━'
                    for i in MIRROR_LOGS:
                        clonelogmsg = bot.sendMessage(i, text=sourceclonemsg + msg1, reply_markup=button, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                        logclonesultlink = f'<a href="{clonelogmsg.link}">Log group</a>'
                        cloneresult = f"\n\n<b><i>This message saved in my</i></b> "
                        cloneresult += f"<b><i>{logclonesultlink}</i></b>"
                except IndexError:
                   pass
                if reply_to is not None:
                    try:
                        reply_text = reply_to.text
                        if is_url(reply_text):
                            sourcelink = reply_text.strip()
                            sourceclonemsg2 = f'<b>#Cloned</b>\n'
                            sourceclonemsg2 += f"━━━━━━━━━━━━━━━━━━━━"
                            sourceclonemsg2 += f'\n<b>Source Url</b>: <b><a href="{sourcelink}">Here</a></b>'
                            sourceclonemsg2 += f"\n━━━━━━━━━━━━━━━━━━━━\n"
                            sourceclonemsg2 += f"ㅤㅤ ㅤ   <b>«Cloned info»</b>\n"
                            msg2 = f'\n{result} '
                            msg2 += f'{logmsg}\n━━━━━━━━━━━━━━━━━━━━'
                            for i in MIRROR_LOGS:
                                clonelogmsg = bot.sendMessage(chat_id=i, text=sourceclonemsg2 + msg2 , reply_markup=button, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                                logclonesultlink = f'<a href="{clonelogmsg.link}">Log group</a>'
                                cloneresult = f"\n\n<b><i>This message saved in my</i></b> "
                                cloneresult += f"<b><i>{logclonesultlink}</i></b>"
                    except TypeError:
                        pass
            if button in ["cancelled", ""]:
              sendMessage(f"{tag} {result}", bot, message)
            else:
                if MAKE_OWNER_AND_SUDO_ANONYMOUS:
                    user_id = message.from_user.id
                    if (
                        user_id in SUDO_USERS or user_id == OWNER_ID
                        ):
                        bot_d = bot.get_me()
                        bot_username = bot_d.username
                        checkbot = f"http://t.me/{bot_username}"
                        ownerresult = f"<b>Dear Owner or Sudo User I Have Sent Your #Cloned Link's In Your PM</b>"
                        chckbutton1 = ButtonMaker()
                        chckbutton1.buildbutton("Check Now", checkbot)
                        bot.sendMessage(chat_id=message.from_user.id, text=result + cc,
                                                                   reply_markup=button, parse_mode=ParseMode.HTML)
                        ownrmsg = sendMarkup(ownerresult, bot, message, InlineKeyboardMarkup(chckbutton1.build_menu(1)))
                        Thread(target=auto_delete_message, args=(bot, message, ownrmsg)).start()
                    else:
                        sendMarkup(result + cc + cloneresult, bot, message, button)
                        pass
                else:
                    sendMarkup(result + cc + cloneresult, bot, message, button)
        else:
            if button in ["cancelled", ""]:
              sendMessage(f"{tag} {result}", bot, message)
            else:
                if MAKE_OWNER_AND_SUDO_ANONYMOUS:
                    user_id = message.from_user.id
                    if (
                        user_id in SUDO_USERS or user_id == OWNER_ID
                        ):
                        bot_d = bot.get_me()
                        bot_username = bot_d.username
                        checkbot = f"http://t.me/{bot_username}"
                        ownerresult = f"<b>Dear Owner or Sudo User I Have Sent Your #Cloned Link's In Your PM</b>"
                        chckbutton = ButtonMaker()
                        chckbutton.buildbutton("Check Now", checkbot)
                        bot.sendMessage(chat_id=message.from_user.id, text=result + cc,
                                                                   reply_markup=button, parse_mode=ParseMode.HTML)
                        ownrmsg = sendMarkup(ownerresult, bot, message, InlineKeyboardMarkup(chckbutton.build_menu(1)))
                        Thread(target=auto_delete_message, args=(bot, message, ownrmsg)).start()
                    else:
                        sendMarkup(result + cc, bot, message, button)
                        pass
                else:
                     sendMarkup(result + cc, bot, message, button)
        if is_gdtot:
            gd.deletefile(link)
        elif is_appdrive:
            if link.get("link_type") == "login":
                LOGGER.info(f"Deleting: {link}")
                gd.deleteFile(link)
        if is_driveapp:
            if link.get("link_type") == "login":
                LOGGER.info(f"Deleting: {link}")
                gd.deleteFile(link)
        if is_hubdrive:
            gd.deletefile(link)
        if is_drivehub:
            if link.get("link_type") == "login":
                LOGGER.info(f"Deleting: {link}")
                gd.deleteFile(link)
        if is_kolop:
            gd.deletefile(link)
        if is_drivebuzz:
            gd.deletefile(link)
        if is_gdflix:
            if link.get("link_type") == "login":
                LOGGER.info(f"Deleting: {link}")
                gd.deleteFile(link)
        if is_drivesharer:
            if link.get("link_type") == "login":
                LOGGER.info(f"Deleting: {link}")
                gd.deleteFile(link)
        if is_drivebit:
            if link.get("link_type") == "login":
                LOGGER.info(f"Deleting: {link}")
                gd.deleteFile(link)
        if is_katdrive:
            gd.deletefile(link)
        if is_drivefire:
            gd.deletefile(link)
        if is_gadrive:
            gd.deletefile(link)
        if is_jiodrive:
            gd.deletefile(link)
        if is_drivelink:
            if link.get("link_type") == "login":
                LOGGER.info(f"Deleting: {link}")
                gd.deleteFile(link)
        if is_drivepro:
            if link.get("link_type") == "login":
                LOGGER.info(f"Deleting: {link}")
                gd.deleteFile(link)
        if is_driveace:
            if link.get("link_type") == "login":
                LOGGER.info(f"Deleting: {link}")
                gd.deleteFile(link)
        if is_sharerpw:
            gd.deletefile(link)
            
    else:
        sendMessage('<b>Cloning Supported Links:</b>\n\n<i>• appdrive links\n• gdtot links\n• drive links\n• Hubdrive links </i>\n\n<b><i>For Multimirror Send multiple links one by one and with replying first link Type /commandname 2,3,4(according to your links)</i></b>', bot, message)

@new_thread
def cloneNode(update, context):
    _clone(update.message, context.bot)

if SUDO_ONLY_MIRROR:
   allow_clone = CustomFilters.owner_filter | CustomFilters.sudo_user
else:
   allow_clone = CustomFilters.authorized_chat | CustomFilters.authorized_user

clone_handler = CommandHandler(BotCommands.CloneCommand, cloneNode, filters=allow_clone, run_async=True)
dispatcher.add_handler(clone_handler)
