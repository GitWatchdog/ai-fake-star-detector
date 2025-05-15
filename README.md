# GitHub Watch Dog: AI Fake Star Detector

A tool for analyzing GitHub repositories to detect potentially fake star activity and suspicious repository patterns.

## 🔍 Features

- **Stargazer Analysis**: Analyze stargazer accounts to identify potentially suspicious patterns
- **Repository Statistics**: Generate detailed reports on stargazer behavior and distribution
- **Account Type Analysis**: Differentiate between public and private accounts
- **Evidence Collection**: Generate timestamped reports and visualizations for future reference

## 📊 How It Works

The system follows a two-step approach:

1. **Data Collection (watchdog.py)**: 
   - Fetches stargazer data for a specified repository
   - Collects information about the repositories owned and starred by each stargazer
   - Gathers user activity data to identify behavioral patterns

2. **Analysis (analyze.py)**:
   - Processes collected data to identify suspicious patterns
   - Generates visual reports showing account distributions
   - Creates detailed Markdown reports summarizing findings

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- GitHub API access token

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/github-watch-dog.git
cd github-watch-dog

# Install dependencies
pip install requests pandas matplotlib seaborn python-dotenv

# Set up environment variables
# Create a .env file with your GitHub API token:
# GITHUB_PAT=your_github_personal_access_token
```

## 📝 Usage

Run the main script with a GitHub repository URL:

```bash
python main.py https://github.com/owner/repository
```

To limit the number of stargazers fetched (useful for testing):

```bash
python main.py https://github.com/owner/repository --limit 50
```

## 📈 Generated Reports

The tool will generate several files with a timestamp:

- `owner_repo_timestamp_stargazer_analysis.csv`: Raw data about each stargazer
- `owner_repo_timestamp_all_owned_repos_list.csv`: List of repositories owned by stargazers
- `owner_repo_timestamp_all_starred_repos_list.csv`: List of repositories starred by stargazers
- `owner_repo_timestamp_user_activity.csv`: User activity data
- `owner_repo_timestamp_analysis_report.md`: Detailed Markdown report
- `owner_repo_timestamp_common_owned_repos.png`: Visualization of common repositories
- `owner_repo_timestamp_account_status_distribution.png`: Account status distribution chart

## 🔒 Ethics & Usage

This tool is intended for legitimate security research and GitHub platform integrity analysis. Please:

- Respect GitHub's rate limits and API usage guidelines
- Use responsibly and for defensive purposes only
- Do not target legitimate repositories or users

## 📄 License

MIT

## 🤝 Contributing

Contributions to improve the analysis algorithms or add new detection features are welcome.