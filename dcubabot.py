#!/usr/bin/python3
# -*- coding: utf-8 -*-

# STL imports
import sys
import logging
import datetime

# Non STL imports
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Updater, Filters, MessageHandler, CallbackQueryHandler)

# Local imports
# from tokenz import *
from models import *
from dccommandhandler import DCCommandHandler
from orga2Utils import noitip, asm
from errors import error_callback
import labos

# TODO:Move this out of here
logging.basicConfig(
    level=logging.INFO,
    # level=logging.DEBUG,
    format='[%(asctime)s] - [%(name)s] - [%(levelname)s] - %(message)s',
    filename="bots.log")


# Globals ...... yes, globals
logger = logging.getLogger("DCUBABOT")


def start(update, context):
    msg = update.message.reply_text("Hola, ¿qué tal? ¡Mandame /help si no sabés qué puedo hacer!",
                              quote=False)
    context.dc_sent_messages.append(msg)


def help(update, context):
    message_text = ""
    with db_session:
        for command in select(c for c in Command if c.description).order_by(lambda c: c.name):
            message_text += "/" + command.name + " - " + command.description + "\n"
    msg = update.message.reply_text(message_text, quote=False)
    context.dc_sent_messages.append(msg)


def estasvivo(update, context):
    msg = update.message.reply_text("Sí, estoy vivo.", quote=False)
    context.dc_sent_messages.append(msg)


def list_buttons(update, context, listable_type):
    with db_session:
        buttons = select(l for l in listable_type if l.validated).order_by(lambda l: l.name)
        keyboard = []
        columns = 3
        for k in range(0, len(buttons), columns):
            row = [InlineKeyboardButton(text=button.name, url=button.url,
                                        callback_data=button.url) for button in buttons[k:k + columns]]
            keyboard.append(row)
        reply_markup = InlineKeyboardMarkup(keyboard)
        msg = update.message.reply_text(text="Grupos: ", disable_web_page_preview=True,
                                        reply_markup=reply_markup, quote=False)
        context.dc_sent_messages.append(msg)


def listar(update, context):
    list_buttons(update, context, Obligatoria)


def listaroptativa(update, context):
    list_buttons(update, context, Optativa)


def listarotro(update, context):
    list_buttons(update, context, Otro)


def cubawiki(update, context):
    with db_session:
        group = select(o for o in Obligatoria if o.chat_id == update.message.chat.id
                       and o.cubawiki_url is not None).first()
        if group:
            msg = update.message.reply_text(group.cubawiki_url, quote=False)
            context.dc_sent_messages.append(msg)


def log_message(update, context):
    user = str(update.message.from_user.id)
    # EAFP
    try:
        user_at_group = user+" @ " + update.message.chat.title
    except:
        user_at_group = user
    logger.info(user_at_group + ": " + update.message.text)


def felizdia_text(today):
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
             "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    dia = str(today.day)
    mes = int(today.month)
    mes = meses[mes - 1]
    return "Feliz " + dia + " de " + mes


def felizdia(context):
    today = datetime.date.today()
    context.bot.send_message(chat_id="@dcfceynuba", text=felizdia_text(today))


def suggest_listable(update, context, listable_type):
    try:
        name, url = " ".join(context.args).split("|")
        if not (name and url):
            raise Exception
    except:
        msg = update.message.reply_text("Hiciste algo mal, la idea es que pongas:\n" +
                                         update.message.text.split()[0] + " <nombre>|<link>", quote=False)
        context.dc_sent_messages.append(msg)
        return
    with db_session:
        group = listable_type(name=name, url=url)
    keyboard = [
        [
            InlineKeyboardButton(text="Aceptar", callback_data=str(group.id) + '|1'),
            InlineKeyboardButton(text="Rechazar", callback_data=str(group.id) + '|0')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.sendMessage(chat_id=137497264, text=listable_type.__name__ + ": " + name + "\n" + url,
                            reply_markup=reply_markup)
    msg = update.message.reply_text("OK, se lo mando a Rozen.", quote=False)
    context.dc_sent_messages.append(msg)


def sugerirgrupo(update, context):
    suggest_listable(update, context, Obligatoria)


def sugeriroptativa(update, context):
    suggest_listable(update, context, Optativa)


def sugerirotro(update, context):
    suggest_listable(update, context, Otro)


def listarlabos(update, context):
    args = context.args
    mins = int(args[0]) if len(args) > 0 else 0
    instant = labos.aware_now() + datetime.timedelta(minutes=mins)
    respuesta = '\n'.join(labos.events_at(instant))
    msg = update.message.reply_text(text=respuesta, quote=False)
    context.dc_sent_messages.append(msg)


''' La funcion button se encarga de tomar todos los context.botones que se apreten en el context.bot (y que no sean links)'''


def button(update, context):
    query = update.callback_query
    message = query.message
    id, action = query.data.split("|")
    with db_session:
        group = Listable[int(id)]
        if action == "1":
            group.validated = True
            action_text = "\n¡Aceptado!"
        else:
            group.delete()
            action_text = "\n¡Rechazado!"
    context.bot.editMessageText(chat_id=message.chat_id, message_id=message.message_id,
                                text=message.text + action_text)


def add_all_handlers(dispatcher):
    dispatcher.add_handler(MessageHandler(
        (Filters.text | Filters.command), log_message), group=1)
    with db_session:
        for command in select(c for c in Command):
            handler = DCCommandHandler(command.name, globals()[command.name])
            dispatcher.add_handler(handler)
    dispatcher.add_handler(CallbackQueryHandler(button))


def main():
    try:
        global update_id
        # Telegram context.bot Authorization Token
        botname = "DCUBABOT"
        print("Iniciando DCUBABOT")
        logger.info("Iniciando")
        init_db("dcubabot.sqlite3")
        updater = Updater(token=token, use_context=True)
        dispatcher = updater.dispatcher
        updater.job_queue.run_daily(callback=felizdia, time=datetime.time(second=3))
        updater.job_queue.run_repeating(callback=labos.update, interval=datetime.timedelta(hours=1))
        dispatcher.add_error_handler(error_callback)
        add_all_handlers(dispatcher)
        # Start running the context.bot
        updater.start_polling(clean=True)
    except Exception as inst:
        logger.critical("ERROR AL INICIAR EL DCUBABOT")
        logger.exception(inst)


if __name__ == '__main__':
    from tokenz import *
    main()
