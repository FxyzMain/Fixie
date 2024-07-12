from supabase import create_client, Client
import os
from dotenv import load_dotenv
import postgrest.exceptions
import asyncio
import logging
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

logging.basicConfig(level=logging.INFO)

async def get_user_agent_id(telegram_user_id: int):
    loop = asyncio.get_event_loop()
    data, error = await loop.run_in_executor(None, lambda: supabase.table("users3").select("agent_id").eq("telegram_user_id", telegram_user_id).execute())
    logging.info(f"Data fetched for agent_id: {data}, Error: {error}")

    if data[1] and data[1][0].get('agent_id'):
        agent_id = data[1][0]['agent_id']
        logging.info(f"Returning agent_id: {agent_id}")
        return agent_id
    else:
        logging.error("Missing 'agent_id' field.")
    
    return None

async def save_user_agent_id(telegram_user_id: int, agent_id: str):
    loop = asyncio.get_event_loop()
    try:
        data, error = await loop.run_in_executor(None, lambda: supabase.table("users3").update({"agent_id": agent_id}).eq("telegram_user_id", telegram_user_id).execute())
        if error and error[0] != 'count':
            logging.error(f"Failed to update agent ID for Telegram user ID {telegram_user_id}: {error}")
            return False
        else:
            logging.info(f"Agent ID {agent_id} updated successfully for Telegram user ID {telegram_user_id}.")
            return True
    except Exception as e:
        logging.error(f"An error occurred while saving agent ID: {e}")
        return False

async def get_memgpt_user_id(telegram_user_id: int) -> str:
    loop = asyncio.get_event_loop()
    data, error = await loop.run_in_executor(None, lambda: supabase.table("users3").select("memgpt_user_id").eq("telegram_user_id", telegram_user_id).execute())
    logging.info(f"Data fetched for memgpt_user_id: {data}, Error: {error}")

    if data[1] and data[1][0].get('memgpt_user_id'):
        memgpt_user_id_value = data[1][0]['memgpt_user_id']
        logging.info(f"Returning memgpt_user_id: {memgpt_user_id_value}")
        return memgpt_user_id_value
    else:
        logging.error("Missing 'memgpt_user_id' field.")
    
    return None

async def check_user_exists(telegram_user_id: int) -> bool:
    try:
        loop = asyncio.get_event_loop()
        data, error = await loop.run_in_executor(None, lambda: supabase.table("users3").select("id").eq("telegram_user_id", telegram_user_id).execute())
        if data and data[1]:
            logging.info(f"User with Telegram user ID {telegram_user_id} already exists.")
            return True
        else:
            logging.info(f"User with Telegram user ID {telegram_user_id} does not exist.")
            return False
    except Exception as e:
        logging.exception("Unexpected error checking if user exists", exc_info=e)
        return False

async def save_memgpt_user_id(telegram_user_id: int, memgpt_user_id: str):
    loop = asyncio.get_event_loop()
    data, error = await loop.run_in_executor(None, lambda: supabase.table("users3").update({"memgpt_user_id": memgpt_user_id}).eq("telegram_user_id", telegram_user_id).execute())
    if error and isinstance(error, tuple) and error[0] != 'count':
        raise Exception(f"Failed to save MemGPT user ID: {error}")
    return data

async def save_user_pseudonym(telegram_user_id: int, pseudonym: str):
    loop = asyncio.get_event_loop()
    try:
        data, error = await loop.run_in_executor(None, lambda: supabase.table("users3").upsert({"telegram_user_id": telegram_user_id, "pseudonym": pseudonym}).execute())
        if error and error[0] != 'count':
            logging.error(f"Failed to save pseudonym for Telegram user ID {telegram_user_id}: {error}")
            return False
        else:
            logging.info(f"Pseudonym saved successfully for Telegram user ID {telegram_user_id}.")
            return True
    except Exception as e:
        logging.error(f"Exception occurred while saving pseudonym for Telegram user ID {telegram_user_id}: {e}")
        return False

async def get_user_pseudonym(telegram_user_id: int) -> str:
    loop = asyncio.get_event_loop()
    data, error = await loop.run_in_executor(None, lambda: supabase.table("users3").select("pseudonym").eq("telegram_user_id", telegram_user_id).execute())
    logging.info(f"Data fetched for pseudonym: {data}, Error: {error}")

    if data[1] and data[1][0].get('pseudonym'):
        pseudonym_value = data[1][0]['pseudonym']
        logging.info(f"Returning pseudonym: {pseudonym_value}")
        return pseudonym_value
    else:
        logging.error("Missing 'pseudonym' field.")
    
    return None

async def get_user_info(telegram_user_id: int):
    loop = asyncio.get_event_loop()
    data, error = await loop.run_in_executor(None, lambda: supabase.table("users3").select("*").eq("telegram_user_id", telegram_user_id).execute())
    if data and data[1]:
        return data[1][0]  # Return the first record
    return None

async def delete_user(telegram_user_id: int):
    loop = asyncio.get_event_loop()
    data, error = await loop.run_in_executor(None, lambda: supabase.table("users3").delete().eq("telegram_user_id", telegram_user_id).execute())
    if error and error[0] != 'count':
        logging.error(f"Failed to delete user {telegram_user_id}: {error}")
        return False
    else:
        logging.info(f"Deleted user: {telegram_user_id}.")
        return True

async def save_user_report(telegram_user_id: int, report_text: str):
    loop = asyncio.get_event_loop()
    try:
        data, error = await loop.run_in_executor(None, lambda: supabase.table("user_reports").insert({
            "telegram_user_id": telegram_user_id,
            "report_text": report_text,
            "status": "pending"  # Default status
        }).execute())
        if error and error[0] != 'count':  # Ignore 'count' errors
            logging.error(f"Failed to save report for Telegram user ID {telegram_user_id}: {error}")
            return False
        else:
            logging.info(f"Report saved successfully for Telegram user ID {telegram_user_id}.")
            return True
    except Exception as e:
        logging.error(f"Exception occurred while saving report for Telegram user ID {telegram_user_id}: {e}")
        return False

async def get_user_reports(telegram_user_id: int):
    loop = asyncio.get_event_loop()
    try:
        data, error = await loop.run_in_executor(None, lambda: supabase.table("user_reports")
            .select("*")
            .eq("telegram_user_id", telegram_user_id)
            .order("created_at", desc=True)
            .execute())
        if error:
            logging.error(f"Failed to retrieve reports for Telegram user ID {telegram_user_id}: {error}")
            return None
        else:
            return data[1] if data and data[1] else []
    except Exception as e:
        logging.error(f"Exception occurred while retrieving reports for Telegram user ID {telegram_user_id}: {e}")
        return None

async def update_report_status(report_id: int, new_status: str):
    loop = asyncio.get_event_loop()
    try:
        data, error = await loop.run_in_executor(None, lambda: supabase.table("user_reports")
            .update({"status": new_status})
            .eq("id", report_id)
            .execute())
        if error:
            logging.error(f"Failed to update status for report ID {report_id}: {error}")
            return False
        else:
            logging.info(f"Status updated successfully for report ID {report_id}.")
            return True
    except Exception as e:
        logging.error(f"Exception occurred while updating status for report ID {report_id}: {e}")
        return False