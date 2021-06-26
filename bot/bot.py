import asyncio
import logging
import os
import pickle
import re
import time

import aiohttp
import aioschedule as schedule
from aiogram import Bot
from bs4 import BeautifulSoup

from bot.exceptions import MessageAlreadyPosted
from bot.models import Outage, OutageInfo, OutageType

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%d/%m/%y %H:%m:S',
)
logging.getLogger('schedule').propagate = False


def load_message_list() -> list[int]:
    with open('message_list.pickle', 'rb') as file:
        d = pickle.load(file)
    return d


async def parse_table_row(row: str, outage: Outage) -> OutageInfo:
    [result] = re.findall(
        r'(\d{2}.\d{2}.\d{4})</td><td.+>(\d{2}:\d{2})</td>'
        r'<td.+>(\d{2}.\d{2}.\d{4})</td><.+>(\d{2}:\d{2})</td>',
        row,
    )
    return OutageInfo(
        type_=outage,
        start_date=result[0],
        start_time=result[1],
        end_date=result[2],
        end_time=result[3],
    )


async def get_html_soup(url: str) -> BeautifulSoup:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()
    return BeautifulSoup(html, 'html.parser')


def check_hash(message: str, message_list: list[int]) -> None:
    h = hash(message)
    if h in message_list:
        raise MessageAlreadyPosted
    message_list.append(h)
    with open('message_list.pickle', 'wb') as file:
        pickle.dump(message_list, file)


async def send_message_to_channel(
    bot: Bot, outage: OutageInfo, posted_messages: list[int]
) -> None:
    text = (
        f'⚡{outage.type_.title}⚡'
        f'Началось {outage.start_date} в {outage.start_time}'
        f'Закончится {outage.end_date} в {outage.end_time}'
    )
    try:
        check_hash(text, posted_messages)
    except MessageAlreadyPosted:
        return
    await bot.send_message(chat_id=os.environ['TELEGRAM_CHAT'], text=text)


async def check_outages(bot: Bot, outage: Outage, data: list[int]) -> None:
    soup = await get_html_soup(outage.url)
    for r in soup.find_all('tr', {'class': 'outages-table__row'}):
        if 'outages-table__row_header' in r['class']:
            continue
        outage_info = await parse_table_row(str(r), outage)
        logging.info('Got an outage! Sending the message...')
        await send_message_to_channel(bot, outage_info, data)


def run(telegram_token: str) -> None:
    logging.info('Bot is running, scheduling tasks...')
    data = load_message_list()
    bot = Bot(token=telegram_token)
    schedule.every(20).minutes.do(
        check_outages,
        bot=bot,
        outage=OutageType.unplanned,
        data=data,
    )
    schedule.every(20).minutes.do(
        check_outages, bot=bot, outage=OutageType.planned, data=data
    )


if __name__ == '__main__':
    token = os.environ['TELEGRAM_TOKEN']
    loop = asyncio.get_event_loop()
    run(token)
    while True:
        loop.run_until_complete(schedule.run_pending())
        time.sleep(0.1)
