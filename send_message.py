import asyncio
import logging
from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.errors import UserAlreadyParticipantError, FloodWaitError, ChannelInvalidError
import settings

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем клиент
client = TelegramClient('session_name', settings.API_ID, settings.API_HASH)

# Флаг для остановки рассылки
stop_broadcast = False

# Функция для отправки сообщений с паузой и циклом
async def send_messages(chat_ids, message):
    global stop_broadcast
    while not stop_broadcast:
        for chat_id in chat_ids:
            if stop_broadcast:
                logger.info("Рассылка остановлена.")
                return
            try:
                await client.send_message(chat_id, message)
                logger.info(f"Сообщение отправлено в {chat_id}")
                await asyncio.sleep(420)  # Пауза в 420 секунд между отправками
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения в {chat_id}: {e}")
        logger.info("Цикл завершен, ждем 1800 сек перед повтором цикла.")
        await asyncio.sleep(1800)  # Пауза в 30 минут перед повтором цикла

# Функция для получения списка публичных чатов
async def get_public_chats():
    public_chats = []
    async for dialog in client.iter_dialogs():
        if dialog.is_channel and dialog.entity.username:  # Проверяем, что это публичный канал
            public_chats.append(dialog.entity.username)
    return public_chats

# Функция для проверки участия в группах и вступления в них
async def follow_list(chat_ids):
    to_join = []
    for chat_id in chat_ids:
        try:
            entity = await client.get_entity(chat_id)
            if not entity.left:  # Проверяем, что пользователь не покинул группу
                logger.info(f"Вы уже состоите в {chat_id}")
            else:
                to_join.append(chat_id)
                logger.info(f"Добавлен в список для вступления: {chat_id}")
                await asyncio.sleep(2)  # Добавляем задержку только для новых чатов
        except UserAlreadyParticipantError:
            logger.info(f"Вы уже состоите в {chat_id}")
        except ChannelInvalidError:
            logger.info(f"Чат {chat_id} не существует. Удаляем из списка.")
            client.chat_list.remove(chat_id)
        except FloodWaitError as e:
            logger.warning(f"Слишком много запросов. Ждем {e.seconds} секунд.")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Ошибка при проверке {chat_id}: {e}")

    logger.info("Проверка завершена. Начинаем процесс вступления.")
    for chat_id in to_join:
        try:
            await client(JoinChannelRequest(chat_id))
            logger.info(f"Вступили в {chat_id}")
            await asyncio.sleep(2)  # Добавляем задержку между вступлениями
        except FloodWaitError as e:
            logger.warning(f"Слишком много запросов. Ждем {e.seconds} секунд.")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Ошибка при вступлении в {chat_id}: {e}")
    logger.info("Процесс вступления завершен.")

# Обработчик для получения команд
@client.on(events.NewMessage(pattern='/add_chat'))
async def handler(event):
    chat_ids = event.message.text.split(" ", 1)[1].split(",")
    chat_ids = [chat_id.strip() for chat_id in chat_ids]
    await event.respond(f"Чаты добавлены.\n Для отображения списка используйте команду:\n /list_chats")
    # Сохраняем чаты и сообщение для рассылки
    client.chat_list = chat_ids
    # Удаляем сообщение через 2 секунды
    await asyncio.sleep(2)
    await event.delete()

@client.on(events.NewMessage(pattern='/set_message'))
async def handler(event):
    message = event.message.text.split(" ", 1)[1]
    await event.respond("Сообщение для рассылки установлено.")
    # Сохраняем сообщение для рассылки
    client.message_to_send = message

@client.on(events.NewMessage(pattern='/start_broadcast'))
async def handler(event):
    await event.respond("Начинаем рассылку сообщений.")
    await send_messages(client.chat_list, client.message_to_send)
    await event.respond("Рассылка запущена.")

@client.on(events.NewMessage(pattern='/stop_broadcast'))
async def handler(event):
    global stop_broadcast
    stop_broadcast = True
    await event.respond("Рассылка остановлена.")

@client.on(events.NewMessage(pattern='/clear_list'))
async def handler(event):
    client.chat_list = []
    await event.respond("Список чатов очищен.")
    
@client.on(events.NewMessage(pattern='/list_chats'))
async def handler(event):
    if hasattr(client, 'chat_list') and client.chat_list:
        await event.respond(f"Текущий список чатов: {', '.join(client.chat_list)}")
    else:
        await event.respond("Список чатов пуст.")

# Обработчик для команды получения списка публичных чатов
@client.on(events.NewMessage(pattern='/list_public_chats'))
async def handler(event):
    public_chats = await get_public_chats()
    message = f"Вы участник следующих публичных чатов (username): {', '.join(public_chats)}"
    if len(message) > 4096:
        parts = [message[i:i+4096] for i in range(0, len(message), 4096)]
        for part in parts:
            await client.send_message(event.chat_id, part)
    else:
        await client.send_message(event.chat_id, message)
        
# Обработчик для команды schedule_message
@client.on(events.NewMessage(pattern='/schedule_message'))
async def handler(event):
    try:
        parts = event.message.text.split(" ", 2)
        chat_id = parts[1].strip()
        message = parts[2].strip()
        send_time = datetime.now() + timedelta(minutes=1)  # Отправка через 1 минуту
        await event.respond(f"Сообщение будет отправлено в {send_time.strftime('%H:%M:%S')}")
        await asyncio.sleep(60)  # Ожидание 1 минуты
        await client.send_message(chat_id, message)
        await event.respond("Сообщение отправлено.")
    except Exception as e:
        await event.respond(f"Ошибка при планировании сообщения: {e}")

# Обработчик для команды follow_list
@client.on(events.NewMessage(pattern='/follow_list'))
async def handler(event):
    await event.respond("Проверяем участие в группах и вступаем при необходимости.")
    await follow_list(client.chat_list)
    await event.respond("Проверка и вступление завершены.")

client.start()
client.run_until_disconnected()
