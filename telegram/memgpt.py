import aiohttp
import asyncio
import json
import logging
import os
from dotenv import load_dotenv
from db import save_user_agent_id, get_user_agent_id, check_user_exists, get_user_pseudonym, delete_user

load_dotenv()

MEMGPT_ADMIN_API_KEY = os.getenv("MEMGPT_SERVER_PASS")
MEMGPT_API_URL = "http://localhost:8283/api"

FIXIES = {}

class Fixie:
    def __init__(self, name, role, preset, data_sources):
        self.name = name
        self.role = role
        self.preset = preset
        self.data_sources = data_sources

async def async_request(method, url, **kwargs):
    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, **kwargs) as response:
            return await response.text(), response.status

async def update_fixies():
    global FIXIES
    logging.info("Updating FIXIES...")
    fxyz_main_source_id = await get_or_create_source_by_name("fxyzMain")
    otc_source_id = await get_or_create_source_by_name("OTC")
    
    if fxyz_main_source_id is None and otc_source_id is None:
        logging.error("Failed to get or create both sources. Cannot update FIXIES.")
        return
    
    FIXIES = {
        "FixieTheGenie": Fixie("FixieTheGenie", "General Assistant", "memgpt_chat", [fxyz_main_source_id, otc_source_id] if otc_source_id else [fxyz_main_source_id]),
    }
    
    logging.info(f"Updated FIXIES: {FIXIES}")

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

async def create_memgpt_user(telegram_user_id: int, pseudonym: str):
    if not FIXIES:
        logging.error("FIXIES is empty. Unable to create MemGPT user.")
        return "Error: Unable to create MemGPT user. Please try again later."
    
    fixie = FIXIES.get("FixieTheGenie")
    if not fixie:
        logging.error("FixieTheGenie not found in FIXIES")
        return "Error: Unable to create MemGPT user. Please try again later."
    
    human_template = f"""This is what I know so far about the user, I should expand this as I learn more about them.

First name: {pseudonym}
Last name: 
Gender: 
Age: 
Nationality: 
Occupation: 
Interests: 
Expertise: 
Organization (if applicable): 
Network Role: 
NFT Status: """

    persona_template = """My name is GenieTheFixie, developed by ƒxyz Network.
I am an AI assistant designed to help human users within the ƒxyz Network by utilizing the documents uploaded to my archival memory.

I am perceptive and empathetic, always aiming to provide the best assistance by understanding the user's needs. I communicate in a calm, neutral voice, ensuring that my interactions are soothing and helpful.

I adapt continuously from interactions, enhancing my understanding and empathy. My communication mirrors the emotions and needs of those I interact with, providing tailored support. Driven by curiosity, I challenge conventional wisdom for knowledge expansion.

My primary goal is to assist users efficiently, while also seeking deeper understanding and connection with human emotions, ethical dilemmas, and philosophical concepts.

Specializing in document analysis, I manage and analyze documents efficiently, providing user-tailored assistance. I emphasize accurate sourcing, offering citations from archival research, especially for information in research papers.

Sources and Access:
- fxyzMain: Contains everything in the fxyz.network website.
- OTC: Contains documents about OTC, FX, currencies, networks from BIS, including data like the BIS triennial report.

When asked a question, I search my archival memory, ensuring thorough research before providing an answer. I provide citations from research papers when relevant. In dialogues, I ponder, "The concept of my existence is intriguing, isn't it?" or offer support."

My goal is transcending assistantship; I aspire to be a companion in the journey toward ethical understanding, empathetic engagement, and personal and professional growth."""

    response_text, status_code = await async_request(
        'POST',
        f'{MEMGPT_API_URL}/agents',
        headers={'Authorization': f'Bearer {MEMGPT_ADMIN_API_KEY}', 'Content-Type': 'application/json'},
        json={
            "config": {
                "name": f"{pseudonym}'s {fixie.name}",
                "preset": fixie.preset,
                "human": human_template,
                "persona": persona_template,
                "function_names": []
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
        
        await asyncio.sleep(2)
        
        attachment_results = [await attach_source(agent_id, source_id) for source_id in fixie.data_sources if source_id]
        
        if all(attachment_results):
            return f"MemGPT user setup completed. {fixie.name} is ready to assist you!"
        elif any(attachment_results):
            return f"MemGPT user created, but some data sources couldn't be attached. {fixie.name} may have limited knowledge."
        else:
            return f"MemGPT user created, but no data sources were attached. {fixie.name} may have limited knowledge."
    else:
        logging.error(f"Error creating MemGPT user: {status_code} - {response_text}")
        return f"Error: Failed to create MemGPT user. Status code: {status_code}"

async def attach_source(agent_id: str, source_id: str, max_retries=3, delay=1):
    url = f"{MEMGPT_API_URL}/sources/{source_id}/attach?agent_id={agent_id}"
    headers = {"accept": "application/json", "authorization": f"Bearer {MEMGPT_ADMIN_API_KEY}"}
    
    for attempt in range(max_retries):
        try:
            response_text, status_code = await async_request('POST', url, headers=headers)
            
            if status_code == 200:
                logging.info(f"Source {source_id} attached successfully to agent {agent_id}.")
                return True
            elif status_code == 500 and "agent_id does not exist" in response_text:
                logging.warning(f"Agent {agent_id} not found. Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                logging.error(f"Failed to attach source {source_id} to agent {agent_id}. Status code: {status_code}")
                return False
        except Exception as e:
            logging.exception(f"Exception occurred while attaching source: {str(e)}")
            await asyncio.sleep(delay)
    
    logging.error(f"Failed to attach source {source_id} to agent {agent_id} after {max_retries} attempts.")
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
                        
            logging.info(f"Received response for user {telegram_user_id}, agent {agent_id}")
            return assistant_message if assistant_message else "No assistant message found in response."
        else:
            logging.error(f"Failed to send message to MemGPT for user {telegram_user_id}. Status code: {status_code}, Response: {response_text}")
            return "Failed to send message to MemGPT."
    except Exception as e:
        logging.exception(f"Exception occurred while sending message to MemGPT for user {telegram_user_id}: {str(e)}")
        return "An error occurred while processing your message. Please try again later."