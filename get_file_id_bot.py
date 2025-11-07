#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bot Simples para Capturar File IDs
Use este bot para obter file_ids de qualquer mídia enviada
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configure o logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# TOKEN DO BOT
BOT_TOKEN = "8509543173:AAHy0_nHzxvjTU0t40952zMgg6vtry5Oys0"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    await update.message.reply_text(
        "🤖 *Bot de File ID*\n\n"
        "Envie qualquer mídia (foto, vídeo, áudio, documento, etc.) "
        "e eu retornarei o file_id!\n\n"
        "Tipos suportados:\n"
        "📷 Fotos\n"
        "🎥 Vídeos\n"
        "🎤 Áudios de voz\n"
        "🎵 Músicas\n"
        "📄 Documentos\n"
        "🎬 GIFs\n"
        "🎭 Stickers",
        parse_mode='Markdown'
    )

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Captura file_id de qualquer mídia"""
    message = update.message
    file_id = None
    media_type = None
    extra_info = ""
    
    # Detecta o tipo de mídia e extrai o file_id
    if message.photo:
        # Para fotos, pega a maior resolução
        largest_photo = max(message.photo, key=lambda p: p.width * p.height)
        file_id = largest_photo.file_id
        media_type = "📷 Foto"
        extra_info = f"Resolução: {largest_photo.width}x{largest_photo.height}"
        
    elif message.video:
        file_id = message.video.file_id
        media_type = "🎥 Vídeo"
        duration = message.video.duration
        extra_info = f"Duração: {duration}s | Resolução: {message.video.width}x{message.video.height}"
        
    elif message.voice:
        file_id = message.voice.file_id
        media_type = "🎤 Áudio de Voz"
        extra_info = f"Duração: {message.voice.duration}s"
        
    elif message.audio:
        file_id = message.audio.file_id
        media_type = "🎵 Música/Áudio"
        title = message.audio.title or "Sem título"
        extra_info = f"Título: {title} | Duração: {message.audio.duration}s"
        
    elif message.document:
        file_id = message.document.file_id
        media_type = "📄 Documento"
        file_name = message.document.file_name or "Sem nome"
        extra_info = f"Nome: {file_name}"
        
    elif message.animation:
        file_id = message.animation.file_id
        media_type = "🎬 GIF/Animação"
        extra_info = f"Resolução: {message.animation.width}x{message.animation.height}"
        
    elif message.sticker:
        file_id = message.sticker.file_id
        media_type = "🎭 Sticker"
        emoji = message.sticker.emoji or ""
        extra_info = f"Emoji: {emoji}"
        
    elif message.video_note:
        file_id = message.video_note.file_id
        media_type = "🎥 Vídeo Nota"
        extra_info = f"Duração: {message.video_note.duration}s"
    
    if file_id:
        # Monta a resposta
        response = f"✅ *{media_type} Detectado!*\n\n"
        response += f"📋 *File ID:*\n`{file_id}`\n\n"
        
        if extra_info:
            response += f"ℹ️ *Informações:*\n{extra_info}\n\n"
        
        response += f"💡 *Como usar no seu bot:*\n```python\n"
        
        # Adiciona exemplo de código específico para cada tipo
        if message.photo:
            response += f'await bot.send_photo(chat_id, photo="{file_id}")'
        elif message.video:
            response += f'await bot.send_video(chat_id, video="{file_id}")'
        elif message.voice:
            response += f'await bot.send_voice(chat_id, voice="{file_id}")'
        elif message.audio:
            response += f'await bot.send_audio(chat_id, audio="{file_id}")'
        elif message.document:
            response += f'await bot.send_document(chat_id, document="{file_id}")'
        elif message.animation:
            response += f'await bot.send_animation(chat_id, animation="{file_id}")'
        elif message.sticker:
            response += f'await bot.send_sticker(chat_id, sticker="{file_id}")'
        elif message.video_note:
            response += f'await bot.send_video_note(chat_id, video_note="{file_id}")'
            
        response += "\n```"
        
        await message.reply_text(response, parse_mode='Markdown')
        
        # Log no console também
        logger.info(f"File ID capturado - Tipo: {media_type}")
        logger.info(f"File ID: {file_id}")
        
    else:
        await message.reply_text("❌ Tipo de mídia não reconhecido!")

def main():
    """Função principal"""
    # Verifica se o token foi configurado
    if BOT_TOKEN == "SEU_TOKEN_AQUI":
        print("❌ ERRO: Configure o BOT_TOKEN no arquivo!")
        print("Edite a linha 19 e coloque seu token")
        return
    
    # Cria a aplicação
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Adiciona os handlers
    application.add_handler(CommandHandler("start", start))
    
    # Handlers para todos os tipos de mídia
    application.add_handler(MessageHandler(filters.PHOTO, handle_media))
    application.add_handler(MessageHandler(filters.VIDEO, handle_media))
    application.add_handler(MessageHandler(filters.VOICE, handle_media))
    application.add_handler(MessageHandler(filters.AUDIO, handle_media))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_media))
    application.add_handler(MessageHandler(filters.ANIMATION, handle_media))
    application.add_handler(MessageHandler(filters.Sticker.ALL, handle_media))
    # VideoNote pode não existir em algumas versões
    try:
        application.add_handler(MessageHandler(filters.VideoNote.ALL, handle_media))
    except AttributeError:
        pass  # Versão antiga da biblioteca, ignora video notes
    
    # Inicia o bot
    print("🤖 Bot de File ID iniciado!")
    print("📱 Envie /start no Telegram para começar")
    print("🛑 Pressione Ctrl+C para parar")
    
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()