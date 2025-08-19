import requests
import csv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Target endpoint
url = "http://localhost:9091/get-address"
headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}
payload = {
    "lat": "6.6500",
    "long": "-1.647"
}

def send_request(request_id):
    """Send a single request and log the response time and status."""
    start_time = time.time()
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=5)
        response_time = round(time.time() - start_time, 4)
        status = "Success" if response.status_code == 200 else f"Failed ({response.status_code})"
    except requests.RequestException as e:
        response_time = round(time.time() - start_time, 4)
        status = f"Error: {str(e)}"

    return [
        request_id,
        time.strftime("%Y-%m-%d %H:%M:%S"),
        payload["lat"],
        payload["long"],
        response_time,
        status
    ]

def stress_test(total_requests, concurrent_users):
    start_time = time.time()
    results = []

    # Send concurrent requests
    with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
        futures = [executor.submit(send_request, i + 1) for i in range(total_requests)]
        for future in as_completed(futures):
            results.append(future.result())

    # Save results to CSV
    filename = f"stress_test_results_{int(time.time())}.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Request ID", "Timestamp", "Latitude", "Longitude", "Response Time (s)", "Status"])
        writer.writerows(results)

    # Calculate summary statistics
    response_times = [r[4] for r in results]
    success_count = sum(1 for r in results if "Success" in r[5])
    fail_count = total_requests - success_count
    avg_time = sum(response_times) / len(response_times)
    min_time = min(response_times)
    max_time = max(response_times)

    # Print summary
    end_time = time.time()
    print("\n--- Load Test Summary ---")
    print(f"Total Users (Concurrent): {concurrent_users}")
    print(f"Total Requests: {total_requests}")
    print(f"Successful Requests: {success_count}")
    print(f"Failed Requests: {fail_count}")
    print(f"Average Response Time: {avg_time:.4f} s")
    print(f"Fastest Response Time: {min_time:.4f} s")
    print(f"Slowest Response Time: {max_time:.4f} s")
    print(f"Total Time Taken: {end_time - start_time:.2f} seconds")
    print(f"Results saved to: {filename}")

if __name__ == "__main__":
    # Dynamic input
    total_requests = int(input("Enter total number of requests to send: "))
    concurrent_users = int(input("Enter number of concurrent users: "))

    stress_test(total_requests, concurrent_users)
