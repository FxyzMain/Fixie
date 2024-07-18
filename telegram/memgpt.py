import json
import logging
import aiohttp
import os
from dotenv import load_dotenv
from db import save_user_agent_id, get_user_agent_id, check_user_exists, get_user_pseudonym, delete_user
from tenacity import retry, stop_after_attempt, wait_fixed

load_dotenv()

MEMGPT_ADMIN_API_KEY = os.getenv("MEMGPT_SERVER_PASS")
MEMGPT_API_URL = "http://localhost:8283/api"

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def async_request(method, url, **kwargs):
    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, **kwargs) as response:
            return await response.text(), response.status

async def create_memgpt_user(telegram_user_id: int, pseudonym: str):
    fixie_role = "You are Genie The Fixie, a general assistant for the ƒxyzNetwork."
    system_prompt = f"""You are Genie The Fixie, a helpful assistant for the ƒxyzNetwork.
Your human is {pseudonym}, a member of the ƒxyzNetwork.
{fixie_role}"""

    try:
        response_text, status_code = await async_request(
            'POST',
            f'{MEMGPT_API_URL}/agents',
            headers={'Authorization': f'Bearer {MEMGPT_ADMIN_API_KEY}', 'Content-Type': 'application/json'},
            json={
                "config": {
                    "name": f"{pseudonym}'s Genie",
                    "persona_name": "genieTheFixie",
                    "human_name": pseudonym,
                    "system": system_prompt,
                }
            }
        )

        if status_code == 200:
            agent_data = json.loads(response_text)
            agent_id = agent_data['agent_state']['id']
            save_result = await save_user_agent_id(telegram_user_id, agent_id)
            if not save_result:
                logging.error(f"Failed to save agent ID for user {telegram_user_id}")
                return "Error: Failed to save your agent information. Please try again later."
            
            logging.info(f"Created new agent for {pseudonym} with ID: {agent_id}")

            # Attach sources
            fxyz_main_source_id = await get_or_create_source_by_name("fxyzMain")
            otc_source_id = await get_or_create_source_by_name("OTC")
            
            attachment_results = []
            if fxyz_main_source_id:
                attachment_results.append(await attach_source(agent_id, fxyz_main_source_id))
            if otc_source_id:
                attachment_results.append(await attach_source(agent_id, otc_source_id))

            if all(attachment_results):
                return f"MemGPT user setup completed. Genie The Fixie is ready to assist you!"
            elif any(attachment_results):
                return f"MemGPT user created, but some data sources couldn't be attached. Genie The Fixie may have limited knowledge."
            else:
                return f"MemGPT user created, but no data sources were attached. Genie The Fixie may have limited knowledge."
        else:
            logging.error(f"Error creating MemGPT user: {status_code} - {response_text}")
            return f"Error: Failed to create MemGPT user. Status code: {status_code}"
    except Exception as e:
        logging.error(f"Error creating MemGPT user: {str(e)}")
        return f"Error: Failed to create MemGPT user. {str(e)}"

async def send_message_to_memgpt(telegram_user_id: int, message_text: str):
    agent_id = await get_user_agent_id(telegram_user_id)
    if not agent_id:
        return "Error: Your digital agent is not set up. Please start over with /start."

    logging.info(f"Sending message to MemGPT for user {telegram_user_id}, agent {agent_id}")
    
    try:
        response_text, status_code = await async_request(
            'POST',
            f'{MEMGPT_API_URL}/agents/{agent_id}/messages',
            headers={'Authorization': f'Bearer {MEMGPT_ADMIN_API_KEY}'},
            json={'agent_id': agent_id, 'message': message_text, 'stream': True, 'role': 'user'}
        )
        
        if status_code == 200:
            assistant_message = None
            for line in response_text.split('\n'):
                if line.startswith('data:'):
                    try:
                        data = json.loads(line[len('data:'):])
                        if 'assistant_message' in data:
                            assistant_message = data['assistant_message']
                            break
                    except json.JSONDecodeError as e:
                        logging.error(f"Error parsing JSON for user {telegram_user_id}: {e}")
            
            if assistant_message:
                logging.info(f"Received response for user {telegram_user_id}, agent {agent_id}")
                return assistant_message
            else:
                raise Exception("No assistant message found in response")
        else:
            raise Exception(f"Failed to send message to MemGPT. Status code: {status_code}")
    except Exception as e:
        logging.error(f"Error processing message for user {telegram_user_id}: {str(e)}")
        return "I'm sorry, I encountered an error while processing your message. Please try again later or contact @fixiesupport."

async def delete_memgpt_user(telegram_user_id: int):
    agent_id = await get_user_agent_id(telegram_user_id)
    if not agent_id:
        logging.warning(f"No agent found for user {telegram_user_id} during deletion")
        return True

    response_text, status_code = await async_request(
        'DELETE',
        f'{MEMGPT_API_URL}/agents/{agent_id}',
        headers={'Authorization': f'Bearer {MEMGPT_ADMIN_API_KEY}'}
    )

    if status_code == 200:
        logging.info(f"Successfully deleted MemGPT agent for user {telegram_user_id}")
        return True
    else:
        logging.error(f"Failed to delete MemGPT agent for user {telegram_user_id}. Status code: {status_code}")
        return False

async def check_memgpt_server():
    try:
        response_text, status_code = await async_request('GET', f'{MEMGPT_API_URL}/health', headers={'Authorization': f'Bearer {MEMGPT_ADMIN_API_KEY}'})
        return status_code == 200
    except Exception as e:
        logging.error(f"Error checking MemGPT server: {str(e)}")
        return False

async def get_or_create_source_by_name(source_name: str):
    source_id = await get_source_id_by_name(source_name)
    if source_id:
        return source_id
    
    logging.info(f"Source {source_name} not found, attempting to create new source")
    try:
        return await create_source(MEMGPT_ADMIN_API_KEY, source_name)
    except Exception as e:
        logging.error(f"Error creating source {source_name}: {str(e)}")
        return None

async def get_source_id_by_name(source_name: str):
    url = f"{MEMGPT_API_URL}/sources"
    headers = {"accept": "application/json", "authorization": f"Bearer {MEMGPT_ADMIN_API_KEY}"}

    response_text, status_code = await async_request('GET', url, headers=headers)
    
    if status_code == 200:
        data = json.loads(response_text)
        sources = data.get('sources', [])
        for source in sources:
            if source.get('name') == source_name:
                return source.get('id')
    else:
        logging.error(f"Error fetching sources: {status_code}")
    return None

async def create_source(api_key: str, source_name: str):
    url = f"{MEMGPT_API_URL}/sources"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {api_key}"
    }
    payload = {"name": source_name}
    
    response_text, status_code = await async_request('POST', url, headers=headers, json=payload)
    
    if status_code == 200:
        response_data = json.loads(response_text)
        logging.info(f"Successfully created source: {source_name}")
        return response_data.get('id')
    elif status_code == 500 and "already exists" in response_text:
        logging.info(f"Source {source_name} already exists, fetching its ID")
        return await get_source_id_by_name(source_name)
    else:
        logging.error(f"Failed to create source {source_name}. Status code: {status_code}, Response: {response_text}")
        return None

async def attach_source(agent_id: str, source_id: str):
    url = f"{MEMGPT_API_URL}/sources/{source_id}/attach?agent_id={agent_id}"
    headers = {"accept": "application/json", "authorization": f"Bearer {MEMGPT_ADMIN_API_KEY}"}
    
    response_text, status_code = await async_request('POST', url, headers=headers)
    
    if status_code == 200:
        logging.info(f"Source {source_id} attached successfully to agent {agent_id}.")
        return True
    elif status_code == 500 and "agent_id does not exist" in response_text:
        logging.warning(f"Agent {agent_id} not found. Retrying...")
        raise Exception("Agent not found")
    else:
        logging.error(f"Failed to attach source {source_id} to agent {agent_id}. Status code: {status_code}")
        return False