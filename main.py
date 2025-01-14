import os
import sys
import sqlite3
import logging
import asyncio
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, html, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from github import Github, Auth
from github.GithubException import UnknownObjectException

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
  if message.reply_to_message.message_id != state_data.get("bot_message_id"):
    return
  url = message.text.strip()
  parsed_url = urlparse(url)
  if parsed_url.netloc != SupportedCodeHubs.github.value:
    fail_msg = await message.reply(
      f"[?] Not supported: {parsed_url.netloc or url}"
    )
    await asyncio.sleep(1.5)
    await fail_msg.delete()
    await message.delete()
    return

  project_id = state_data.get("project_id")
  gh_repository_full_name = "/".join(
    tuple(filter(bool, parsed_url.path.split("/", maxsplit=3)))[:2]
  )
  try:
    repository = github.get_repo(gh_repository_full_name)
  except UnknownObjectException:
    fail_msg = await message.reply(
      f"[?] Repository ({gh_repository_full_name}) is not found "
      "or you have no access!"
    )
    await asyncio.sleep(2.5)
    await fail_msg.delete()
    await message.delete()
    return

  curr.execute(
    """
    UPDATE
      projects
    SET
      gh_repository_url = ?,
      gh_repository_full_name = ?
    WHERE
      id = ?
    """,
    (
      repository.html_url,
      gh_repository_full_name,
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
    SELECT id FROM projects WHERE tg_channel_id = ?
    """,
    (
      message.reply_to_message.sender_chat.id,
    )
  )
  project = curr.fetchone()
  if project:
    await message.reply(
      f"[!] Project(id={project[0]}) already has been created!"
    )
    await state.clear()
    return

  curr.execute(
    """
    INSERT INTO
      projects (
        tg_channel_id,
        tg_channel_title,
        tg_channel_post_url,
        tg_channel_post_date
      )
    VALUES (
      ?, ?, ?, ?
    )
    """,
    (
      message.reply_to_message.sender_chat.id,
      message.reply_to_message.sender_chat.title,
      message.reply_to_message.get_url(force_private=True),
      message.reply_to_message.date.strftime(MESSAGE_DT_FORMAT),
    )
  )
  conn.commit()

  await state.update_data(project_id=curr.lastrowid)
  await state.update_data(admin_message_id=message.message_id)

  message = await message.reply("Reply GitHub/Project URL")

  await state.update_data(bot_message_id=message.message_id)


@dp.message(Command("report"))
async def report_handler(message: Message) -> None:
  # XXX: FEAT:
  # - set the MAX issue "REAL" (not report) for the `tg_channel_post_url`

  if not message.reply_to_message.sender_chat:
    await message.reply("Comment to the channel post to `/report`")
    return

  curr.execute(
    """
    SELECT
      id, tg_channel_title, gh_repository_full_name
    FROM
      projects
    WHERE
      tg_channel_id = ?
    """,
    (
      message.reply_to_message.sender_chat.id,
    )
  )
  project = curr.fetchone()
  # NOTE: checking any project is registered for the `channel`
  if project is None:
    await message.reply(
      "[?] Project is not registered for the chat: "
      f"{html.bold(message.reply_to_message.sender_chat.title)}\n"
      "[!] Bot/Admin only /start"
    )
    return

  project_id, tg_channel_title, gh_repository_full_name = project

  tg_user_id = message.from_user.id
  tg_user_is_bot = message.from_user.is_bot
  tg_message_url = message.get_url(force_private=True)
  tg_message_date = message.date.strftime(MESSAGE_DT_FORMAT)
  tg_channel_post_url = message.reply_to_message.get_url(force_private=True)

  curr.execute(
    """
    SELECT
      gh_issue_html_url
    FROM
      project_issues
    WHERE
      project_id = ?
    AND
      tg_channel_post_url = ?
    """,
    (
      # XXX: `tg_channel_post_url` is unique, no need to filter by `project_id`
      project_id,
      tg_channel_post_url,
    )
  )
  project_issue = curr.fetchone()
  # NOTE: checking if any issue is registered for the `channel_post`
  if project_issue:
    await message.reply(
      f"[!] GitHub Issue already has been created at: {project_issue[0]}",
    )
    return

  try:
    repository = github.get_repo(gh_repository_full_name)
  except UnknownObjectException:
    await message.reply(
      f"[?] Repository ({gh_repository_full_name}) is not found "
      "or you have no access!"
    )
    return

  # ChannelTitle / ChannelPostTitle / message_id
  issue = repository.create_issue(
    title=f"{tg_channel_title} / {message.chat.title} / {message.message_id}",
    body=\
      f"[{tg_message_date}] - [{tg_user_is_bot}] - [{tg_user_id}]\n"
      "---\n"
      f"[ChannelPostURL]({tg_channel_post_url}) - [ChannelPostCommentURL]({tg_message_url})"
  )

  curr.execute(
    """
    INSERT INTO
      project_issues (
        project_id,
        tg_user_id,
        tg_user_is_bot,
        tg_message_url,
        tg_message_date,
        tg_channel_post_url,
        gh_issue_id,
        gh_issue_html_url,
        gh_issue_created_at
      )
    VALUES
      (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
      project_id,
      tg_user_id,
      tg_user_is_bot,
      tg_message_url,
      tg_message_date,
      tg_channel_post_url,
      issue.id,
      issue.html_url,
      issue.created_at.strftime(MESSAGE_DT_FORMAT),
    )
  )
  conn.commit()

  await message.reply(f"[!] GitHub Issue created at: {issue.html_url}")


if __name__ == "__main__":
  MESSAGE_DT_FORMAT = "%Y-%m-%d %H:%M:%S"

  STATIC_DIR = Path("./static")
  STATIC_DIR.mkdir(exist_ok=True)

  DB_FILE = STATIC_DIR / "db.sqlite3"

  if not os.environ.get("TG__TOKEN"):
    load_dotenv("deploy/secrets/.env-local")

  github = Github(
    auth=Auth.Token(os.environ.get("GH__TOKEN"))
  )

  conn = sqlite3.connect(DB_FILE)
  curr = conn.cursor()
  curr.execute(
    """
    CREATE TABLE IF NOT EXISTS projects (
      id                      INTEGER PRIMARY KEY AUTOINCREMENT,
      tg_channel_id           BIGINT,
      tg_channel_title        TEXT,

      -- I may not need this here
      -- Project is registered for the `channel_id`
      -- I'll keep in case project will be registered to `channel_post_url`
      tg_channel_post_url     TEXT,
      tg_channel_post_date    TEXT,

      gh_repository_url       TEXT,
      gh_repository_full_name TEXT
    )
    """
  )
  curr.execute(
    """
    CREATE TABLE IF NOT EXISTS project_issues (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      project_id          INTEGER,
      tg_user_id          BIGINT,
      tg_user_is_bot      BOOLEAN,
      tg_message_url      TEXT,
      tg_message_date     TEXT,

      -- issue per post, use to filter
      tg_channel_post_url TEXT,

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