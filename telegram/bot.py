import asyncio
import logging
from os import getenv
from collections import defaultdict

from aiogram import Bot, Dispatcher, Router, html, types
from aiogram.enums import ParseMode, ChatAction
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.bot import DefaultBotProperties
from dotenv import load_dotenv

from memgpt import create_memgpt_user, send_message_to_memgpt, delete_memgpt_user, check_memgpt_server
from db import save_user_pseudonym, get_user_info, get_user_agent_id, check_user_exists, delete_user, save_user_report

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
    awaiting_report = State()

MAINTENANCE_MODE = False

async def maintenance_message(message: Message):
    await message.answer(
        "⚠️ The bot is currently undergoing maintenance. "
        "We apologize for the inconvenience and will be back soon! "
        "For urgent matters, please contact @fixiesupport."
    )

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    if MAINTENANCE_MODE:
        await maintenance_message(message)
        return

    user_id = message.from_user.id
    user_exists = await check_user_exists(user_id)
    agent_id = await get_user_agent_id(user_id)

    if user_exists and agent_id:
        await message.answer("Welcome back! How can I assist you today?")
    elif user_exists and not agent_id:
        await message.answer(
            "Welcome back! It seems your digital agent wasn't set up properly last time. "
            "Let's try again. What name would you like to use within the network?"
        )
        await state.set_state(Form.awaiting_pseudonym)
    else:
        await message.answer(
            "Welcome to the ƒxyzNetwork! I'm the Fixie Bot. I will help to create and manage the ƒixies "
            "Let's begin by creating your pseudonym. What name would you like to use within the network?"
        )
        await state.set_state(Form.awaiting_pseudonym)

@router.message(Form.awaiting_pseudonym)
async def process_pseudonym(message: Message, state: FSMContext):
    if MAINTENANCE_MODE:
        await maintenance_message(message)
        return

    user_id = message.from_user.id
    user_exists = await check_user_exists(user_id)
    
    if user_exists:
        await message.answer("Welcome back! How can I assist you today?")
        await state.clear()
        return

    pseudonym = message.text
    await state.update_data(creating_user=True)
    
    save_result = await save_user_pseudonym(user_id, pseudonym)
    
    if not save_result:
        await message.answer("I'm sorry, there was an error saving your pseudonym. Please try again later.")
        await state.clear()
        return

    await message.answer(
        f"Great choice, {html.quote(pseudonym)}! I'm setting up your personalized digital agent now. "
        "This may take a moment, so please hang tight..."
    )
    
    try:
        result = await create_memgpt_user(user_id, pseudonym)
        if result.startswith("MemGPT user setup completed"):
            await message.answer(
                f"Your first personalized digital agent, Genie The Fixie, is ready, {html.quote(pseudonym)}! "
                "Genie is here to help you navigate the ƒxyzNetwork. "
                "Your custom NFT will be minted soon, allowing you to fully engage with the network. "
                "Feel free to ask Genie anything about the network or how they can assist you!"
            )
        else:
            await message.answer(f"I'm sorry, there was an error creating your agent: {result}")
    finally:
        await state.clear()

@router.message(Command("help"))
async def help_command(message: Message):
    if MAINTENANCE_MODE:
        await maintenance_message(message)
        return
    
    await message.answer(
        "Here are the available commands:\n"
        "/start - Begin interaction or get a welcome message\n"
        "/help - Show this help message\n"
        "/delete - Delete your account\n"
        "/report - Report a bug or get help\n"
        "You can also simply send me a message, and I'll do my best to assist you!"
    )

@router.message(Command("delete"))
async def delete_command(message: Message):
    if MAINTENANCE_MODE:
        await maintenance_message(message)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Yes, delete my account", callback_data="confirm_delete")],
        [InlineKeyboardButton(text="No, keep my account", callback_data="cancel_delete")]
    ])
    await message.answer("Are you sure you want to delete your account? This action cannot be undone.", reply_markup=keyboard)

@router.callback_query(lambda c: c.data in ['confirm_delete', 'cancel_delete'])
async def process_delete_callback(callback_query: types.CallbackQuery):
    if MAINTENANCE_MODE:
        await maintenance_message(callback_query.message)
        return
    
    if callback_query.data == "confirm_delete":
        user_id = callback_query.from_user.id
        deletion_result = await delete_user_data(user_id)
        if deletion_result:
            await callback_query.message.edit_text("Your account has been successfully deleted. If you wish to use the bot again, please start with /start.")
        else:
            await callback_query.message.edit_text("There was an error deleting your account. Please try again later or contact support.")
    else:
        await callback_query.message.edit_text("Account deletion cancelled. Your account remains active.")

async def delete_user_data(user_id: int):
    try:
        memgpt_deletion = await delete_memgpt_user(user_id)
        db_deletion = await delete_user(user_id)
        return memgpt_deletion and db_deletion
    except Exception as e:
        logging.error(f"Error deleting user data: {str(e)}")
        return False

@router.message(Command("report"))
async def report_command(message: Message, state: FSMContext):
    if MAINTENANCE_MODE:
        await maintenance_message(message)
        return
    
    await message.answer("Please describe the issue you're experiencing or the help you need. Your report will be sent to our support team.")
    await state.set_state(Form.awaiting_report)

@router.message(Form.awaiting_report)
async def process_report(message: Message, state: FSMContext):
    if MAINTENANCE_MODE:
        await maintenance_message(message)
        return
    
    report_text = message.text
    user_id = message.from_user.id
        
    report_saved = await save_user_report(user_id, report_text)
        
    if report_saved:
        await message.answer("Thank you for your report. Our support team will review it and get back to you if necessary. If you need immediate assistance, please contact @fixiesupport.")
    else:
        await message.answer("I'm sorry, there was an error processing your report. Please try again later or contact @fixiesupport directly for assistance.")
        
    await state.clear()

@router.message()
async def handle_message(message: Message):
    if MAINTENANCE_MODE:
        await maintenance_message(message)
        return

    user_exists = await check_user_exists(message.from_user.id)
    if not user_exists:
        await message.answer("It seems you're not registered yet. Please start with /start to create your account.")
        return

    agent_id = await get_user_agent_id(message.from_user.id)
    if not agent_id:
        await message.answer("Your Genie The Fixie agent hasn't been set up properly. Please try /start again.")
        return

    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await message.answer("I'm processing your message...")

async def set_commands(bot: Bot):
    if MAINTENANCE_MODE:
        commands = [
            BotCommand(command="/start", description="Maintenance information"),
        ]
    else:
        commands = [
            BotCommand(command="/start", description="Begin interaction or get a welcome message"),
            BotCommand(command="/help", description="Show this help message"),
            BotCommand(command="/delete", description="Delete your account"),
            BotCommand(command="/report", description="Report a bug or get help"),
        ]
    await bot.set_my_commands(commands)

async def main():
    global MAINTENANCE_MODE
    memgpt_server_available = await check_memgpt_server()
    if not memgpt_server_available:
        MAINTENANCE_MODE = True
        logging.warning("MemGPT server is not available. Bot is in maintenance mode.")
    else:
        MAINTENANCE_MODE = False
    
    dp.include_router(router)
    await set_commands(bot)  # Set the bot commands
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())