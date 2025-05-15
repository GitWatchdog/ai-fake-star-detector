import requests
import os
import datetime
import time
from dotenv import load_dotenv
import csv
import re # Import regex for sanitizing filenames
import argparse

# --- Constants and Setup ---
# Load environment variables from .env file if it exists
load_dotenv()

# GitHub Personal Access Token should be stored in your .env file as GITHUB_PAT=your_token_here
# Never hardcode tokens in your script files!

GITHUB_PAT = os.getenv("GITHUB_PAT")

if not GITHUB_PAT:
    print("Warning: GITHUB_PAT environment variable not set. API requests will be severely rate-limited.")
    HEADERS = {
        "Accept": "application/vnd.github.v3+json",
    }
else:
    HEADERS = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {GITHUB_PAT}",
    }

BASE_URL = "https://api.github.com"
REQUEST_DELAY = 0.5 # Seconds delay between API requests

# --- Filename Generation Helper ---
def sanitize_filename(name):
    """Removes potentially problematic characters for filenames."""
    name = re.sub(r'[<>:"/\\|?*]', '_', name) # Replace illegal chars with underscore
    return name

def generate_filenames(owner, repo):
    """Generates a dictionary of output filenames based on owner and repo with a timestamp."""
    sanitized_owner = sanitize_filename(owner)
    sanitized_repo = sanitize_filename(repo)
    
    # Add timestamp to avoid overwriting
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{sanitized_owner}_{sanitized_repo}_{timestamp}"
    
    return {
        "analysis_csv": f"{base_name}_stargazer_analysis.csv",
        "starred_list_csv": f"{base_name}_all_starred_repos_list.csv",
        "owned_list_csv": f"{base_name}_all_owned_repos_list.csv",
        "user_activity_csv": f"{base_name}_user_activity.csv",
        "report_md": f"{base_name}_analysis_report.md",
        "owned_repos_plot": f"{base_name}_common_owned_repos.png",
        "status_plot": f"{base_name}_account_status_distribution.png"
    }

# --- API Fetching Functions ---

def get_stargazers(owner, repo, limit=None):
    """Fetches stargazers for a given repository, handling pagination. Optionally limits the number fetched."""
    stargazers = []
    page = 1
    per_page = 100 # Max allowed by GitHub API
    fetched_count = 0
    
    while True:
        # Adjust per_page if limit is set and close to being reached
        current_per_page = per_page
        if limit is not None:
            remaining_needed = limit - fetched_count
            if remaining_needed <= 0:
                break
            if remaining_needed < per_page:
                current_per_page = remaining_needed
        
        url = f"{BASE_URL}/repos/{owner}/{repo}/stargazers?page={page}&per_page={current_per_page}"
        print(f"Fetching stargazers page {page} for {owner}/{repo} (requesting {current_per_page})...")
        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            # Check rate limit
            remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            print(f"Rate limit remaining: {remaining}")
            if remaining < 10: # Be cautious when approaching the limit
                print("Approaching rate limit, sleeping for 60 seconds...")
                time.sleep(60)

            data = response.json()
            if not data: # No more stargazers
                break
                
            stargazers.extend(data)
            fetched_count += len(data)
            
            # Check if limit reached
            if limit is not None and fetched_count >= limit:
                print(f"Reached fetch limit of {limit}.")
                stargazers = stargazers[:limit] # Trim excess if per_page fetched more
                break

            # Check for next page
            if 'next' not in response.links:
                break

            page += 1
            time.sleep(REQUEST_DELAY) # Small delay between requests

        except requests.exceptions.RequestException as e:
            print(f"Error fetching stargazers for {owner}/{repo}: {e}")
            if response is not None:
                print(f"Status Code: {response.status_code}")
                print(f"Response Body: {response.text}")
                # Specific handling for rate limit errors
                if response.status_code == 403 and ('rate limit exceeded' in response.text.lower() or 'secondary rate limit' in response.text.lower()):
                    reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 3600))
                    sleep_duration = max(reset_time - time.time(), 60) # Sleep until reset time or at least 60s
                    print(f"Rate limit hit. Sleeping for {sleep_duration:.0f} seconds.")
                    time.sleep(sleep_duration)
                    continue # Retry the current page
            break # Stop if other error occurs

    print(f"Fetched a total of {len(stargazers)} stargazers for {owner}/{repo}.")
    return stargazers

# --- Function to get user details ---
def get_user_details(username):
    """Fetches detailed information for a specific GitHub user."""
    url = f"{BASE_URL}/users/{username}"
    print(f"Fetching details for user: {username}...")
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        
        # Check rate limit
        remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
        print(f"Rate limit remaining: {remaining}")
        if remaining < 10:
            print("Approaching rate limit, sleeping for 60 seconds...")
            time.sleep(60)
            
        user_data = response.json()
        # Add a small delay after successful fetch
        time.sleep(REQUEST_DELAY)
        return user_data
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching details for user {username}: {e}")
        if response is not None:
            print(f"Status Code: {response.status_code}")
            print(f"Response Body: {response.text}")
            if response.status_code == 404:
                print(f"User {username} not found (might be deleted or renamed).")
            elif response.status_code == 403 and ('rate limit exceeded' in response.text.lower() or 'secondary rate limit' in response.text.lower()):
                 reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 3600))
                 sleep_duration = max(reset_time - time.time(), 60)
                 print(f"Rate limit hit. Sleeping for {sleep_duration:.0f} seconds.")
                 time.sleep(sleep_duration)
                 return get_user_details(username) # Retry after sleeping
        return None # Indicate failure

# --- Function to get user repos ---
def get_user_repos(username, limit=5):
    """Fetches a user's public repositories, sorted by last push, limited to 'limit'.
    
    Returns a list of tuples (name, description) for each repository.
    """
    repos = []
    page = 1
    per_page = min(limit, 100) # Request 'limit' repos, max 100 per page
    fetched_count = 0
    
    # Only fetch if limit > 0
    if limit <= 0:
        return []

    while fetched_count < limit:
        url = f"{BASE_URL}/users/{username}/repos?sort=pushed&direction=desc&page={page}&per_page={per_page}"
        print(f"Fetching repos for user {username} (page {page}, requesting {per_page})...")
        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()

            # Check rate limit
            remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            print(f"Rate limit remaining: {remaining}")
            if remaining < 10:
                print("Approaching rate limit, sleeping for 60 seconds...")
                time.sleep(60)

            data = response.json()
            if not data:
                break # No more repos

            repos.extend(data)
            fetched_count += len(data)
            
            # Check if we have enough or if there's no next page
            if fetched_count >= limit or 'next' not in response.links:
                break

            page += 1
            # Adjust per_page for the last request if needed
            remaining_needed = limit - fetched_count
            if remaining_needed < per_page:
                 per_page = remaining_needed
                 
            time.sleep(REQUEST_DELAY) # Small delay between requests

        except requests.exceptions.RequestException as e:
            print(f"Error fetching repos for user {username}: {e}")
            if response is not None:
                print(f"Status Code: {response.status_code}")
                print(f"Response Body: {response.text}")
                if response.status_code == 403 and ('rate limit exceeded' in response.text.lower() or 'secondary rate limit' in response.text.lower()):
                    reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 3600))
                    sleep_duration = max(reset_time - time.time(), 60)
                    print(f"Rate limit hit. Sleeping for {sleep_duration:.0f} seconds.")
                    time.sleep(sleep_duration)
                    continue # Retry the current page
            return None # Indicate error by returning None

    # Return a list of tuples with (name, description) for each repo up to the limit
    return [(repo['name'], repo.get('description', '') or '') for repo in repos[:limit]]

# --- Function to get starred repos ---
def get_starred_repos(username):
    """Fetches the first page (up to 100) of a user's starred repositories.
    
    Returns a list of tuples (full_name, description) for each repository.
    """
    starred_list_data = []
    # Fetch only the first page to get a sample
    url = f"{BASE_URL}/users/{username}/starred?page=1&per_page=100"
    print(f"Fetching starred repos for user {username} (first page)...")
    try:
        response = requests.get(url, headers=HEADERS)
        # 404 Not Found can sometimes happen for starred repos endpoint too, treat as error/empty
        if response.status_code == 404:
             print(f"Could not fetch starred repos for {username} (404 Not Found).")
             return None # Indicate error
        response.raise_for_status()

        # Check rate limit
        remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
        print(f"Rate limit remaining: {remaining}")
        if remaining < 10:
            print("Approaching rate limit, sleeping for 60 seconds...")
            time.sleep(60)

        starred_list_data = response.json()
            
        time.sleep(REQUEST_DELAY) # Small delay between requests

    except requests.exceptions.RequestException as e:
        print(f"Error fetching starred repos for user {username}: {e}")
        if response is not None:
            print(f"Status Code: {response.status_code}")
            print(f"Response Body: {response.text}")
            if response.status_code == 403 and ('rate limit exceeded' in response.text.lower() or 'secondary rate limit' in response.text.lower()):
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 3600))
                sleep_duration = max(reset_time - time.time(), 60)
                print(f"Rate limit hit. Sleeping for {sleep_duration:.0f} seconds.")
                time.sleep(sleep_duration)
                return get_starred_repos(username) # Retry after sleeping
        return None # Indicate error by returning None

    # Return a list of tuples with (full_name, description) for each repo
    return [(repo['full_name'], repo.get('description', '') or '') for repo in starred_list_data]

# --- Function to get starred repos count ---
def get_total_starred_count(username):
    """Gets the total count of repositories starred by a user.
    
    Args:
        username (str): GitHub username
        
    Returns:
        int, None, or "Private": 
            int: Count of starred repositories
            None: Error occurred during API request
            "Private": Unable to access starred repos (likely private account)
    """
    # First try to get the first page of starred repos to see if we can access them
    url = f"{BASE_URL}/users/{username}/starred?per_page=1"
    print(f"Checking starred repos count for user: {username}...")
    try:
        response = requests.get(url, headers=HEADERS)
        
        # If we get a 404, the user's stars are likely private
        if response.status_code == 404:
            print(f"Could not access starred repos for {username} (404 Not Found).")
            return "Private"
            
        response.raise_for_status()
        
        # Check rate limit
        remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
        print(f"Rate limit remaining: {remaining}")
        if remaining < 10:
            print("Approaching rate limit, sleeping for 60 seconds...")
            time.sleep(60)
        
        # Get total count from Link header if available (GitHub API pagination)
        if 'Link' in response.headers:
            links = response.headers['Link']
            # Try to extract the last page number from the Link header
            if 'rel="last"' in links:
                last_link = [link for link in links.split(',') if 'rel="last"' in link][0]
                page_num = last_link.split('&page=')[1].split('&')[0].split('>')[0]
                per_page = response.url.split('per_page=')[1].split('&')[0] if 'per_page=' in response.url else '30'
                try:
                    total_count = int(page_num) * int(per_page)  # Approximate count
                    return total_count
                except (ValueError, IndexError):
                    # If we can't parse the Link header reliably, fall back to user API
                    pass
        
        # If Link header approach failed, we'll ask the user API directly
        # which has a public_gists count (GitHub API may not provide direct starred count)
        user_url = f"{BASE_URL}/users/{username}"
        user_response = requests.get(user_url, headers=HEADERS)
        user_response.raise_for_status()
        user_data = user_response.json()
        
        # GitHub API doesn't provide a starred count directly in user data
        # We'll have to make a guess based on the first page
        # or we could potentially paginate through all starred repos to count them exactly
        
        # For now, we'll return the count from the first page as a minimum
        # and add a + to indicate there may be more
        first_page_count = len(response.json())
        if 'next' in response.links:
            return f"{first_page_count}+"
        else:
            return first_page_count
            
        time.sleep(REQUEST_DELAY)
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching starred count for user {username}: {e}")
        if response is not None:
            print(f"Status Code: {response.status_code}")
            print(f"Response Body: {response.text}")
            if response.status_code == 403 and ('rate limit exceeded' in response.text.lower() or 'secondary rate limit' in response.text.lower()):
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 3600))
                sleep_duration = max(reset_time - time.time(), 60)
                print(f"Rate limit hit. Sleeping for {sleep_duration:.0f} seconds.")
                time.sleep(sleep_duration)
                return get_total_starred_count(username)  # Retry after sleeping
        return None  # Indicate error

# --- Function to get user activity ---
def get_user_activity(username, max_pages=1):
    """Fetches a user's public activity (events) from GitHub.
    
    Args:
        username (str): GitHub username
        max_pages (int): Maximum number of pages to fetch (30 events per page)
        
    Returns:
        list or None: List of activity events or None if error or private
    """
    activities = []
    page = 1
    
    while page <= max_pages:
        url = f"{BASE_URL}/users/{username}/events/public?page={page}&per_page=30"
        print(f"Fetching activity for user {username} (page {page})...")
        try:
            response = requests.get(url, headers=HEADERS)
            
            # If we get a 404, the user's activity might be private
            if response.status_code == 404:
                print(f"Could not fetch activity for {username} (404 Not Found).")
                return None
                
            response.raise_for_status()
            
            # Check rate limit
            remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            print(f"Rate limit remaining: {remaining}")
            if remaining < 10:
                print("Approaching rate limit, sleeping for 60 seconds...")
                time.sleep(60)
            
            data = response.json()
            if not data:  # No more activities
                break
                
            activities.extend(data)
            
            # Check for next page
            if 'next' not in response.links or page >= max_pages:
                break
                
            page += 1
            time.sleep(REQUEST_DELAY)  # Small delay between requests
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching activity for user {username}: {e}")
            if response is not None:
                print(f"Status Code: {response.status_code}")
                if response.status_code == 403 and ('rate limit exceeded' in response.text.lower() or 'secondary rate limit' in response.text.lower()):
                    reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 3600))
                    sleep_duration = max(reset_time - time.time(), 60)
                    print(f"Rate limit hit. Sleeping for {sleep_duration:.0f} seconds.")
                    time.sleep(sleep_duration)
                    continue  # Retry the current page
            return None  # Indicate error by returning None
            
    # Process activity data to format it for CSV storage
    if activities:
        # Extract key information from each activity
        formatted_activities = []
        for activity in activities:
            event_type = activity.get('type', 'Unknown')
            created_at = activity.get('created_at', 'Unknown')
            repo_name = activity.get('repo', {}).get('name', 'Unknown')
            
            # Format activity entry
            formatted_activity = f"{created_at}: {event_type} on {repo_name}"
            formatted_activities.append(formatted_activity)
            
        return formatted_activities
    
    return []  # Return empty list if no activities found

# --- Main Data Fetching and Saving Function ---

def fetch_and_save_stargazer_data(repo_owner, repo_name, return_filenames=False, limit=None):
    """Fetches stargazer data for a repo and saves it to CSV files named after the repo.
    
    Args:
        repo_owner (str): GitHub repository owner/organization name
        repo_name (str): GitHub repository name
        return_filenames (bool): If True, returns the filename dict for use by analyze.py
        limit (int, optional): Maximum number of stargazers to fetch. If None, fetches all.
        
    Returns:
        dict or None: Dictionary of filenames if return_filenames is True, otherwise None
    """
    print(f"--- Starting data fetch for {repo_owner}/{repo_name} ---")

    filenames = generate_filenames(repo_owner, repo_name) # Generate filenames

    stargazers_to_analyze = get_stargazers(repo_owner, repo_name, limit=limit)

    analysis_results = []
    user_all_starred_map = {}
    user_owned_repos_map = {}
    user_activity_map = {}

    if not stargazers_to_analyze:
        print("No stargazers found or fetched.")
        return

    print(f"\nAnalyzing {len(stargazers_to_analyze)} stargazers...")
    for i, stargazer in enumerate(stargazers_to_analyze):
        login = stargazer['login']
        print(f"\nProcessing stargazer {i+1}/{len(stargazers_to_analyze)}: {login}")

        details = get_user_details(login)

        # Initialize default values for this user
        user_data = {
            'login': login, 'created_at': 'Error', 'public_repos': 'Error',
            'has_public_repos': 'Error', 'followers': 'Error', 'following': 'Error',
            'top_5_repos': 'Error', 'top_5_repos_descriptions': 'Error',
            'starred_repo_status': 'Error', 'starred_repos_sample': 'Error',
            'starred_repos_descriptions': 'Error', 'user_activity': 'Error'
        }

        if details:
            user_data.update({
                'created_at': details.get('created_at', 'N/A'),
                'public_repos': details.get('public_repos', 0),
                'followers': details.get('followers', 0),
                'following': details.get('following', 0),
            })
            user_data['has_public_repos'] = user_data['public_repos'] > 0 if isinstance(user_data['public_repos'], int) else 'Error'

            # Fetch Owned Repos
            if user_data['has_public_repos'] is True:
                top_5_repos_list = get_user_repos(login, limit=5)
                if top_5_repos_list is None:
                    user_data['top_5_repos'] = "Error fetching repos"
                    user_data['top_5_repos_descriptions'] = "Error fetching repos"
                else:
                    # Split the names and descriptions
                    repo_names = [name for name, _ in top_5_repos_list] if top_5_repos_list else []
                    repo_descriptions = [desc for _, desc in top_5_repos_list] if top_5_repos_list else []
                    
                    user_data['top_5_repos'] = ", ".join(repo_names) if repo_names else "None"
                    user_data['top_5_repos_descriptions'] = " | ".join(repo_descriptions) if repo_descriptions else "None"
                    user_owned_repos_map[login] = top_5_repos_list # Save for export
            else:
                 user_data['top_5_repos'] = "N/A (0 public repos)"
                 user_data['top_5_repos_descriptions'] = "N/A (0 public repos)"

            # Fetch Starred Repos
            starred_repos_list = get_starred_repos(login)
            # Get total starred count (adding this new call here)
            total_starred_count = get_total_starred_count(login)
            
            if starred_repos_list is not None:
                user_all_starred_map[login] = starred_repos_list # Save for export
                if len(starred_repos_list) == 0:
                    user_data['starred_repo_status'] = "Private (No Access to Starred Repo)"
                    user_data['starred_repos_sample'] = "None"
                    user_data['starred_repos_descriptions'] = "None"
                else:
                    user_data['starred_repo_status'] = "Public (Has Starred Repos)"
                    display_count = 10
                    sample_list = starred_repos_list[:display_count]
                    
                    # Split the names and descriptions
                    starred_names = [name for name, _ in sample_list]
                    starred_descriptions = [desc for _, desc in sample_list]
                    
                    user_data['starred_repos_sample'] = ", ".join(starred_names)
                    user_data['starred_repos_descriptions'] = " | ".join(starred_descriptions)
                    
                    if len(starred_repos_list) > display_count:
                        more_count = len(starred_repos_list) - display_count
                        user_data['starred_repos_sample'] += f", ... ({more_count} more)"
                # Add total starred count to user data
                user_data['total_starred_count'] = total_starred_count
            # Error status remains if starred_repos_list is None
            
            # Fetch User Activity (only if they have public repos or stars)
            is_public_user = (user_data['has_public_repos'] is True or 
                             (starred_repos_list is not None and len(starred_repos_list) > 0))
                             
            if is_public_user:
                user_activity = get_user_activity(login, max_pages=1)  # Fetch 1 page of activity (30 events)
                if user_activity is None:
                    user_data['user_activity'] = "Error fetching activity or private"
                elif not user_activity:
                    user_data['user_activity'] = "No recent activity"
                else:
                    user_data['user_activity'] = " || ".join(user_activity[:10])  # Store up to 10 most recent activities
                    if len(user_activity) > 10:
                        user_data['user_activity'] += f" || ... ({len(user_activity) - 10} more events)"
                    user_activity_map[login] = user_activity  # Store for separate file
            else:
                user_data['user_activity'] = "N/A (Private user)"

        analysis_results.append(user_data)

    # --- Export Main Analysis to CSV ---
    if analysis_results:
        output_file = filenames['analysis_csv'] # Use dynamic filename
        print(f"\nExporting main analysis results to {output_file}...")
        try:
            default_keys = ['login', 'created_at', 'public_repos', 'has_public_repos', 
                           'followers', 'following', 'top_5_repos', 'top_5_repos_descriptions',
                           'starred_repo_status', 'starred_repos_sample', 'starred_repos_descriptions',
                           'total_starred_count', 'user_activity']
            fieldnames = analysis_results[0].keys() if analysis_results else default_keys

            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(analysis_results)
            print("Main analysis export complete.")
        except Exception as e:
            print(f"Error writing main analysis CSV file ({output_file}): {e}")
    else:
        print("No analysis results to export.")

    # --- Export All Starred Repos to Separate CSV ---
    if user_all_starred_map:
        output_file = filenames['starred_list_csv'] # Use dynamic filename
        print(f"Exporting full starred repo list to {output_file}...")
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['user_login', 'starred_repos', 'starred_repos_descriptions']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for user_login, starred_list in user_all_starred_map.items():
                    # Split the names and descriptions
                    repo_names = [name for name, _ in starred_list] if starred_list else []
                    repo_descriptions = [desc for _, desc in starred_list] if starred_list else []
                    
                    writer.writerow({
                        'user_login': user_login,
                        'starred_repos': ", ".join(repo_names) if repo_names else "None",
                        'starred_repos_descriptions': " | ".join(repo_descriptions) if repo_descriptions else "None"
                    })
            print("Full starred repo export complete.")
        except IOError as e:
            print(f"Error writing starred repo CSV file ({output_file}): {e}")
    else:
        print("No starred repository data found to export to separate file.")

    # --- Export All Owned Repos (Top 5) to Separate CSV ---
    if user_owned_repos_map:
        output_file = filenames['owned_list_csv'] # Use dynamic filename
        print(f"Exporting owned repo list (top 5) to {output_file}...")
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['user_login', 'owned_repos', 'owned_repos_descriptions']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for user_login, owned_list in user_owned_repos_map.items():
                    # Split the names and descriptions
                    repo_names = [name for name, _ in owned_list] if owned_list else []
                    repo_descriptions = [desc for _, desc in owned_list] if owned_list else []
                    
                    writer.writerow({
                        'user_login': user_login,
                        'owned_repos': ", ".join(repo_names) if repo_names else "None",
                        'owned_repos_descriptions': " | ".join(repo_descriptions) if repo_descriptions else "None"
                    })
            print("Owned repo export complete.")
        except IOError as e:
            print(f"Error writing owned repo CSV file ({output_file}): {e}")
    else:
        print("No owned repository data found to export to separate file.")
    
    # --- Export User Activity to Separate CSV ---
    if user_activity_map:
        output_file = filenames['user_activity_csv']  # Use dynamic filename
        print(f"Exporting user activity to {output_file}...")
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['user_login', 'activity_events']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for user_login, activity_list in user_activity_map.items():
                    writer.writerow({
                        'user_login': user_login,
                        'activity_events': " || ".join(activity_list) if activity_list else "None"
                    })
            print("User activity export complete.")
        except IOError as e:
            print(f"Error writing user activity CSV file ({output_file}): {e}")
    else:
        print("No user activity data found to export to separate file.")

    print(f"\n--- Data fetch for {repo_owner}/{repo_name} finished. ---")
    
    # Return filenames if requested
    if return_filenames:
        return filenames
    return None

# Keep this block if you want to be able to run watchdog.py directly for testing
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch GitHub stargazer data for a given repository.")
    parser.add_argument("--owner", "-o", default="owner", help="Repository owner (default: owner)")
    parser.add_argument("--repo", "-r", default="repository", help="Repository name (default: repository)")
    parser.add_argument("--limit", "-l", type=int, help="Maximum number of stargazers to fetch (fetches all if not specified)")
    
    args = parser.parse_args()
    
    fetch_and_save_stargazer_data(args.owner, args.repo, limit=args.limit)
