import aiohttp
import asyncio
import json
import logging
import os
from dotenv import load_dotenv
from db import save_user_agent_id, get_user_agent_id, check_user_exists, get_user_pseudonym, delete_user
from tenacity import retry, stop_after_attempt, wait_fixed
from memgpt.memory import BaseMemory, MemoryModule

load_dotenv()

MEMGPT_ADMIN_API_KEY = os.getenv("MEMGPT_SERVER_PASS")
MEMGPT_API_URL = "http://localhost:8283/api"

class FixieMemory(BaseMemory):
    def __init__(self, persona: str, human: str, fixie_role: str, limit: int = 2000):
        self.memory = {
            "persona": MemoryModule(name="persona", value=persona, limit=limit),
            "human": MemoryModule(name="human", value=human, limit=limit),
            "fixie_role": MemoryModule(name="fixie_role", value=fixie_role, limit=limit),
        }

    def core_memory_append(self, name: str, content: str) -> Optional[str]:
        """
        Append to the contents of core memory.

        Args:
            name (str): Section of the memory to be edited (persona, human, or fixie_role).
            content (str): Content to write to the memory. All unicode (including emojis) are supported.

        Returns:
            Optional[str]: None is always returned as this function does not produce a response.
        """
        self.memory[name].value += "\n" + content
        return None

    def core_memory_replace(self, name: str, old_content: str, new_content: str) -> Optional[str]:
        """
        Replace the contents of core memory. To delete memories, use an empty string for new_content.

        Args:
            name (str): Section of the memory to be edited (persona, human, or fixie_role).
            old_content (str): String to replace. Must be an exact match.
            new_content (str): Content to write to the memory. All unicode (including emojis) are supported.

        Returns:
            Optional[str]: None is always returned as this function does not produce a response.
        """
        self.memory[name].value = self.memory[name].value.replace(old_content, new_content)
        return None

async def create_memgpt_user(telegram_user_id: int, pseudonym: str):
    fixie_role = "You are Genie The Fixie, a general assistant for the ƒxyzNetwork."
    memory = FixieMemory(
        persona="I am Genie The Fixie, a helpful assistant for the ƒxyzNetwork.",
        human=f"I am {pseudonym}, a member of the ƒxyzNetwork.",
        fixie_role=fixie_role
    )

    response_text, status_code = await async_request(
        'POST',
        f'{MEMGPT_API_URL}/agents',
        headers={'Authorization': f'Bearer {MEMGPT_ADMIN_API_KEY}', 'Content-Type': 'application/json'},
        json={
            "name": f"{pseudonym}'s Genie",
            "memory": memory,
            "system_prompt": fixie_role,
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
        return f"MemGPT user setup completed. Genie The Fixie is ready to assist you!"
    else:
        logging.error(f"Error creating MemGPT user: {status_code} - {response_text}")
        return f"Error: Failed to create MemGPT user. Status code: {status_code}"

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
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
            json={'message': message_text, 'stream': True, 'role': 'user'}
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
        logging.exception(f"Exception occurred while sending message to MemGPT for user {telegram_user_id}: {str(e)}")
        raise

async def delete_memgpt_user(telegram_user_id: int):
    agent_id = await get_user_agent_id(telegram_user_id)
    if not agent_id:
        logging.warning(f"No agent found for user {telegram_user_id} during deletion")
        return True  # Consider it a success if there's no agent to delete

    url = f"{MEMGPT_API_URL}/agents/{agent_id}"
    headers = {"accept": "application/json", "authorization": f"Bearer {MEMGPT_ADMIN_API_KEY}"}

    response_text, status_code = await async_request('DELETE', url, headers=headers)

    if status_code == 200:
        logging.info(f"Successfully deleted MemGPT agent for user {telegram_user_id}")
        return True
    else:
        logging.error(f"Failed to delete MemGPT agent for user {telegram_user_id}. Status code: {status_code}")
        return False

async def check_memgpt_server():
    try:
        # Replace this with an actual health check endpoint of your MemGPT server
        response_text, status_code = await async_request('GET', f'{MEMGPT_API_URL}/health', headers={'Authorization': f'Bearer {MEMGPT_ADMIN_API_KEY}'})
        return status_code == 200
    except Exception as e:
        logging.error(f"Error checking MemGPT server: {str(e)}")
        return False