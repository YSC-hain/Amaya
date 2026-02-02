from config.logger import logger
from events import bus, E
from channels.base import ChannelType, IncomingMessage, OutgoingMessage
import datetime
import asyncio

from config.settings import TELEGRAM_BOT_TOKEN
import telegram
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters


async def cmd_start(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"收到 /start 命令来自用户 {update.effective_user.id}")
    await update.message.reply_text("Amaya bot online.")


async def process_message(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"用户: {update.effective_user.id} 消息内容: {update.message.text}")
    await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action='typing')
    if update.message and update.message.text:
        incoming_msg = IncomingMessage(
            channel_type = ChannelType.TELEGRAM_BOT_POLLING,
            user_id = update.effective_user.id,
            content = update.message.text,
            channel_context = context,
            timestamp = update.message.date,
        )
        bus.emit(E.IO_MESSAGE_RECEIVED, incoming_msg)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 telegram 库中发生的错误"""
    logger.error(f"Telegram 错误: {context.error}", exc_info=context.error)

@bus.on(E.IO_SEND_MESSAGE)
async def send_outgoing_message(msg: OutgoingMessage) -> None:
    logger.info(f"发送消息给用户 {msg.user_id}: {msg.content}")
    await msg.channel_context.bot.send_message(chat_id=msg.user_id, text=msg.content)


async def main(shutdown_event: asyncio.Event = asyncio.Event()) -> None:
    # 最简单的 builder 用法（官方示例风格）
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_message))
    app.add_error_handler(error_handler)

    #app.run_polling(
    #    drop_pending_updates=True,
    #    timeout=datetime.timedelta(seconds=30),  # 长轮询
    #)

    try:    
        await app.initialize()
        await app.updater.start_polling(
            poll_interval=0.0,
            timeout=datetime.timedelta(seconds=30),
            drop_pending_updates=True,
        )
        await app.start()
        logger.info("Telegram Bot Polling 已启动")
        
        await shutdown_event.wait()
    finally:
        logger.info("关闭 Telegram Bot Polling...")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
