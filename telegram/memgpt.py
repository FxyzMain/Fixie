import aiohttp
import asyncio
import json
import logging
import os
from dotenv import load_dotenv
from db import save_user_agent_id, get_user_agent_id, check_user_exists, get_user_pseudonym, delete_user
from tenacity import retry, stop_after_attempt, wait_fixed
from memgpt.memory import BaseMemory, MemoryModule
from memgpt.agent import Agent
from memgpt.client import Client

load_dotenv()

MEMGPT_ADMIN_API_KEY = os.getenv("MEMGPT_SERVER_PASS")
MEMGPT_API_URL = "http://localhost:8283/api"

client = Client(api_key=MEMGPT_ADMIN_API_KEY, base_url=MEMGPT_API_URL)

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

    try:
        agent = client.create_agent(
            name=f"{pseudonym}'s Genie",
            memory=memory,
            system_prompt=fixie_role,
        )

        agent_id = agent.id
        save_result = await save_user_agent_id(telegram_user_id, agent_id)
        if not save_result:
            logging.error(f"Failed to save agent ID for user {telegram_user_id}")
            return "Error: Failed to save your agent information. Please try again later."
        
        logging.info(f"Created new agent for {pseudonym} with ID: {agent_id}")
        return f"MemGPT user setup completed. Genie The Fixie is ready to assist you!"
    except Exception as e:
        logging.error(f"Error creating MemGPT user: {str(e)}")
        return f"Error: Failed to create MemGPT user. {str(e)}"

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def send_message_to_memgpt(telegram_user_id: int, message_text: str):
    agent_id = await get_user_agent_id(telegram_user_id)

    if not agent_id:
        logging.error(f"No agent found for user {telegram_user_id}")
        return "No agent found. Please start again with /start."
    
    logging.info(f"Sending message to MemGPT for user {telegram_user_id}, agent {agent_id}")
    
    try:
        agent = client.get_agent(agent_id)
        response = agent.send_message(message_text)
        return response.content
    except Exception as e:
        logging.error(f"Error processing message for user {telegram_user_id}: {str(e)}")
        return "I'm sorry, I encountered an error while processing your message. Please try again later or contact @fixiesupport."

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