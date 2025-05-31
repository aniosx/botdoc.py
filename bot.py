#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import logging
import threading
from flask import Flask
from dotenv import load_dotenv
from telegram import Update, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    CallbackQueryHandler
)

# Configuration du logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Chargement des variables d'environnement
load_dotenv()

# Configuration du bot
TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("Le token TELEGRAM_TOKEN est manquant dans les variables d'environnement.")
OWNER_ID = int(os.getenv('OWNER_ID', '144262846'))
PORT = int(os.environ.get('PORT', 8080))

# Dictionnaire pour stocker les messages et leurs expéditeurs
message_registry = {}

# Liste des utilisateurs bloqués (en mémoire)
blocked_users = set()

# Fichier pour stocker les utilisateurs bloqués
BLOCKED_USERS_FILE = 'blocked_users.json'

# Créer une application Flask pour le ping
app = Flask(__name__)

@app.route('/')
def index():
    return 'Bot Telegram en ligne!'

def load_blocked_users():
    """Charge la liste des utilisateurs bloqués depuis le fichier."""
    global blocked_users
    try:
        if os.path.exists(BLOCKED_USERS_FILE):
            with open(BLOCKED_USERS_FILE, 'r') as f:
                blocked_list = json.load(f)
                blocked_users = set(blocked_list)
                logger.info(f"Loaded {len(blocked_users)} blocked users from file")
    except Exception as e:
        logger.error(f"Error loading blocked users: {e}")

def save_blocked_users():
    """Sauvegarde la liste des utilisateurs bloqués dans le fichier."""
    try:
        with open(BLOCKED_USERS_FILE, 'w') as f:
            json.dump(list(blocked_users), f)
            logger.info(f"Saved {len(blocked_users)} blocked users to file")
    except Exception as e:
        logger.error(f"Error saving blocked users: {e}")

def start(update: Update, context: CallbackContext) -> None:
    """Gestionnaire de la commande /start."""
    user = update.effective_user
    
    if user.id in blocked_users and user.id != OWNER_ID:
        update.message.reply_text(
            "Vous avez été bloqué et ne pouvez pas utiliser ce bot."
        )
        return
    
    update.message.reply_text(
        f'Bonjour {user.first_name} ! Je suis un bot de relais de messages. '
        f'Envoyez-moi un message et il sera transmis au propriétaire du bot.'
    )
    
    if user.id != OWNER_ID:
        context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"Nouvel utilisateur: {user.first_name} (@{user.username or 'Sans username'}) [ID: {user.id}] a démarré le bot."
        )

def help_command(update: Update, context: CallbackContext) -> None:
    """Gestionnaire de la commande /help."""
    user = update.effective_user
    
    if user.id in blocked_users and user.id != OWNER_ID:
        update.message.reply_text(
            "Vous avez été bloqué et ne pouvez pas utiliser ce bot."
        )
        return
    
    help_text = (
        'Commandes disponibles:\n'
        '/start - Démarrer le bot\n'
        '/help - Afficher ce message d\'aide\n\n'
        'Pour utiliser ce bot, envoyez simplement un message et il sera transmis au propriétaire.'
    )
    
    if user.id == OWNER_ID:
        help_text += (
            '\n\nCommandes de gestion (propriétaire uniquement):\n'
            '/block [user_id] - Bloquer un utilisateur\n'
            '/unblock [user_id] - Débloquer un utilisateur\n'
            '/blocklist - Afficher la liste des utilisateurs bloqués'
        )
    
    update.message.reply_text(help_text)

def block_user(update: Update, context: CallbackContext) -> None:
    """Gestionnaire de la commande /block pour bloquer un utilisateur."""
    user = update.effective_user
    
    if user.id != OWNER_ID:
        update.message.reply_text("Cette commande est réservée au propriétaire du bot.")
        return
    
    if not context.args or not context.args[0].isdigit():
        update.message.reply_text(
            "Veuillez spécifier l'ID de l'utilisateur à bloquer.\n"
            "Exemple: /block 123456789"
        )
        return
    
    user_id = int(context.args[0])
    
    if user_id == OWNER_ID:
        update.message.reply_text("Vous ne pouvez pas vous bloquer vous-même.")
        return
    
    blocked_users.add(user_id)
    save_blocked_users()
    
    update.message.reply_text(f"L'utilisateur avec l'ID {user_id} a été bloqué.")

def unblock_user(update: Update, context: CallbackContext) -> None:
    """Gestionnaire de la commande /unblock pour débloquer un utilisateur."""
    user = update.effective_user
    
    if user.id != OWNER_ID:
        update.message.reply_text("Cette commande est réservée au propriétaire du bot.")
        return
    
    if not context.args or not context.args[0].isdigit():
        update.message.reply_text(
            "Veuillez spécifier l'ID de l'utilisateur à débloquer.\n"
            "Exemple: /unblock 123456789"
        )
        return
    
    user_id = int(context.args[0])
    
    if user_id in blocked_users:
        blocked_users.remove(user_id)
        save_blocked_users()
        update.message.reply_text(f"L'utilisateur avec l'ID {user_id} a été débloqué.")
    else:
        update.message.reply_text(f"L'utilisateur avec l'ID {user_id} n'est pas bloqué.")

def blocklist(update: Update, context: CallbackContext) -> None:
    """Gestionnaire de la commande /blocklist pour afficher la liste des utilisateurs bloqués."""
    user = update.effective_user
    
    if user.id != OWNER_ID:
        update.message.reply_text("Cette commande est réservée au propriétaire du bot.")
        return
    
    if not blocked_users:
        update.message.reply_text("Aucun utilisateur n'est bloqué.")
        return
    
    blocklist_text = "Liste des utilisateurs bloqués:\n"
    for blocked_id in blocked_users:
        blocklist_text += f"- ID: {blocked_id}\n"
    
    update.message.reply_text(blocklist_text)

def forward_message(update: Update, context: CallbackContext) -> None:
    """Transmet les messages des utilisateurs au propriétaire."""
    user = update.effective_user
    message = update.message
    
    if user.id == OWNER_ID:
        return
    
    if user.id in blocked_users:
        update.message.reply_text(
            "Vous avez été bloqué et ne pouvez pas envoyer de messages via ce bot."
        )
        return
    
    # Créer un lien Telegram vers l'utilisateur
    sender_info = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
    
    # Créer des boutons inline pour répondre et bloquer
    reply_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Répondre", callback_data=f"reply_{user.id}_{message.message_id}"),
            InlineKeyboardButton("Bloquer", callback_data=f"block_{user.id}")
        ]
    ])
    
    # Transmettre différents types de messages
    if message.text:
        forwarded = context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"{sender_info}\n{message.text}",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_keyboard
        )
        message_registry[f"{forwarded.message_id}"] = {
            "user_id": user.id,
            "original_message_id": message.message_id
        }
    
    elif message.photo:
        photo = message.photo[-1]
        caption = message.caption or ""
        forwarded = context.bot.send_photo(
            chat_id=OWNER_ID,
            photo=photo.file_id,
            caption=f"{sender_info}\n{caption}",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_keyboard
        )
        message_registry[f"{forwarded.message_id}"] = {
            "user_id": user.id,
            "original_message_id": message.message_id
        }
    
    elif message.document:
        forwarded = context.bot.send_document(
            chat_id=OWNER_ID,
            document=message.document.file_id,
            caption=f"{sender_info}\n{message.document.file_name or ''}",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_keyboard
        )
        message_registry[f"{forwarded.message_id}"] = {
            "user_id": user.id,
            "original_message_id": message.message_id
        }
    
    elif message.video:
        forwarded = context.bot.send_video(
            chat_id=OWNER_ID,
            video=message.video.file_id,
            caption=f"{sender_info}\n{message.caption or ''}",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_keyboard
        )
        message_registry[f"{forwarded.message_id}"] = {
            "user_id": user.id,
            "original_message_id": message.message_id
        }
    
    elif message.voice:
        forwarded = context.bot.send_voice(
            chat_id=OWNER_ID,
            voice=message.voice.file_id,
            caption=f"{sender_info}\nMessage vocal",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_keyboard
        )
        message_registry[f"{forwarded.message_id}"] = {
            "user_id": user.id,
            "original_message_id": message.message_id
        }
    
    elif message.audio:
        forwarded = context.bot.send_audio(
            chat_id=OWNER_ID,
            audio=message.audio.file_id,
            caption=f"{sender_info}\n{message.audio.title or ''}",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_keyboard
        )
        message_registry[f"{forwarded.message_id}"] = {
            "user_id": user.id,
            "original_message_id": message.message_id
        }
    
    elif message.sticker:
        forwarded = context.bot.send_sticker(
            chat_id=OWNER_ID,
            sticker=message.sticker.file_id
        )
        context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"{sender_info}\nSticker envoyé",
            parse_mode=ParseMode.HTML,
            reply_to_message_id=forwarded.message_id,
            reply_markup=reply_keyboard
        )
        message_registry[f"{forwarded.message_id}"] = {
            "user_id": user.id,
            "original_message_id": message.message_id
        }
    
    else:
        update.message.reply_text("Ce type de message n'est pas encore pris en charge.")
        context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"{sender_info}\nMessage de type non pris en charge",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_keyboard
        )
    
    update.message.reply_text("Votre message a été transmis.")

def handle_reply_button(update: Update, context: CallbackContext) -> None:
    """Gère les clics sur les boutons inline."""
    query = update.callback_query
    query.answer()
    
    if query.from_user.id != OWNER_ID:
        query.edit_message_reply_markup(None)
        context.bot.send_message(
            chat_id=query.from_user.id,
            text="Seul le propriétaire du bot peut utiliser ces boutons."
        )
        return
    
    data = query.data.split("_")
    
    if len(data) >= 3 and data[0] == "reply":
        user_id = int(data[1])
        context.user_data["reply_to"] = user_id
        context.user_data["original_message"] = query.message.message_id
        
        query.edit_message_reply_markup(None)
        context.bot.send_message(
            chat_id=OWNER_ID,
            text="Envoyez votre réponse maintenant",
            reply_to_message_id=query.message.message_id
        )
    
    elif len(data) >= 2 and data[0] == "block":
        user_id = int(data[1])
        
        if user_id == OWNER_ID:
            context.bot.send_message(
                chat_id=OWNER_ID,
                text="Vous ne pouvez pas vous bloquer vous-même."
            )
            return
        
        blocked_users.add(user_id)
        save_blocked_users()
        
        query.edit_message_reply_markup(None)
        context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"L'utilisateur avec l'ID {user_id} a été bloqué."
        )

def handle_owner_reply(update: Update, context: CallbackContext) -> None:
    """Gère les réponses du propriétaire aux messages transmis."""
    user = update.effective_user
    message = update.message
    
    if user.id != OWNER_ID:
        return
    
    if message.reply_to_message:
        replied_msg_id = str(message.reply_to_message.message_id)
        
        if replied_msg_id in message_registry:
            target_user_id = message_registry[replied_msg_id]["user_id"]
            
            if target_user_id in blocked_users:
                context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"Cet utilisateur (ID: {target_user_id}) est bloqué. Débloquez-le avec /unblock {target_user_id} pour lui envoyer des messages.",
                    reply_to_message_id=message.message_id
                )
                return
            
            try:
                if message.text:
                    context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"Réponse du propriétaire: {message.text}"
                    )
                elif message.photo:
                    photo = message.photo[-1]
                    caption = message.caption or ""
                    context.bot.send_photo(
                        chat_id=target_user_id,
                        photo=photo.file_id,
                        caption=f"Réponse du propriétaire: {caption}"
                    )
                elif message.document:
                    context.bot.send_document(
                        chat_id=target_user_id,
                        document=message.document.file_id,
                        caption=f"Réponse du propriétaire: {message.caption or ''}"
                    )
                elif message.video:
                    context.bot.send_video(
                        chat_id=target_user_id,
                        video=message.video.file_id,
                        caption=f"Réponse du propriétaire: {message.caption or ''}"
                    )
                elif message.voice:
                    context.bot.send_voice(
                        chat_id=target_user_id,
                        voice=message.voice.file_id,
                        caption="Réponse vocale du propriétaire"
                    )
                elif message.audio:
                    context.bot.send_audio(
                        chat_id=target_user_id,
                        audio=message.audio.file_id,
                        caption=f"Réponse audio du propriétaire: {message.caption or ''}"
                    )
                elif message.sticker:
                    context.bot.send_sticker(
                        chat_id=target_user_id,
                        sticker=message.sticker.file_id
                    )
                else:
                    context.bot.send_message(
                        chat_id=target_user_id,
                        text="Le propriétaire a répondu avec un type de message non pris en charge."
                    )
                
                context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"Votre réponse a été envoyée à l'utilisateur ID: {target_user_id}",
                    reply_to_message_id=message.message_id
                )
            
            except Exception as e:
                context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"Erreur lors de l'envoi de la réponse: {str(e)}",
                    reply_to_message_id=message.message_id
                )

def error_handler(update: Update, context: CallbackContext) -> None:
    """Gère les erreurs rencontrées par le dispatcher."""
    logger.exception("Une erreur est survenue pendant le traitement de la mise à jour.", exc_info=context.error)
    if update and update.effective_chat:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Une erreur est survenue. Veuillez réessayer plus tard."
        )

def run_flask():
    """Exécute l'application Flask pour le ping."""
    app.run(host='0.0.0.0', port=PORT)

def main() -> None:
    """Fonction principale pour démarrer le bot."""
    load_blocked_users()
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("block", block_user))
    dispatcher.add_handler(CommandHandler("unblock", unblock_user))
    dispatcher.add_handler(CommandHandler("blocklist", blocklist))
    dispatcher.add_handler(CallbackQueryHandler(handle_reply_button))
    dispatcher.add_handler(MessageHandler(
        Filters.reply & Filters.user(OWNER_ID),
        handle_owner_reply
    ))
    dispatcher.add_handler(MessageHandler(
        Filters.text | Filters.photo | Filters.document | Filters.video |
        Filters.voice | Filters.audio | Filters.sticker,
        forward_message
    ))
    dispatcher.add_error_handler(error_handler)
    
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    updater.start_polling()
    logger.info("Bot démarré. Appuyez sur Ctrl+C pour arrêter.")
    updater.idle()

if __name__ == '__main__':
    main()
