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

def create_source(name):
    try:
        payload = {"name": name}
        response = requests.post(f"{base_url}/sources", headers=headers, json=payload)
        logging.info(f"Create source response: Status {response.status_code}, Content: {response.text}")
        
        if response.status_code == 200:
            return response.json().get('id')
        elif response.status_code == 500 and "already exists" in response.text:
            logging.info(f"Source {name} already exists, fetching its ID")
            return get_source_id_by_name(name)
        else:
            logging.error(f"Failed to create source {name}. Status code: {response.status_code}")
            return None
    except Exception as e:
        logging.exception(f"Exception occurred while creating source {name}: {str(e)}")
        return None

def get_source_id_by_name(name):
    sources = get_sources()
    if sources:
        for source in sources:
            if source['name'] == name:
                return source['id']
    return None

def main():
    sources = get_sources()
    if sources:
        logging.info("Available sources:")
        for source in sources:
            logging.info(f"- Name: {source['name']}, ID: {source['id']}")
    else:
        logging.error("Failed to retrieve sources.")

    source_names = ["fxyzMain", "OTC"]
    for name in source_names:
        source_id = get_source_id_by_name(name)
        if not source_id:
            source_id = create_source(name)
        logging.info(f"Source {name}: ID = {source_id}")

if __name__ == "__main__":
    main()
