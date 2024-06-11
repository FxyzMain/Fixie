import requests

user_api_key = "sk-a770b8769f93ee4fcfe17d603705355b3cc85e942ddba747"
agent_id = "7da0a161-264d-4af3-882c-530a2ec64d63"

url = f"http://localhost:8283/api/agents/{agent_id}/archival/all"

headers = {
    "accept": "application/json",
    "authorization": f"Bearer {user_api_key}"
}

response = requests.get(url, headers=headers)

print(response.text)