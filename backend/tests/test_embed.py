import requests
import re

url = "https://www.youtube.com/embed/g34ZoiKJVG0"
print(f"Testing {url}")
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
response = requests.get(url, headers=headers)
print(f"Status: {response.status_code}")

if "This video isn't available anymore" in response.text:
    print("FOUND 'This video isn\\'t available anymore'")
elif "Video unavailable" in response.text:
    print("FOUND 'Video unavailable'")
else:
    print("Looks fine. Title:")
    m = re.search(r'<title>(.*?)</title>', response.text)
    if m:
        print(m.group(1))
