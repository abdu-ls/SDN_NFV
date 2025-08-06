import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Target endpoint and data
url = "http://localhost:9091/get-address"
headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}
payload = {
    "lat": "6.6500",
    "long": "-1.647"
}

# Number of requests and concurrency level
total_requests = 1000  # total number of requests to send
max_workers = 50       # number of concurrent threads

def send_request():
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=5)
        return response.status_code
    except requests.RequestException as e:
        return f"Error: {e}"

def stress_test():
    start_time = time.time()
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(send_request) for _ in range(total_requests)]

        for future in as_completed(futures):
            results.append(future.result())

    end_time = time.time()

    # Summary
    print(f"Total requests sent: {total_requests}")
    print(f"Successful requests: {sum(1 for r in results if r == 200)}")
    print(f"Failed requests: {sum(1 for r in results if r != 200)}")
    print(f"Time taken: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    stress_test()
