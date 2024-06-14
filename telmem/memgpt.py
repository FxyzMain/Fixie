import requests
import json
import asyncio
import logging
import random
from db import save_user_api_key, save_user_agent_id, get_user_api_key, get_user_agent_id, get_memgpt_user_id, check_user_exists, save_source_id, get_source_id, save_memgpt_user_id_and_api_key, get_user_pseudonym, delete_user
import os
from dotenv import load_dotenv

load_dotenv()

MEMGPT_ADMIN_API_KEY = os.getenv("MEMGPT_SERVER_PASS")

user_memgpt_id = os.getenv("MEMGPT_USER_ID")
user_api_key = os.getenv("MEMGPT_SERVER_PASS")
source_id = "4972ff4f-de6d-4db2-9296-9dc63635e96e"

# Helper function to make asynchronous HTTP requests
async def async_request(method, url, **kwargs):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: requests.request(method, url, **kwargs))
    return response

async def create_memgpt_user(telegram_user_id: int, pseudonym: str):
    
    agent_response = await async_request(
            'POST',
            'http://localhost:8283/api/agents',
            headers={'Authorization': f'Bearer {user_api_key}', 'Content-Type': 'application/json'},
            json={
                "config": {
                    "user_id": f"{user_memgpt_id}",
                    "name": f"{pseudonym}'s FixieTheGenie",
                    "preset": "memgpt_chat",
                }
            }
        )
    
    if agent_response.status_code == 200:
        agent_data = agent_response.json()
        agent_id = agent_data['agent_state']['id']
        await save_user_agent_id(telegram_user_id, agent_id)
        # Save MemGPT user ID and API key in Supabase
        await save_memgpt_user_id_and_api_key(telegram_user_id, user_memgpt_id, user_api_key)
        await attach_source(agent_id, source_id)


    return "MemGPT user setup completed using static user ID."

async def send_message_to_memgpt(telegram_user_id: int, message_text: str):
    agent_id = await get_user_agent_id(telegram_user_id)

    if not user_api_key or not agent_id:
        return "No API key or agent found. Please start again."
    
    response = await async_request(
        'POST',
        f'http://localhost:8283/api/agents/{agent_id}/messages',
        headers={'Authorization': f'Bearer {user_api_key}'},
        json={'agent_id': agent_id, 'message': message_text, 'stream': True, 'role': 'user'}
    )
    
    if response.status_code == 200:
        # Extract and return assistant message
        assistant_message = None
        for line in response.text.split('\n'):
            if line.startswith('data:'):
                try:
                    data = json.loads(line[len('data:'):])
                    if 'assistant_message' in data:
                        assistant_message = data['assistant_message']
                        break
                except json.JSONDecodeError as e:
                    print("Error parsing JSON:", e)
                    
        if assistant_message:
            return assistant_message
        else:
            return "No assistant message found in response."
    else:
        return "Failed to send message to MemGPT."

async def list_agents(telegram_user_id: int):
    # Check if user already exists in Supabase
    user_exists = await check_user_exists(telegram_user_id)
    if not user_exists:
        return "Create a user first."

    url = "http://localhost:8283/api/agents"
    headers = {"accept": "application/json", "authorization": f"Bearer {user_api_key}"}

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

async def attach_source(agent_id, source_id):
    url = f"http://localhost:8283/api/sources/{source_id}/attach?agent_id={agent_id}"

    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {user_api_key}"
    }

    response = requests.post(url, headers=headers)

    print("Upload.")

async def current_agent(telegram_user_id: int):
    # Check if user already exists in Supabase
    user_exists = await check_user_exists(telegram_user_id)
    if not user_exists:
        return "Create a user first."

    agent_id = await get_user_agent_id(telegram_user_id)
    pseudonym = await get_user_pseudonym(telegram_user_id)

    url = f"http://localhost:8283/api/agents/{agent_id}/config"
    headers = {"accept": "application/json", "authorization": f"Bearer {user_api_key}"}

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = json.loads(response.text)
        
        agent_state = data.get("agent_state", {})
        agent_name = agent_state.get("name", "")

        # Check if agent name contains the user's pseudonym
        if pseudonym and pseudonym in agent_name:
            agent_id = agent_state.get("id", "")
            created_at = agent_state.get("created_at", "")
            preset = agent_state.get("preset", "")

            current_agent_info = f"Your current agent info:\n"
            current_agent_info += f"-----{agent_name}-----\n"
            current_agent_info += f"Agent ID: {agent_id}\n"
            current_agent_info += f"Preset: {preset}\n"
            current_agent_info += f"Creation Date: {created_at}\n"

            return current_agent_info
        else:
            return "No agents found matching your pseudonym."
    else:
        return "Failed to fetch current agent's info."


async def change_agent(telegram_user_id: int, agent_name: str):
    # Check if user already exists in Supabase
    user_exists = await check_user_exists(telegram_user_id)
    if not user_exists:
        return "Create a user first."
    
    # Fetch the list of agents
    agents_info = await list_agents(telegram_user_id)
    
    # Check if agent_name matches any of the agent names
    if agent_name not in agents_info:
        return "Agent not found. Please choose from the available agents."

    agent_id = await name_to_id(agents_info, agent_name)

    await save_user_agent_id(telegram_user_id, agent_id)

    return f"Your agent changed to {agent_name}."

async def delete_agent(telegram_user_id: int, agent_id: str):

    # Check if user already exists in Supabase
    user_exists = await check_user_exists(telegram_user_id)

    if not user_exists:
        return "Create a user first."    

    url = f"http://localhost:8283/api/agents/{agent_id}"
    headers = {"accept": "application/json", "authorization": f"Bearer {user_api_key}"}

    response = requests.delete(url, headers=headers)

    if response.status_code == 200:
        return True
    else:
        return False

async def delete_user_agent(telegram_user_id: int):
    agent_id = await get_user_agent_id(telegram_user_id)
    
    if await delete_agent(telegram_user_id, agent_id):
        if await delete_user(telegram_user_id):
            return True

    