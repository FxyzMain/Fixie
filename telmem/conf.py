import requests

url = "http://localhost:8283/api/humans"

headers = {
    "accept": "application/json",
    "authorization": "Bearer ilovellms"
}

response = requests.get(url, headers=headers)

print(response.text)