import requests
import time

startTime = time.time()
response = requests.post(
    "https://715bf7eb9186.ngrok-free.app/api/generate",
    json={
        "model": "gpt-oss:20b",
        "prompt": "什麼是人工智能？",
        "stream": False
    }
)

print("status:", response.status_code)
print("text:", response.text)  # 印出真正的錯誤


# import requests
# import time

# startTime = time.time()
# response = requests.post(
#     "https://715bf7eb9186.ngrok-free.app/api/generate",
#     json={
#         "model": "gpt-oss:20b",
#         "prompt": "什麼是人工智能？",
#         "stream": False
#     }
# )
# print(time.time() - startTime)
# print(response.json()["response"])