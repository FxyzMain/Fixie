import requests
import json
import logging

logging.basicConfig(level=logging.INFO)

base_url = "http://localhost:8283/api"
headers = {
    "accept": "application/json",
    "authorization": "Bearer ilovellms"
}

def get_sources():
    try:
        response = requests.get(f"{base_url}/sources", headers=headers)
        logging.info(f"Response status code: {response.status_code}")
        logging.info(f"Response content: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and 'sources' in data:
                return data['sources']
            else:
                logging.error(f"Unexpected response format. Expected a dict with 'sources' key, got: {type(data)}")
                return None
        else:
            logging.error(f"Error fetching sources: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Request exception: {e}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {e}")
        return None

def main():
    sources = get_sources()
    if sources:
        logging.info("Available sources:")
        for source in sources:
            logging.info(f"- Name: {source['name']}")
            logging.info(f"  ID: {source['id']}")
            logging.info(f"  Description: {source['description']}")
            logging.info(f"  Created at: {source['created_at']}")
            if 'metadata_' in source and 'attached_agents' in source['metadata_']:
                logging.info("  Attached agents:")
                for agent in source['metadata_']['attached_agents']:
                    logging.info(f"    - {agent['name']} (ID: {agent['id']})")
            logging.info("---")
    else:
        logging.error("Failed to retrieve sources.")

if __name__ == "__main__":
    main()
