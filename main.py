import os
import sys
import sqlite3
import logging
import asyncio
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from github import Github, Auth

from dotenv import load_dotenv


class Form(StatesGroup):
  project_id = State()
  admin_message_id = State()
  bot_message_id = State()
  project_gh_url = State()


class SupportedCodeHubs(Enum):
  github = 'github.com'


dp = Dispatcher()


@dp.message(Form.project_gh_url)
async def handle_github_url(
  message: Message, state: FSMContext
) -> None:
  if not message.from_user.is_bot:
    return
  state_data = await state.get_data()
  if message.reply_to_message.message_id != state_data["bot_message_id"]:
    return
  url = message.text.strip()
  parsed_url = urlparse(url)
  if parsed_url.netloc != SupportedCodeHubs.github.value:
    fail_msg = await message.reply(
      f"[?] Not supported: {parsed_url.netloc or url}! Try again..."
    )
    await asyncio.sleep(1.5)
    await fail_msg.delete()
    await message.delete()
    return

  project_id = state_data["project_id"]
  project_name = "/".join(
    tuple(filter(bool, parsed_url.path.split("/", maxsplit=3)))[:2]
  )

  curr.execute(
    """
    UPDATE
      projects
    SET
      gh_project_url = ?,
      gh_project_name = ?
    WHERE
      id = ?
    """,
    (
      url,
      project_name,
      project_id,
    )
  )
  conn.commit()

  last_msg = await message.reply(f"[!] Created a Project(id={project_id})")
  await asyncio.sleep(1.5)
  await last_msg.delete()
  await message.delete()
  await bot.delete_message(message.chat.id, state_data["bot_message_id"])
  await bot.delete_message(message.chat.id, state_data["admin_message_id"])
  await state.clear()


@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
  if not message.from_user.is_bot:
    return

  await state.set_state(Form.project_gh_url)

  curr.execute(
    """
    SELECT id FROM projects WHERE tg_mrtm_sender_chat_id = ?
    """,
    (message.reply_to_message.sender_chat.id,)
  )
  project = curr.fetchone()
  if not project:
    curr.execute(
      """
      INSERT INTO
        projects (
          tg_mrtm_message_id,
          tg_mrtm_date,
          tg_mrtm_sender_chat_id,
          tg_mrtm_sender_chat_title
        )
      VALUES (
        ?, ?, ?, ?
      )
      """,
      (
        message.reply_to_message.message_id,
        message.reply_to_message.date.strftime(MESSAGE_DT_FORMAT),
        message.reply_to_message.sender_chat.id,
        message.reply_to_message.sender_chat.title,
      )
    )
    project_id = curr.lastrowid
  else:
    project_id = project[0]
    curr.execute(
      """
      UPDATE
        projects
      SET
        tg_mrtm_message_id = ?,
        tg_mrtm_date = ?,
        tg_mrtm_sender_chat_id = ?,
        tg_mrtm_sender_chat_title = ?
      WHERE
        id = ?
      """,
      (
        message.reply_to_message.message_id,
        message.reply_to_message.date.strftime(MESSAGE_DT_FORMAT),
        message.reply_to_message.sender_chat.id,
        message.reply_to_message.sender_chat.title,
        project_id,
      )
    )
  conn.commit()

  await state.update_data(project_id=project_id)
  await state.update_data(admin_message_id=message.message_id)

  message = await message.reply("Reply GitHub/Project URL")

  await state.update_data(bot_message_id=message.message_id)


@dp.message(Command("report"))
async def report_handler(message: Message) -> None:
  # NOTE
  # - Single issue per `tg_mrtm_message_id`

  # XXX: next version
  # - set the MAX issue "REAL" (not report) for the `tg_mrtm_message_id`
  curr.execute(
    """
    SELECT id, gh_project_name FROM projects WHERE tg_mrtm_sender_chat_id = ?
    """,
    (message.reply_to_message.sender_chat.id,)
  )
  project = curr.fetchone()
  if project is None:
    await message.reply(
      "[?] Project is not registered for the chat: "
      f"{html.bold(message.reply_to_message.sender_chat.title)}\n"
      "[!] Bot/Admin only /start"
    )
    return

  project_id, gh_project_name = project
  tg_mrtm_message_id = message.reply_to_message.message_id
  tg_mrtm_user_id = message.from_user.id
  tg_mrtm_user_is_bot = message.from_user.is_bot
  tg_message_id = message.message_id
  tg_message_date = message.date.strftime(MESSAGE_DT_FORMAT)
  tg_message_chat_title = message.chat.title

  curr.execute(
    """
    SELECT
      gh_issue_html_url
    FROM
      project_issues
    WHERE
      project_id = ?
    AND
      tg_mrtm_message_id = ?
    """,
    (
      project_id,
      tg_mrtm_message_id,
    )
  )
  project_issue = curr.fetchone()
  if project_issue:
    await message.reply(
      f"[!] An Issue already has been created at: {project_issue[0]}",
    )
    return

  tg_chat_url = f"https://t.me/{message.reply_to_message.sender_chat.username}"
  tg_message_url = f"{tg_chat_url}/{tg_mrtm_message_id}"
  tg_mrtm_message_url = f"{tg_message_url}?comment={tg_message_id}"

  repository = github.get_repo(gh_project_name)
  issue = repository.create_issue(
    title=f"{tg_message_chat_title}/{tg_message_id}",
    body=f"[{tg_message_date}] - [{tg_mrtm_user_is_bot}] - [{tg_mrtm_user_id}]\n"
         "//\n"
         f"[ChatPostURL]({tg_message_url}) - [ChatPostCommentURL]({tg_mrtm_message_url})"
  )

  curr.execute(
    """
    INSERT INTO
      project_issues (
        project_id,
        tg_mrtm_message_id,
        tg_mrtm_message_url,
        tg_mrtm_user_id,
        tg_mrtm_user_is_bot,
        tg_message_id,
        tg_message_url,
        tg_message_date,
        gh_issue_id,
        gh_issue_html_url,
        gh_issue_created_at
      )
    VALUES
      (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
      project_id,
      tg_mrtm_message_id,
      tg_mrtm_message_url,
      tg_mrtm_user_id,
      tg_mrtm_user_is_bot,
      tg_message_id,
      tg_message_url,
      tg_message_date,
      issue.id,
      issue.html_url,
      issue.created_at.strftime(MESSAGE_DT_FORMAT),
    )
  )
  conn.commit()

  await message.reply(f"[!] Created an Issue at: {issue.html_url}")


if __name__ == "__main__":
  MESSAGE_DT_FORMAT = "%Y-%m-%d %H:%M:%S"

  STATIC_DIR = Path("./static")
  STATIC_DIR.mkdir(exist_ok=True)

  DB_FILE = STATIC_DIR / "db.sqlite3"

  if not os.environ.get("BOT__TOKEN"):
    load_dotenv("deploy/secrets/.env-local")

  github = Github(
    auth=Auth.Token(os.environ.get("GH__TOKEN"))
  )

  conn = sqlite3.connect(DB_FILE)
  curr = conn.cursor()

  curr.execute(
    """
    CREATE TABLE IF NOT EXISTS projects (
      id                        INTEGER PRIMARY KEY AUTOINCREMENT,
      tg_mrtm_message_id        INTEGER,
      tg_mrtm_date              TEXT,
      tg_mrtm_sender_chat_id    BIGINT,
      tg_mrtm_sender_chat_title TEXT,
      gh_project_url            TEXT,
      gh_project_name           TEXT
    )
    """
  )
  curr.execute(
    """
    CREATE TABLE IF NOT EXISTS project_issues (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      project_id          INTEGER,
      tg_mrtm_message_id  INTEGER,
      tg_mrtm_message_url TEXT,
      tg_mrtm_user_id     BIGINT,
      tg_mrtm_user_is_bot BOOLEAN,
      tg_message_id       INT,
      tg_message_url      TEXT,
      tg_message_date     TEXT,
      gh_issue_id         INT,
      gh_issue_html_url   TEXT,
      gh_issue_created_at TEXT
    )
    """
  )
  conn.commit()

  logging.basicConfig(level=logging.INFO, stream=sys.stdout)

  bot = Bot(
    token=os.getenv("TG__TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
  )

  asyncio.run(dp.start_polling(bot))