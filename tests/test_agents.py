import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key and base URL from environment variables
API_KEY = os.getenv('MEMGPT_SERVER_PASS')
BASE_URL = os.getenv('MEMGPT_BASE_URL', 'http://localhost:8283')
USER_ID = os.getenv('MEMGPT_USER_ID')

headers = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}

def list_agents():
    print("Fetching agents...")
    response = requests.get(f'{BASE_URL}/api/agents', headers=headers)
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, dict) and 'agents' in data:
            agents = data['agents']
            print(f"\nAvailable agents ({len(agents)}):")
            for agent in agents:
                if isinstance(agent, dict) and 'id' in agent and 'name' in agent:
                    print(f"ID: {agent['id']}, Name: {agent['name']}")
                else:
                    print(f"Unexpected agent format: {agent}")
        else:
            print(f"Unexpected response format. Expected a dict with 'agents' key, got: {type(data)}")
    else:
        print(f"Failed to list agents. Status code: {response.status_code}")
        print(response.text)

def delete_agent(agent_id):
    response = requests.delete(f'{BASE_URL}/api/agents/{agent_id}', headers=headers)
    if response.status_code == 200:
        print(f"Agent with ID {agent_id} has been deleted successfully.")
    else:
        print(f"Failed to delete agent. Status code: {response.status_code}")
        print(response.text)

def delete_all_agents():
    confirm = input("Are you sure you want to delete all agents? This action cannot be undone. (y/n): ")
    if confirm.lower() != 'y':
        print("Operation cancelled.")
        return

    response = requests.get(f'{BASE_URL}/api/agents', headers=headers)
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, dict) and 'agents' in data:
            agents = data['agents']
            total = len(agents)
            print(f"Deleting {total} agents...")
            for i, agent in enumerate(agents, 1):
                if isinstance(agent, dict) and 'id' in agent:
                    delete_agent(agent['id'])
                    print(f"Deleted agent {i}/{total}")
            print("All agents have been deleted.")
        else:
            print(f"Unexpected response format. Expected a dict with 'agents' key, got: {type(data)}")
    else:
        print(f"Failed to list agents for deletion. Status code: {response.status_code}")
        print(response.text)

def main():
    while True:
        print("\n1. List agents")
        print("2. Delete specific agent")
        print("3. Delete all agents")
        print("4. Exit")
        choice = input("Enter your choice (1-4): ")

        if choice == '1':
            list_agents()
        elif choice == '2':
            agent_id = input("Enter the ID of the agent to delete: ")
            delete_agent(agent_id)
        elif choice == '3':
            delete_all_agents()
        elif choice == '4':
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()