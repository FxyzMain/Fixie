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

class Fixie:
    def __init__(self, name, role, preset, data_sources):
        self.name = name
        self.role = role
        self.preset = preset
        self.data_sources = data_sources

# Update the FIXIES dictionary to use source IDs
FIXIES = {
    "FixieTheGenie": Fixie("FixieTheGenie", "General Assistant", "memgpt_chat", ["ec44d5cb-39ea-4b00-bebc-b9f2ad5ce6aa", "eea587fd-66b9-4877-b784-0cd923ef2df9"]),
    "FixieTheArb": Fixie("FixieTheArb", "Arbitrage Specialist", "memgpt_chat", ["ec44d5cb-39ea-4b00-bebc-b9f2ad5ce6aa"]),
    # Add more Fixies as needed
}

async def get_source_id_by_name(source_name: str):
    url = "http://localhost:8283/api/sources"
    headers = {"accept": "application/json", "authorization": f"Bearer {MEMGPT_ADMIN_API_KEY}"}

    response = await async_request('GET', url, headers=headers)
    
    if response.status_code == 200:
        sources = response.json()
        for source in sources:
            if isinstance(source, dict) and source.get('name') == source_name:
                return source.get('id')
    return None

async def create_memgpt_user(telegram_user_id: int, pseudonym: str):
    fixie = FIXIES["FixieTheGenie"]
    response_text, status_code = await async_request(
        'POST',
        'http://localhost:8283/api/agents',
        headers={'Authorization': f'Bearer {MEMGPT_ADMIN_API_KEY}', 'Content-Type': 'application/json'},
        json={
            "config": {
                "name": f"{pseudonym}'s {fixie.name}",
                "preset": fixie.preset,
                "human": f"Name: {pseudonym}"
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
            result = await attach_source(agent_id, source_id)
            attachment_results.append(result)
            logging.info(f"Attaching source {source_id} to agent {agent_id}: {'Success' if result else 'Failed'}")
        
        if all(attachment_results):
            return f"MemGPT user setup completed. {fixie.name} is ready to assist you!"
        else:
            failed_sources = [source_id for source_id, result in zip(fixie.data_sources, attachment_results) if not result]
            logging.warning(f"Failed to attach sources: {failed_sources} for agent {agent_id}")
            return f"MemGPT user created, but some data sources couldn't be attached. {fixie.name} may have limited knowledge."
    else:
        logging.error(f"Error creating MemGPT user: {status_code} - {response_text}")
        return None

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

async def create_source(user_api_key: str, agent_id: str):

    url = "http://localhost:8283/api/sources"

    payload = { "name": "Docs" }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {user_api_key}"
    }

    response = requests.post(url, json=payload, headers=headers)

    response_dict = json.loads(response.text)

    # Extract the id
    source_id = response_dict['id']


    return source_id

async def upload_to_source(user_api_key: str, source_id):
    url = f"http://localhost:8283/api/sources/{source_id}/upload"

    files = { "file": ("fxyzNetwork.pdf", open("fxyzNetwork.pdf", "rb"), "application/pdf") }
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {user_api_key}"
    }

    response = requests.post(url, files=files, headers=headers)

    print("Upload.")

async def attach_source(agent_id: str, source_id: str):
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
