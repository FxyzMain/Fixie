import asyncio
import logging
from os import getenv
from collections import defaultdict

from aiogram import Bot, Dispatcher, Router, html
from aiogram.enums import ParseMode, ChatAction
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from dotenv import load_dotenv

from memgpt import create_memgpt_user, send_message_to_memgpt
from db import save_user_pseudonym, get_user_info, get_user_agent_id, check_user_exists

load_dotenv()
TELEGRAM_TOKEN = getenv("TELEGRAM_TOKEN")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
router = Router()

class Form(StatesGroup):
    awaiting_pseudonym = State()

# Add this at the top level
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
    
    result = await create_memgpt_user(message.from_user.id, pseudonym)
    if result:
        await message.answer(
            f"Great choice, {html.quote(pseudonym)}! {result} "
            "Your customized NFT will be minted soon, allowing you to interact with the network, "
            "upgrade your profile, and engage in various activities. "
            "For now, you can ask me anything about the fxyzNetwork or how I can assist you!"
        )
    else:
        await message.answer("I'm sorry, there was an error creating your agent. Please try again with /start.")
    await state.clear()

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

    logger.debug(f"Handling message for user {message.from_user.id}: {message.text}")
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await user_queues[message.from_user.id].put(message.text)

async def process_message_queue():
    while True:
        for user_id, queue in user_queues.items():
            if not queue.empty():
                message_text = await queue.get()
                response = await send_message_to_memgpt(user_id, message_text)
                logger.debug(f"Response for user {user_id}: {response}")
                await bot.send_message(user_id, response)
        await asyncio.sleep(0.1)

async def main():
    dp.include_router(router)
    asyncio.create_task(process_message_queue())
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    asyncio.run(main())