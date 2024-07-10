import asyncio
import logging
from os import getenv
from collections import defaultdict

from aiogram import Bot, Dispatcher, Router, html
from aiogram.enums import ParseMode, ChatAction
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, Message
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.bot import DefaultBotProperties
from dotenv import load_dotenv

from memgpt import create_memgpt_user, send_message_to_memgpt, update_fixies
from db import save_user_pseudonym, get_user_info, get_user_agent_id, check_user_exists

load_dotenv()
TELEGRAM_TOKEN = getenv("TELEGRAM_TOKEN")

bot = Bot(
    token=TELEGRAM_TOKEN,
    session=AiohttpSession(),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
router = Router()

class Form(StatesGroup):
    awaiting_pseudonym = State()

user_queues = defaultdict(asyncio.Queue)

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    user_exists = await check_user_exists(message.from_user.id)
    if user_exists:
        await message.answer("Welcome back! How can I assist you today?")
    else:
        await message.answer(
            "Welcome to the fxyzNetwork! I'm FixieTheGenie, your digital assistant. "
            "Let's begin by creating your pseudonym. What name would you like to use within the network?"
        )
        await state.set_state(Form.awaiting_pseudonym)

@router.message(Form.awaiting_pseudonym)
async def process_pseudonym(message: Message, state: FSMContext):
    pseudonym = message.text
    await save_user_pseudonym(message.from_user.id, pseudonym)
    
    await message.answer(
        f"Great choice, {html.quote(pseudonym)}! I'm setting up your personalized Fixie assistant now. "
        "This may take a moment, so please hang tight..."
    )
    
    result = await create_memgpt_user(message.from_user.id, pseudonym)
    if result:
        await message.answer(
            f"Your GenieTheFixie - digital assistant is ready! GenieTheFixie is here to help. "
            "Your custom NFT will be minted soon, allowing you to fully engage with the fxyzNetwork. "
            "Feel free to ask me anything about the network or how I can assist you!"
        )
    else:
        await message.answer("I'm sorry, there was an error creating your agent. Please try again with /start.")
    await state.clear()

@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "Here are the available commands:\n"
        "/start - Begin interaction or get a welcome message\n"
        "/help - Show this help message\n"
        "You can also simply send me a message, and I'll do my best to assist you!"
    )

# Commenting out the /menu command handler for now
# @router.message(Command("menu"))
# async def menu_command(message: Message):
#     await message.answer(
#         "Here is the menu:\n"
#         "1. Option 1\n"
#         "2. Option 2\n"
#         "3. Option 3\n"
#         "Please choose an option."
#     )

@router.message()
async def handle_message(message: Message):
    user_exists = await check_user_exists(message.from_user.id)
    if not user_exists:
        await message.answer("It seems you're not registered yet. Please start with /start to create your account.")
        return

    agent_id = await get_user_agent_id(message.from_user.id)
    if not agent_id:
        await message.answer("Your agent hasn't been set up properly. Please try /start again.")
        return

    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await user_queues[message.from_user.id].put(message.text)

async def process_message_queue():
    while True:
        for user_id, queue in user_queues.items():
            if not queue.empty():
                message_text = await queue.get()
                response = await send_message_to_memgpt(user_id, message_text)
                await bot.send_message(user_id, response)
        await asyncio.sleep(0.1)

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="/start", description="Begin interaction or get a welcome message"),
        BotCommand(command="/help", description="Show this help message"),
    ]
    await bot.set_my_commands(commands)

async def main():
    await update_fixies()  # Ensure FIXIES is updated before starting the bot
    dp.include_router(router)
    asyncio.create_task(process_message_queue())
    await set_commands(bot)  # Set the bot commands
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())