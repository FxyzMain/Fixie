from supabase import create_client, Client
import os
from dotenv import load_dotenv
import postgrest.exceptions
import asyncio
import logging

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

print(f"SUPABASE_URL: {SUPABASE_URL}")
print(f"SUPABASE_SERVICE_ROLE_KEY: {SUPABASE_SERVICE_ROLE_KEY}")

# Initialize Supabase client with the service role key
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

logging.basicConfig(level=logging.INFO)

async def get_user_api_key(telegram_user_id: int) -> str:
    loop = asyncio.get_event_loop()
    # Change from "users" to "users3"
    data, error = await loop.run_in_executor(None, lambda: supabase.table("users3").select("api_key").eq("telegram_user_id", telegram_user_id).execute())
    logging.info(f"Data fetched for API key: {data}, Error: {error}")

    # Check if 'api_key' key exists
    if data[1][0].get('api_key'):
        # Extracting the value of 'api_key'
        api_key_value = data[1][0]['api_key']
        logging.info(f"Returning API_key: {api_key_value}")
        return api_key_value
    else:
        logging.error("Missing 'api_key' field.")
    
    return None

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

async def get_memgpt_user_id(telegram_user_id: int) -> str:
    loop = asyncio.get_event_loop()
    data, error = await loop.run_in_executor(None, lambda: supabase.table("users3").select("memgpt_user_id").eq("telegram_user_id", telegram_user_id).execute())
    logging.info(f"Data fetched for memgpt_user_id: {data}, Error: {error}")

    # Check if 'memgpt_user_id' key exists
    if data[1][0].get('memgpt_user_id'):
        # Extracting the value of 'memgpt_user_id'
        memgpt_user_id_value = data[1][0]['memgpt_user_id']
        logging.info(f"Returning memgpt_user_id: {memgpt_user_id_value}")
        return memgpt_user_id_value
    else:
        logging.error("Missing 'memgpt_user_id' field.")
    
    return None

async def save_user_api_key(telegram_user_id: int, user_api_key: str):
    loop = asyncio.get_event_loop()
    data, error = await loop.run_in_executor(None, lambda: supabase.table("users3").upsert({"telegram_user_id": telegram_user_id, "api_key": user_api_key}).execute())
    if error and isinstance(error, tuple) and error[0] != 'count':
        raise Exception(f"Failed to save or update user API key: {error}")

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

async def save_memgpt_user_id_and_api_key(telegram_user_id: int, memgpt_user_id: str, user_api_key: str):
    loop = asyncio.get_event_loop()
    data, error = await loop.run_in_executor(None, lambda: supabase.table("users3").update({"memgpt_user_id": memgpt_user_id, "api_key": user_api_key}).eq("telegram_user_id", telegram_user_id).execute())
    if error and isinstance(error, tuple) and error[0] != 'count':
        raise Exception(f"Failed to save MemGPT user ID and API key: {error}")
    return data

async def save_user_pseudonym(telegram_user_id: int, pseudonym: str):
    loop = asyncio.get_event_loop()
    try:
        data, error = await loop.run_in_executor(None, lambda: supabase.table("users3").upsert({"telegram_user_id": telegram_user_id, "pseudonym": pseudonym}).execute())
        # Check if the operation was successful by examining the error variable correctly
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

    # Check if 'pseudonym' key exists
    if data[1] and data[1][0].get('pseudonym'):
        # Extracting the value of 'pseudonym'
        pseudonym_value = data[1][0]['pseudonym']
        logging.info(f"Returning pseudonym: {pseudonym_value}")
        return pseudonym_value
    else:
        logging.error("Missing 'pseudonym' field.")
    
    return None

async def save_source_id(telegram_user_id: int, source_id: str):
    loop = asyncio.get_event_loop()
    try:
        data, error = await loop.run_in_executor(None, lambda: supabase.table("users3").update({"source_id": source_id}).eq("telegram_user_id", telegram_user_id).execute())
        # Check if the operation was successful by examining the error variable correctly
        if error and error[0] != 'count':
            logging.error(f"Failed to save source_id for Telegram user ID {telegram_user_id}: {error}")
            return False
        else:
            logging.info(f"Source_id saved successfully for Telegram user ID {telegram_user_id}.")
            return True
    except Exception as e:
        logging.error(f"Exception occurred while saving source_id for Telegram user ID {telegram_user_id}: {e}")
        return False

async def get_source_id(telegram_user_id: int):
    loop = asyncio.get_event_loop()
    data, error = await loop.run_in_executor(None, lambda: supabase.table("users3").select("source_id").eq("telegram_user_id", telegram_user_id).execute())
    logging.info(f"Data fetched for memgpt_user_id: {data}, Error: {error}")

    # Check if 'memgpt_user_id' key exists
    if data[1][0].get('source_id'):
        # Extracting the value of 'memgpt_user_id'
        source_id = data[1][0]['source_id']
        logging.info(f"Returning source_id: {source_id}")
        return source_id
    else:
        logging.error("Missing 'source_id' field.")
    
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
        
