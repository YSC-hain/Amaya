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


_typing_tasks: dict[int, asyncio.Task] = {}
_bot_instance: telegram.Bot = None

async def _send_typing_loop(bot: telegram.Bot, chat_id: int) -> None:
    """发送正在输入的动作"""
    try:
        logger.trace(f"开始发送 'typing' 动作给 Telegram chat_id: {chat_id}")
        for _ in range(0, 15):
            await bot.send_chat_action(chat_id=chat_id, action='typing')
            await asyncio.sleep(3.5)
        logger.trace(f"停止发送 typing 动作给 Telegram chat_id: {chat_id}")
    except asyncio.CancelledError:
        logger.trace(f"中止发送 typing 动作给 Telegram chat_id: {chat_id}")
        return        

@bus.on(E.IO_MESSAGE_RECEIVED)
async def start_sending_typing_loop(msg: IncomingMessage) -> None:
    """开始发送正在输入动作的循环任务"""
    chat_id = msg.metadata["channel_chat_id"]
    task = asyncio.create_task(_send_typing_loop(msg.channel_context.bot, chat_id))
    _typing_tasks[msg.user_id] = task

@bus.on(E.IO_SEND_MESSAGE)
async def stop_sending_typing_loop(msg: OutgoingMessage) -> None:
    """停止发送正在输入动作的循环任务"""
    task = _typing_tasks.get(msg.user_id)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        del _typing_tasks[msg.user_id]


@requires_auth
async def cmd_start(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"收到 /start 命令来自 Telegram ID: {update.effective_user.id}")
    await storage.user.create_user_if_not_exists(update.effective_user.id)
    await update.message.reply_text("Amaya bot online.")

@requires_auth
async def process_message(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # 预处理
    user = await storage.user.get_user_by_telegram_id(update.effective_user.id)
    if user is not None:
        user_id = user['user_id']
    else:
        logger.error(f"Telegram User ID: {update.effective_user.id} 在未注册时发送消息")
        await update.message.reply_text("您尚未注册，请发送 /start 命令以注册")
        return

    logger.info(f"User ID: {user_id} 消息内容: {update.message.text}")

    # 发送到事件总线
    if update.message and update.message.text:
        incoming_msg = IncomingMessage(
            channel_type = ChannelType.TELEGRAM_BOT_POLLING,
            user_id = user_id,
            content = update.message.text,
            channel_context = context,
            timestamp = update.message.date,
            metadata = {"channel_chat_id": update.effective_chat.id},
        )
        bus.emit(E.IO_MESSAGE_RECEIVED, incoming_msg)


@bus.on(E.IO_SEND_MESSAGE)
async def send_outgoing_message(msg: OutgoingMessage) -> None:
    logger.info(f"发送消息给用户 {msg.user_id}: {msg.content}")
    user = await storage.user.get_user_by_id(msg.user_id)
    if user is not None:
        chat_id = user['telegram_user_id']
        bot = _bot_instance or msg.channel_context.bot
        try:
            await bot.send_message(chat_id=chat_id, text=msg.content)
        except Exception as e:
            logger.error(f"向 Telegram 用户 {chat_id} 发送消息失败: {e}, 即将重试", exc_info=e)
            try:
                await asyncio.sleep(5)
                await bot.send_message(chat_id=chat_id, text=msg.content)
            except Exception as e:
                logger.error(f"[重试] 向 Telegram 用户 {chat_id} 发送消息失败: {e}", exc_info=e)
    else:
        logger.error(f"无法找到 user_id: {msg.user_id} 对应的 Telegram 用户")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 telegram 库中发生的错误"""
    logger.error(f"Telegram 错误: {context.error}", exc_info=context.error)
    if ADMIN_TELEGRAM_USER_ID != 0:
        try:
            await context.bot.send_message(chat_id=ADMIN_TELEGRAM_USER_ID, text=f"Warning! Amaya 在与 {update.effective_user.id} 的对话中发生错误: {context.error}")
        except Exception as e:
            logger.error(f"向管理员发送错误消息失败: {e}", exc_info=e)

def bot_error_callback(error: telegram.error.TelegramError) -> None:
    if isinstance(error, telegram.error.NetworkError):
        logger.warning(f"Telegram Bot 网络错误: {error}")
    else:
        logger.error(f"Telegram Bot 发生预期外的错误: {error}", exc_info=error)


async def main(shutdown_event: asyncio.Event = asyncio.Event()) -> None:
    global _bot_instance
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
        _bot_instance = app.bot
        await app.updater.start_polling(
            poll_interval=0.5,
            timeout=datetime.timedelta(seconds=15),
            bootstrap_retries=-1,
            drop_pending_updates=False,  # 保留下线期间的消息
            error_callback=bot_error_callback,
        )
        await app.start()
        logger.info("Telegram Bot Polling 已启动")
        
        await shutdown_event.wait()
    finally:
        logger.info("关闭 Telegram Bot Polling...")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
