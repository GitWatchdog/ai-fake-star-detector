# main.py

import watchdog
import analyze
import argparse
import sys

def run_analysis(owner, repo, limit=None):
    """Runs the full stargazer fetching and analysis process.
    
    Args:
        owner (str): GitHub repository owner
        repo (str): GitHub repository name
        limit (int, optional): Maximum number of stargazers to fetch. If None, fetches all.
    """
    print(f"Starting analysis for repository: {owner}/{repo}")
    if limit:
        print(f"Sampling mode: Will fetch up to {limit} stargazers")

    # Step 1: Fetch and save data, get the filenames
    try:
        # Note: We need to grab the actual timestamp-based filenames
        filenames = None
        result = watchdog.fetch_and_save_stargazer_data(owner, repo, return_filenames=True, limit=limit)
        if isinstance(result, dict):
            filenames = result
        
        if not filenames:
            print("Error: Could not get filenames from data fetch. Analysis cannot proceed.")
            return
            
    except Exception as e:
        print(f"Error during data fetching: {e}", file=sys.stderr)
        print("Analysis cannot proceed.")
        return # Stop if fetching fails

    # Step 2: Analyze data and generate report using the same filenames
    try:
        # Pass the filenames from the fetch step to ensure we're using the same timestamp
        analyze.analyze_data(owner, repo, filenames=filenames)
    except Exception as e:
        print(f"Error during analysis report generation: {e}", file=sys.stderr)

    print(f"\nProcess finished for {owner}/{repo}.")

if __name__ == "__main__":
    # --- Configuration ---
    # Option 1: Hardcode the repository (Comment out if using argparse)
    # TARGET_OWNER = "cafferychen777"
    # TARGET_REPO = "mLLMCelltype"
    # run_analysis(TARGET_OWNER, TARGET_REPO)

    # Option 2: Use command-line arguments (Recommended)
    parser = argparse.ArgumentParser(description="Fetch and analyze GitHub stargazer data for a given repository.")
    parser.add_argument("repo_url", help="Full URL of the GitHub repository (e.g., https://github.com/owner/repo)")
    parser.add_argument("--limit", "-l", type=int, help="Maximum number of stargazers to fetch. If not specified, fetches all stargazers.")
    # Example parsing: python main.py https://github.com/cafferychen777/mLLMCelltype --limit 50

    args = parser.parse_args()

    # Basic parsing of owner/repo from URL
    try:
        # Improve URL parsing to handle various formats
        parts = args.repo_url.strip('/').split('/')
        if len(parts) >= 2 and "github.com" in args.repo_url.lower(): 
             # Find github.com index
             try:
                 gh_index = parts.index("github.com")
                 if len(parts) > gh_index + 2:
                     target_owner = parts[gh_index + 1]
                     target_repo = parts[gh_index + 2]
                     # Remove potential .git suffix
                     if target_repo.endswith(".git"): 
                         target_repo = target_repo[:-4]
                     print(f"Parsed Owner: {target_owner}, Repo: {target_repo}")
                     run_analysis(target_owner, target_repo, limit=args.limit)
                 else:
                     raise ValueError("Could not extract owner/repo after github.com")
             except ValueError:
                 print("Error: Could not find 'github.com' or owner/repo part in the URL.", file=sys.stderr)
                 sys.exit(1)

        else:
             print("Error: Invalid GitHub repository URL format. Please use https://github.com/owner/repo", file=sys.stderr)
             sys.exit(1)
    except Exception as e:
        print(f"Error parsing repository URL '{args.repo_url}': {e}", file=sys.stderr)
        sys.exit(1)
