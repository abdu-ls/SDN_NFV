import requests
import csv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Target endpoint
url = "http://localhost:9091/get-address"
headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}

def send_request(request_id, lat, longi):
    """Send a single request and log the response time and status."""
    payload = {"lat": lat, "long": longi}
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
        lat,
        longi,
        response_time,
        status
    ]

def stress_test(total_requests, concurrent_users, lat, longi):
    start_time = time.time()
    results = []

    # Send concurrent requests
    with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
        futures = [executor.submit(send_request, i + 1, lat, longi) for i in range(total_requests)]
        for future in as_completed(futures):
            results.append(future.result())

    # Save results to CSV
    filename = f"stress_test_results_{int(time.time())}.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Request ID", "Timestamp", "Latitude", "Longitude", "Response Time (s)", "Status"])
        writer.writerows(results)

        # Summary statistics
        writer.writerow([])  # Empty row
        writer.writerow(["--- Summary Statistics ---"])
        response_times = [r[4] for r in results]
        success_count = sum(1 for r in results if "Success" in r[5])
        fail_count = total_requests - success_count
        avg_time = sum(response_times) / len(response_times)
        min_time = min(response_times)
        max_time = max(response_times)
        total_duration = time.time() - start_time
        requests_per_sec = round(total_requests / total_duration, 2)

        writer.writerow(["Total Requests", total_requests])
        writer.writerow(["Concurrent Users", concurrent_users])
        writer.writerow(["Successful Requests", success_count])
        writer.writerow(["Failed Requests", fail_count])
        writer.writerow(["Average Response Time (s)", round(avg_time, 4)])
        writer.writerow(["Fastest Response Time (s)", min_time])
        writer.writerow(["Slowest Response Time (s)", max_time])
        writer.writerow(["Total Duration (s)", round(total_duration, 2)])
        writer.writerow(["Requests Per Second (RPS)", requests_per_sec])
        writer.writerow(["Latency (s)", round(avg_time, 4)])  # Using avg_time as latency here

    # Print summary
    print("\n--- Load Test Summary ---")
    print(f"Total Users (Concurrent): {concurrent_users}")
    print(f"Total Requests: {total_requests}")
    print(f"Successful Requests: {success_count}")
    print(f"Failed Requests: {fail_count}")
    print(f"Average Response Time: {avg_time:.4f} s")
    print(f"Fastest Response Time: {min_time:.4f} s")
    print(f"Slowest Response Time: {max_time:.4f} s")
    print(f"Requests Per Second: {requests_per_sec}")
    print(f"Total Time Taken: {total_duration:.2f} seconds")
    print(f"Results saved to: {filename}")

if __name__ == "__main__":
    # Dynamic input
    total_requests = int(input("Enter total number of requests to send: "))
    concurrent_users = int(input("Enter number of concurrent users: "))
    lat = 6.6500
    longi = -1.647

    stress_test(total_requests, concurrent_users, lat, longi)
