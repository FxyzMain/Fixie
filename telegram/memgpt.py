import requests
import json
import asyncio
import logging
from db import save_user_api_key, save_user_agent_id, get_user_agent_id, check_user_exists, save_source_id, get_source_id, save_memgpt_user_id_and_api_key, get_user_pseudonym, delete_user
import os
from dotenv import load_dotenv

load_dotenv()

MEMGPT_ADMIN_API_KEY = os.getenv("MEMGPT_SERVER_PASS")

# Helper function to make asynchronous HTTP requests
import aiohttp

async def async_request(method, url, **kwargs):
    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, **kwargs) as response:
            return await response.text(), response.status

# At the top of the file
global FIXIES
FIXIES = {}

class Fixie:
    def __init__(self, name, role, preset, data_sources):
        self.name = name
        self.role = role
        self.preset = preset
        self.data_sources = data_sources

async def update_fixies():
    global FIXIES
    logging.info("Updating FIXIES...")
    fxyz_main_source_id = await get_or_create_source_by_name("fxyzMain")
    otc_source_id = await get_or_create_source_by_name("OTC")
    
    logging.info(f"fxyz_main_source_id: {fxyz_main_source_id}")
    logging.info(f"otc_source_id: {otc_source_id}")
    
    if fxyz_main_source_id is None and otc_source_id is None:
        logging.error("Failed to get or create both sources. Cannot update FIXIES.")
        return
    
    FIXIES = {}
    if fxyz_main_source_id:
        FIXIES["FixieTheGenie"] = Fixie("FixieTheGenie", "General Assistant", "memgpt_chat", [fxyz_main_source_id])
        if otc_source_id:
            FIXIES["FixieTheGenie"].data_sources.append(otc_source_id)
    
    if fxyz_main_source_id:
        FIXIES["FixieTheArb"] = Fixie("FixieTheArb", "Arbitrage Specialist", "memgpt_chat", [fxyz_main_source_id])
    
    logging.info(f"Updated FIXIES: {FIXIES}")

async def get_source_id_by_name(source_name: str):
    url = "http://localhost:8283/api/sources"
    headers = {"accept": "application/json", "authorization": f"Bearer {MEMGPT_ADMIN_API_KEY}"}

    response_text, status_code = await async_request('GET', url, headers=headers)
    
    if status_code == 200:
        data = json.loads(response_text)
        if isinstance(data, dict) and 'sources' in data:
            sources = data['sources']
            for source in sources:
                if source.get('name') == source_name:
                    return source.get('id')
    else:
        logging.error(f"Error fetching sources: {status_code}")
    return None

async def get_or_create_source_by_name(source_name: str):
    source_id = await get_source_id_by_name(source_name)
    if source_id:
        logging.info(f"Source {source_name} already exists with id {source_id}")
        return source_id
    
    logging.info(f"Source {source_name} not found, attempting to create new source")
    try:
        source_id = await create_source(MEMGPT_ADMIN_API_KEY, source_name)
        if source_id:
            logging.info(f"Successfully created source {source_name} with id {source_id}")
            return source_id
        else:
            logging.error(f"Failed to create source {source_name}, attempting to fetch again")
            return await get_source_id_by_name(source_name)
    except Exception as e:
        logging.error(f"Error creating source {source_name}: {str(e)}")
        # If creation failed, try to fetch the ID one more time
        return await get_source_id_by_name(source_name)

async def create_source(api_key: str, source_name: str):
    url = "http://localhost:8283/api/sources"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {api_key}"
    }
    payload = {"name": source_name}
    
    try:
        response_text, status_code = await async_request('POST', url, headers=headers, json=payload)
        logging.info(f"Create source response: Status {status_code}, Content: {response_text}")
        
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
    except Exception as e:
        logging.exception(f"Exception occurred while creating source {source_name}: {str(e)}")
        return None

async def create_memgpt_user(telegram_user_id: int, pseudonym: str):
    await update_fixies()  # Ensure FIXIES is updated before use
    if not FIXIES:
        logging.error("FIXIES is empty. Unable to create MemGPT user.")
        return "Error: Unable to create MemGPT user. Please try again later."
    
    logging.info(f"FIXIES content: {FIXIES}")
    
    if "FixieTheGenie" not in FIXIES:
        logging.error("FixieTheGenie not found in FIXIES")
        return "Error: Unable to create MemGPT user. Please try again later."
    
    fixie = FIXIES["FixieTheGenie"]
    response_text, status_code = await async_request(
        'POST',
        'http://localhost:8283/api/agents',
        headers={'Authorization': f'Bearer {MEMGPT_ADMIN_API_KEY}', 'Content-Type': 'application/json'},
        json={
            "config": {
                "name": f"{pseudonym}'s {fixie.name}",
                "preset": fixie.preset,
                "human": f"Name: {pseudonym}",
                "function_names": []
            }
        }
    )
    
    if status_code == 200:
        agent_data = json.loads(response_text)
        agent_id = agent_data['agent_state']['id']
        await save_user_agent_id(telegram_user_id, agent_id)
        
        logging.info(f"Created new agent for {pseudonym} with ID: {agent_id}")
        
        attachment_results = []
        for source_id in fixie.data_sources:
            if source_id:
                result = await attach_source(agent_id, source_id)
                attachment_results.append(result)
                logging.info(f"Attaching source {source_id} to agent {agent_id}: {'Success' if result else 'Failed'}")
            else:
                logging.warning(f"Skipping attachment of invalid source_id: None")
        
        if all(attachment_results):
            return f"MemGPT user setup completed. {fixie.name} is ready to assist you!"
        elif any(attachment_results):
            return f"MemGPT user created, but some data sources couldn't be attached. {fixie.name} may have limited knowledge."
        else:
            return f"MemGPT user created, but no data sources were attached. {fixie.name} may have limited knowledge."
    else:
        logging.error(f"Error creating MemGPT user: {status_code} - {response_text}")
        return None

async def attach_source(agent_id: str, source_id: str):
    if not source_id or not agent_id:
        logging.warning(f"Invalid source_id or agent_id")
        return False

    url = f"http://localhost:8283/api/sources/{source_id}/attach?agent_id={agent_id}"
    headers = {"accept": "application/json", "authorization": f"Bearer {MEMGPT_ADMIN_API_KEY}"}
    
    try:
        response_text, status_code = await async_request('POST', url, headers=headers)
        logging.info(f"Attach response status code: {status_code}")
        logging.info(f"Attach response content: {response_text}")
        
        if status_code == 200:
            logging.info(f"Source {source_id} attached successfully to agent {agent_id}.")
            return True
        else:
            logging.error(f"Failed to attach source {source_id} to agent {agent_id}. Status code: {status_code}")
            return False
    except Exception as e:
        logging.exception(f"Exception occurred while attaching source: {str(e)}")
        return False

async def send_message_to_memgpt(telegram_user_id: int, message_text: str):
    agent_id = await get_user_agent_id(telegram_user_id)

    if not agent_id:
        logging.error(f"No agent found for user {telegram_user_id}")
        return "No agent found. Please start again with /start."
    
    logging.info(f"Sending message to MemGPT for user {telegram_user_id}, agent {agent_id}")
    
    try:
        response_text, status_code = await async_request(
            'POST',
            f'http://localhost:8283/api/agents/{agent_id}/messages',
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
                        
            logging.info(f"Received response for user {telegram_user_id}, agent {agent_id}")
            return assistant_message if assistant_message else "No assistant message found in response."
        else:
            logging.error(f"Failed to send message to MemGPT for user {telegram_user_id}. Status code: {status_code}, Response: {response_text}")
            return "Failed to send message to MemGPT."
    except Exception as e:
        logging.exception(f"Exception occurred while sending message to MemGPT for user {telegram_user_id}: {str(e)}")
        return "An error occurred while processing your message. Please try again later."

async def list_agents(telegram_user_id: int):
    # Check if user already exists in Supabase
    user_exists = await check_user_exists(telegram_user_id)
    if not user_exists:
        return "Create a user first."

    url = "http://localhost:8283/api/agents"
    headers = {"accept": "application/json", "authorization": f"Bearer {MEMGPT_ADMIN_API_KEY}"}

    response = requests.get(url, headers=headers)

    pseudonym = await get_user_pseudonym(telegram_user_id)

    if response.status_code == 200:
        data = json.loads(response.text)
        agents = data.get("agents", [])
        
        agent_info = "-" * 7 + "\n"
        
        # Filter agents whose names include the pseudonym
        filtered_agents = [agent for agent in agents if pseudonym and pseudonym in agent.get("name", "")]
        
        # Debugging: Log the pseudonym and filtered agents
        logging.info(f"Pseudonym: {pseudonym}")
        logging.info(f"Filtered Agents: {filtered_agents}")
        
        for agent in filtered_agents:
            name = agent.get("name", "")
            agent_id = agent.get("id", "")
            persona = agent.get("persona", "")
            created_at = agent.get("created_at", "")
            
            agent_info += f"Agent Name: {name}\n"
            agent_info += f"Agent ID: {agent_id}\n"
            agent_info += f"Persona: {persona}\n"
            agent_info += f"Creation Date: {created_at}\n"
            agent_info += "-------\n"
        
        return agent_info if filtered_agents else "No agents found with the specified pseudonym."
    else:
        return "Failed to fetch agents data."
    
async def create_agent(telegram_user_id: int, agent_name: str):
    # Check if user already exists in Supabase
    user_exists = await check_user_exists(telegram_user_id)
    if not user_exists:
        return "Create a user first."

    user_api_key = await get_user_api_key(telegram_user_id)
    user_memgpt_id = await get_memgpt_user_id(telegram_user_id)
    agent_response = await async_request(
            'POST',
            'http://localhost:8283/api/agents',
            headers={'Authorization': f'Bearer {user_api_key}', 'Content-Type': 'application/json'},
            json={
                "config": {
                    "user_id": f"{user_memgpt_id}",
                    "name" : f"{agent_name}",
                    "preset": "memgpt_chat",
                }
            }
        )

    if agent_response.status_code == 200:
        agents_info = await list_agents(telegram_user_id)
        
        agent_id = await name_to_id(agents_info, agent_name)

        source_id = await get_source_id(telegram_user_id)
        print 
        await attach_source(user_api_key, agent_id, source_id)

        return "Your MemGPT agent has been created."
    else:
        return "Failed to create MemGPT agent."
