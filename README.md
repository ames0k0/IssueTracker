# Issue Tracker

Let the community report/create an issues on GitHub

> [!NOTE]
> Run commands in the Telegram Channel Discussion\
> Brief: [Project Diagram and Screenshots](./docs/readme/DAS.md)

```
/start  - Link GitHub repository with Telegram Channel
/report - Create an issue on GitHub
```

---
<details>
<summary>Dependencies</summary>
<pre>
python3 -V        # Python 3.11.6
sqlite3 -version  # 3.42.0 2023-05-16 12:36:15 831d0f...
</pre>
</details>

```bash
# Set an Environment variables: $TG__TOKEN, $GH__TOKEN
cp ./deploy/secrets/.env-local-EXAMPLE ./deploy/secrets/.env-local

# Virtual Environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the program
python3 main.py
```

#### Versions
- **~~0.0.2~~**
  - [ ] Code/Database documentations
  - [ ] Handle missclick
  - [ ] Detailed report/issue
- **0.0.5**
  - [x] Remove registered project update https://github.com/ames0k0/IssueTracker/issues/18
  - [x] Update tables, Remove custom urls https://github.com/ames0k0/IssueTracker/issues/19 
- **0.0.1**
  - [x] `/start` - Link GitHub repository with Telegram Channel
  - [x] `/report` - Create an issue on GitHub
