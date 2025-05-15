import pandas as pd
from collections import Counter
import os
import matplotlib.pyplot as plt
import seaborn as sns
import re # Import regex for sanitizing filenames
import datetime
import numpy as np

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
        "owned_list_csv": f"{base_name}_all_owned_repos_list.csv",
        "report_md": f"{base_name}_analysis_report.md",
        "owned_repos_plot": f"{base_name}_common_owned_repos.png",
        "status_plot": f"{base_name}_account_status_distribution.png"
        # Note: We don't need starred_list_csv here, only owned_list_csv for analysis
    }

# --- Plotting Functions ---
def generate_repo_plot(repo_counts, output_filename, top_n=10, title=None):
    """Generates and saves a bar plot of the most common repositories.
    
    Args:
        repo_counts: Counter object with repository counts
        output_filename: Path to save the plot
        top_n: Number of top repositories to include
        title: Custom title for the plot (defaults to 'Top X Most Common Owned Repositories')
    """
    if not repo_counts:
        print("No repository data to plot.")
        return False

    # Get the top N most common items
    common_repos = repo_counts.most_common(top_n)
    repos, counts = zip(*common_repos)
    
    # Default title if none provided
    if title is None:
        title = f'Top {len(repos)} Most Common Owned Repositories'

    try:
        plt.figure(figsize=(10, max(6, top_n * 0.5))) # Adjust height based on N
        sns.barplot(x=list(counts), y=list(repos), palette="viridis", orient='h')
        plt.title(title)
        plt.xlabel('Number of Occurrences')
        plt.ylabel('Repository Name')
        plt.tight_layout()
        plt.savefig(output_filename) # Use passed filename
        plt.close()
        print(f"Generated plot: {output_filename}")
        return True
    except Exception as e:
        print(f"Error generating plot: {e}")
        return False

def generate_status_pie_chart(status_counts, output_filename, title='Account Status Distribution'):
    """Generates and saves a pie chart of account status distribution.
    
    Args:
        status_counts: Dictionary mapping status labels to counts
        output_filename: Path to save the plot
        title: Custom title for the plot
    """
    labels = status_counts.keys()
    sizes = status_counts.values()
    
    # Ensure we only plot if there's data
    if not any(sizes):
        print("No status data to plot.")
        return False
        
    # Define colors for different statuses
    color_map = {
        'Private (No Access)': '#ff9999',  # Light red
        'Public (Has Stars)': '#66b3ff',   # Light blue
        'Error/Unknown': '#c2c2c2'         # Light gray
    }
    
    # Get colors for each label, with fallback to default color palette
    colors = [color_map.get(label, '#%02x%02x%02x' % tuple(np.random.randint(0, 200, 3))) for label in labels]

    try:
        fig, ax = plt.subplots(figsize=(8, 8))
        wedges, texts, autotexts = ax.pie(
            sizes, 
            labels=labels, 
            autopct='%1.1f%%', 
            startangle=90, 
            colors=colors,
            shadow=True,
            wedgeprops={'edgecolor': 'white', 'linewidth': 1}
        )
        
        # Make the percentage text inside the pie chart more readable
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            
        ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
        plt.title(title, fontsize=15, fontweight='bold')
        plt.tight_layout()
        plt.savefig(output_filename, dpi=300)
        plt.close()
        print(f"Generated status plot: {output_filename}")
        return True
    except Exception as e:
        print(f"Error generating status pie chart: {e}")
        return False

# --- Main Analysis Function ---
def analyze_data(repo_owner, repo_name, filenames=None):
    """Reads generated CSVs and produces a Markdown analysis report named after the repo.
    
    Args:
        repo_owner (str): GitHub repository owner/organization name
        repo_name (str): GitHub repository name
        filenames (dict, optional): Dictionary of filenames from watchdog, to ensure timestamp matches
        
    Returns:
        bool: True if analysis completed successfully, False otherwise
    """
    report_title = f"Stargazer Analysis Report for {repo_owner}/{repo_name}"
    
    # Generate filenames only if not provided
    if filenames is None:
        filenames = generate_filenames(repo_owner, repo_name)

    # Define input/output files for this run
    analysis_csv_file = filenames['analysis_csv']
    owned_repos_csv_file = filenames['owned_list_csv']
    report_md_file = filenames['report_md']
    owned_repos_plot_file = filenames['owned_repos_plot']
    status_plot_file = filenames['status_plot']
    
    # Define additional plot filenames for segregated analysis
    private_repos_plot_file = owned_repos_plot_file.replace('_common_owned_repos.png', '_private_users_repos.png')
    public_repos_plot_file = owned_repos_plot_file.replace('_common_owned_repos.png', '_public_users_repos.png')
    
    print(f"--- Generating analysis report: {report_md_file} ---")
    report_content = []
    num_to_show_common_repos = 10

    # Check if required input files exist
    if not os.path.exists(analysis_csv_file):
        print(f"Error: Analysis file not found: {analysis_csv_file}")
        print("Please run the data fetching script first.")
        return False
    if not os.path.exists(owned_repos_csv_file):
        print(f"Error: Owned repos file not found: {owned_repos_csv_file}")
        print("Please run the data fetching script first.")
        return False

    try:
        # --- Analyze Main Stargazer Data ---
        df_analysis = pd.read_csv(analysis_csv_file)
        total_users = len(df_analysis)
        report_content.append(f"# {report_title}\n")
        report_content.append(f"Total stargazers analyzed: {total_users}\n")

        if total_users == 0:
            print("No user data to analyze.")
            report_content.append("No user data found in CSV.")
            # Write incomplete report and exit
            with open(report_md_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(report_content))
            return False

        # Calculate percentage of private users
        # Handle potential 'Error' values in the status column gracefully
        private_users = df_analysis[df_analysis['starred_repo_status'] == 'Private (No Access to Starred Repo)']
        private_count = len(private_users)
        public_users = df_analysis[df_analysis['starred_repo_status'] == 'Public (Has Starred Repos)']
        public_count = len(public_users)
        error_count = total_users - private_count - public_count  # Users with Error status

        # Calculate percentage for private and public users
        private_percentage = (private_count / total_users) * 100
        public_percentage = (public_count / total_users) * 100
        error_percentage = (error_count / total_users) * 100 if error_count > 0 else 0

        report_content.append(f"## Account Status Distribution\n")
        report_content.append(f"Users considered 'private' (no access to starred repos): {private_count} ({private_percentage:.2f}%)")
        report_content.append(f"Users considered 'public' (has starred repos): {public_count} ({public_percentage:.2f}%)")
        if error_count > 0:
            report_content.append(f"Users with error status: {error_count} ({error_percentage:.2f}%)")
        report_content.append("\n")

        # --- Generate Status Distribution Plot ---
        status_counts = {
            'Private (No Access)': private_count,
            'Public (Has Stars)': public_count
        }
        if error_count > 0:
            status_counts['Error/Unknown'] = error_count
            
        status_plot_generated = generate_status_pie_chart(status_counts, status_plot_file)
        if status_plot_generated:
            report_content.append(f"![Account Status Distribution]({os.path.basename(status_plot_file)})\n")
        else:
            report_content.append("(Status plot generation failed or no data)\n")

        # --- Load owned repos data ---
        df_owned = pd.read_csv(owned_repos_csv_file)
        
        # --- Create lists of user logins by type ---
        private_logins = set(private_users['login'])
        public_logins = set(public_users['login'])
        
        # --- Filter owned repos data by user type ---
        df_private_owned = df_owned[df_owned['user_login'].isin(private_logins)]
        df_public_owned = df_owned[df_owned['user_login'].isin(public_logins)]
        
        # --- Analyze All Owned Repos (All Users) ---
        all_owned_repos = []
        for repo_str in df_owned['owned_repos'].dropna():
            if repo_str and isinstance(repo_str, str) and repo_str.lower() != 'none':
                try:
                    repos = [repo.strip() for repo in repo_str.split(',')]
                    all_owned_repos.extend(repos)
                except Exception as split_error:
                    print(f"Warning: Could not parse repo string '{repo_str}': {split_error}")

        # --- Analyze Owned Repos (Private Users) ---
        private_owned_repos = []
        for repo_str in df_private_owned['owned_repos'].dropna():
            if repo_str and isinstance(repo_str, str) and repo_str.lower() != 'none':
                try:
                    repos = [repo.strip() for repo in repo_str.split(',')]
                    private_owned_repos.extend(repos)
                except Exception as split_error:
                    print(f"Warning: Could not parse repo string '{repo_str}': {split_error}")

        # --- Analyze Owned Repos (Public Users) ---
        public_owned_repos = []
        for repo_str in df_public_owned['owned_repos'].dropna():
            if repo_str and isinstance(repo_str, str) and repo_str.lower() != 'none':
                try:
                    repos = [repo.strip() for repo in repo_str.split(',')]
                    public_owned_repos.extend(repos)
                except Exception as split_error:
                    print(f"Warning: Could not parse repo string '{repo_str}': {split_error}")
                    
        # --- Generate Report Sections ---
        
        # ALL USERS SECTION
        report_content.append("## Common Owned Repositories (All Users)\n")
        if not all_owned_repos:
            report_content.append("No owned repositories found in the data.\n")
            all_repo_plot_generated = False
        else:
            repo_counts = Counter(all_owned_repos)
            num_to_show = min(num_to_show_common_repos, len(repo_counts))
            
            report_content.append("Occurrences:")
            for repo, count in repo_counts.most_common(num_to_show):
                percentage = (count / len(all_owned_repos)) * 100
                report_content.append(f"  - `{repo}`: {count} ({percentage:.2f}%)")
            report_content.append("\n")
            
            # Generate plot for all users
            all_repo_plot_generated = generate_repo_plot(repo_counts, owned_repos_plot_file, top_n=num_to_show)

        if all_repo_plot_generated:
            report_content.append(f"![Top {num_to_show} Common Owned Repos (All Users)]({os.path.basename(owned_repos_plot_file)})\n")
        else:
            report_content.append("(Owned repo plot generation failed or no data to plot)\n")
            
        # PUBLIC USERS SECTION
        report_content.append("## Common Owned Repositories (Public Users Only)\n")
        if not public_owned_repos:
            report_content.append("No owned repositories found for public users.\n")
            public_repo_plot_generated = False
        else:
            public_repo_counts = Counter(public_owned_repos)
            num_to_show_public = min(num_to_show_common_repos, len(public_repo_counts))
            
            report_content.append("Occurrences:")
            for repo, count in public_repo_counts.most_common(num_to_show_public):
                percentage = (count / len(public_owned_repos)) * 100
                report_content.append(f"  - `{repo}`: {count} ({percentage:.2f}%)")
            report_content.append("\n")
            
            # Generate plot for public users
            public_repo_plot_generated = generate_repo_plot(
                public_repo_counts, 
                public_repos_plot_file, 
                top_n=num_to_show_public,
                title="Top Common Owned Repositories (Public Users Only)"
            )

        if public_repo_plot_generated:
            report_content.append(f"![Top {num_to_show_public} Common Owned Repos (Public Users)]({os.path.basename(public_repos_plot_file)})\n")
        else:
            report_content.append("(Public users repo plot generation failed or no data to plot)\n")
            
        # PRIVATE USERS SECTION
        report_content.append("## Common Owned Repositories (Private Users Only)\n")
        if not private_owned_repos:
            report_content.append("No owned repositories found for private users.\n")
            private_repo_plot_generated = False
        else:
            private_repo_counts = Counter(private_owned_repos)
            num_to_show_private = min(num_to_show_common_repos, len(private_repo_counts))
            
            report_content.append("Occurrences:")
            for repo, count in private_repo_counts.most_common(num_to_show_private):
                percentage = (count / len(private_owned_repos)) * 100
                report_content.append(f"  - `{repo}`: {count} ({percentage:.2f}%)")
            report_content.append("\n")
            
            # Generate plot for private users
            private_repo_plot_generated = generate_repo_plot(
                private_repo_counts, 
                private_repos_plot_file, 
                top_n=num_to_show_private,
                title="Top Common Owned Repositories (Private Users Only)"
            )

        if private_repo_plot_generated:
            report_content.append(f"![Top {num_to_show_private} Common Owned Repos (Private Users)]({os.path.basename(private_repos_plot_file)})\n")
        else:
            report_content.append("(Private users repo plot generation failed or no data to plot)\n")

    except FileNotFoundError:
         print(f"Error: One or both CSV files not found.")
         return False
    except pd.errors.EmptyDataError:
        print("Error: One of the CSV files is empty.")
        report_content.append("\n*Analysis incomplete: Input CSV file was empty.*\n")
    except KeyError as e:
        print(f"Error: Expected column missing in CSV file: {e}. Did the data fetch script run correctly?")
        report_content.append(f"\n*Analysis incomplete due to missing column: {e}*\n")
    except Exception as e:
        print(f"An unexpected error occurred during analysis: {e}")
        report_content.append(f"\n*Analysis incomplete due to error: {e}*\n")

    # --- Write Report ---
    try:
        with open(report_md_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(report_content))
        print(f"Successfully generated analysis report: {report_md_file}")
        return True
    except IOError as e:
        print(f"Error writing report file {report_md_file}: {e}")
        return False

# Keep this block if you want to be able to run analyze.py directly on default named files
if __name__ == "__main__":
    print("Running analyze.py directly.")
    print("WARNING: This assumes CSV files like 'stargazer_analysis.csv' exist.")
    print("         Run main.py to generate repo-specific files and reports.")
    # Attempt analysis assuming default filenames, owner/repo unknown for title
    analyze_data("unknown_owner", "unknown_repo")
