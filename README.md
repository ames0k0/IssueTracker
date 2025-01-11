# Issue Tracker

Let the community report/create an issues on GitHub

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

### Versions
- **0.0.2**
  - [ ] Code/Database documentations
  - [ ] Handle missclick
  - [ ] Detailed report/issue
- **0.0.1**
  - [x] `/start` - Register `Telegram Channel Discussion` to a GitHub repository/project
  - [x] `/report` - Repost an issue by creating the GitHub issue to the repository/project

---
[Project Diagram and Screenshots](./docs/readme/DAS.md)
