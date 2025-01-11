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
from aiogram.types import Message, BufferedInputFile, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

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
  project_name = parsed_url.path.split("/")[-1]

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
        message.reply_to_message.date.strftime("%Y-%m-%d %H:%M:%S"),
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
        message.reply_to_message.date.strftime("%Y-%m-%d %H:%M:%S"),
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
  pass


if __name__ == "__main__":
  STATIC_DIR = Path("./static")
  STATIC_DIR.mkdir(exist_ok=True)

  DB_FILE = STATIC_DIR / "db.sqlite3"

  if not os.environ.get("BOT__TOKEN"):
    load_dotenv("deploy/secrets/.env-local")

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
      id                        INTEGER PRIMARY KEY AUTOINCREMENT,
      tg_report_post_message_id INTEGER,
      tg_report_message_id      INTEGER,
      tg_report_message_dt      TEXT,
      tg_user_id                BIGINT,
      gh_issue_id               INT
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