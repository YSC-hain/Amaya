from config.logger import logger
from events import bus, E
from channels.base import ChannelType, IncomingMessage, OutgoingMessage
import datetime
import asyncio

from config.settings import *
import storage.user
import telegram
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from functools import wraps

def requires_auth(func):
    @wraps(func)
    async def decorated(update: telegram.Update, *args, **kwargs):
        if(update.effective_user.id not in ALLOWED_TELEGRAM_USER_IDS and ALLOWED_TELEGRAM_USER_IDS != []):
            logger.warning(f"用户 {update.effective_user.id} 未经允许访问 Bot")
            await update.message.reply_text("您无权使用此 Bot。如有需要, 请联系管理员。")
        else:
            return await func(update, *args, **kwargs)
    return decorated

async def send_typing_action(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """发送正在输入的动作"""
    while True:
        await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action='typing')
        await asyncio.sleep(3.5)


@requires_auth
async def cmd_start(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"收到 /start 命令来自 Telegram ID: {update.effective_user.id}")
    storage.user.create_user_if_not_exists(update.effective_user.id)
    await update.message.reply_text("Amaya bot online.")

@requires_auth
async def process_message(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = storage.user.get_user_by_telegram_id(update.effective_user.id)['user_id']
    logger.info(f"User ID: {user_id} 消息内容: {update.message.text}")
    send_typing_task = asyncio.create_task(send_typing_action(update, context))
    if update.message and update.message.text:
        incoming_msg = IncomingMessage(
            channel_type = ChannelType.TELEGRAM_BOT_POLLING,
            user_id = user_id,
            content = update.message.text,
            channel_context = context,
            timestamp = update.message.date,
        )
        bus.emit(E.IO_MESSAGE_RECEIVED, incoming_msg)
    send_typing_task.cancel()  # ToDo: 该task应该放入incoming_msg中, 由后续处理器取消

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 telegram 库中发生的错误"""
    logger.error(f"Telegram 错误: {context.error}", exc_info=context.error)
    if ADMIN_TELEGRAM_USER_ID != 0:
        try:
            await context.bot.send_message(chat_id=ADMIN_TELEGRAM_USER_ID, text=f"Warning! Amaya发生错误: {context.error}")
        except Exception as e:
            logger.error(f"向管理员发送错误消息失败: {e}", exc_info=e)


@bus.on(E.IO_SEND_MESSAGE)
async def send_outgoing_message(msg: OutgoingMessage) -> None:
    logger.info(f"发送消息给用户 {msg.user_id}: {msg.content}")
    chat_id = storage.user.get_user_by_id(msg.user_id)['telegram_user_id']
    await msg.channel_context.bot.send_message(chat_id=chat_id, text=msg.content)


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
