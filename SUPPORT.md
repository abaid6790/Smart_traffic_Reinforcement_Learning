# Getting help

1. **Read the guides.** [docs/USER_GUIDE.md](docs/USER_GUIDE.md) answers most "how do I ..." questions and has a
   troubleshooting table.
2. **Check the basics.**
   * `python main.py --version` and `python --version` (Python 3.11 or newer is needed).
   * `pip install -r requirements.txt` in your virtual environment.
   * `python -m unittest discover -s tests -t .` should end with `OK`.
3. **Look at the log.** Technical details are in `logs/application.log`. (It can contain file paths; see
   [PRIVACY.md](PRIVACY.md) before sharing it.)
4. **Ask.** Open an issue with the bug report template in `.github/ISSUE_TEMPLATE`, or contact _your supervisor / your
   contact (replace this placeholder)_.

Please include: what you did, what you expected, what happened, your operating system, and the output of
`python main.py --version`.

Security problems: [SECURITY.md](SECURITY.md). Questions about the ideas behind the project:
[docs/RL_EXPLAINED.md](docs/RL_EXPLAINED.md) and [docs/VIVA_QUESTIONS.md](docs/VIVA_QUESTIONS.md).

This is a student project without a support service; answers come when someone has time.
