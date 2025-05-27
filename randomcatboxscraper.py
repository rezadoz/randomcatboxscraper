import os
import argparse
import random
import string
import requests
import sys
import time
import concurrent.futures
import threading
from colorama import init, Fore, Style

init(autoreset=True)

#------------------
#-----Settings-----
#------------------

workers = 20  # number of concurrent searches
FIREFOX_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
HEADERS = {'User-Agent': FIREFOX_USER_AGENT}
log_lock = threading.Lock()
shutdown_event = threading.Event()

sys.stdout.flush()

parser = argparse.ArgumentParser(description='catbox.moe downloader')
parser.add_argument('-v', '--verbose', action='store_true', help='adds verbose output')
parser.add_argument('-f', '--file', help='the file type you want to search for i.e. png jpeg mp4')
parser.add_argument('-l', '--list', action='store_true', help='lists all previously found URLs from log.txt')
parser.add_argument('-c', '--count', action='store_true', help='list the amount checked per second')
parser.add_argument('-d', '--download', action='store_true', help='download as it finds it')

args = parser.parse_args()

verbose = args.verbose
file_extension = args.file or 'png'
list_mode = args.list
count = args.count
download = args.download

if list_mode:
    with open('log.txt', 'r') as file:
        for line in file:
            if 'found' in line:
                print(line.strip())
    sys.exit()

print('searching for:', file_extension)
folder_path = file_extension

if download and not os.path.exists(folder_path):
    os.makedirs(folder_path)

def download_image(url, file_path):
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            with open(file_path, 'wb') as file:
                file.write(response.content)
            print("✅ file downloaded successfully!")
        else:
            print(Fore.RED + f"(!) failed to download image: {url}")
    except Exception as e:
        print(Fore.RED + f"Download error: {e}")

def count_calls_per_second(func):
    count = 0
    start_time = time.time()

    def wrapper(*args, **kwargs):
        nonlocal count
        count += 1
        return func(*args, **kwargs)

    def display_calls_per_second():
        nonlocal count, start_time
        elapsed_time = time.time() - start_time
        if elapsed_time > 0:
            calls_per_second = count / elapsed_time
            print("requests/sec:", calls_per_second, end="\r")

    wrapper.display_calls_per_second = display_calls_per_second
    return wrapper

@count_calls_per_second
def track_request():
    pass

def generate_catbox_url():
    random_link = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f'https://files.catbox.moe/{random_link}.{file_extension}'

def check_url():
    if shutdown_event.is_set():
        return
    try:
        url = generate_catbox_url()
        response = requests.get(url, headers=HEADERS, timeout=10)

        if response.status_code == 200:
            print(Fore.GREEN + 'bingo! valid:', url)
            with log_lock:
                with open('log.txt', 'a') as f:
                    f.write('Valid URL found: ' + url + '\n')
            if download:
                file_path = os.path.join(folder_path, os.path.basename(url))
                download_image(url, file_path)
        else:
            if verbose:
                print('Invalid URL:', url)
            with log_lock:
                with open('log.txt', 'a') as f:
                    f.write('Invalid URL: ' + url + '\n')

        track_request()
        if count:
            track_request.display_calls_per_second()

    except requests.exceptions.RequestException as e:
        if verbose:
            print(Fore.YELLOW + f'connection error: {e}')

def main():
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            while not shutdown_event.is_set():
                executor.submit(check_url)
                time.sleep(0.005)
    except KeyboardInterrupt:
        print(Fore.CYAN + '\n[!] KeyboardInterrupt received, exiting gracefully.')
        shutdown_event.set()
    finally:
        executor.shutdown(wait=True)
        sys.exit(0)

if __name__ == '__main__':
    main()
