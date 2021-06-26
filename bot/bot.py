import asyncio
import logging
import os
import pickle
import re
import time
from typing import Dict, Optional, Tuple

import aiohttp
import aioschedule as schedule
from aiogram import Bot
from bs4 import BeautifulSoup

from bot.exceptions import MessageAlreadyPosted, MessageUpdateRequired
from bot.models import Outage, OutageInfo, OutageType

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%d/%m/%y %H:%m:S',
)
logging.getLogger('schedule').propagate = False


def load_message_history() -> Dict[OutageInfo, int]:
    with open('message_list.pickle', 'rb') as file:
        od = pickle.load(file)
    return od


async def parse_table_row(row: str, outage: Outage) -> OutageInfo:
    [result] = re.findall(
        r'(\d{2}.\d{2}.\d{4})<.+>(\d{2}:\d{2})</td>'
        r'<td.+>(\d{2}.\d{2}.\d{4})<.+>(\d{2}:\d{2})</td>',
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


async def is_message_new(outage: OutageInfo, data: Dict[OutageInfo, int]) -> bool:
    if outage in data:
        raise MessageAlreadyPosted
    if data and outage.start_date == list(data)[-1].start_date:
        raise MessageUpdateRequired(
            date=outage.start_date,
            time=outage.start_time,
            message_id=list(data.values())[-1],
        )
    return True


def save_message(
    outage: OutageInfo, message_id: int, data: Dict[OutageInfo, int]
) -> None:
    data[outage] = message_id
    with open('message_list.pickle', 'wb') as file:
        pickle.dump(data, file)


async def generate_message(
    outage: OutageInfo, exception: Optional[MessageUpdateRequired] = None
) -> Tuple[str, OutageInfo]:
    if exception:
        outage = outage._replace(
            end_date=exception.new_date, end_time=exception.new_time
        )
    return (
        f'⚡{outage.type_.title}⚡'
        f'Началось {outage.start_date} в {outage.start_time}'
        f'Закончится {outage.end_date} в {outage.end_time}'
    ), outage


async def send_message_to_channel(
    bot: Bot, outage: OutageInfo, message_history: Dict[OutageInfo, int]
) -> None:
    try:
        await is_message_new(outage, message_history)
    except MessageAlreadyPosted:
        return
    except MessageUpdateRequired as e:
        text, fixed_outage = await generate_message(outage, e)
        message = await bot.edit_message_text(
            chat_id=os.environ['TELEGRAM_CHAT'], text=text, message_id=e.message_id
        )
        message_history.pop(fixed_outage)
    else:
        text, _ = await generate_message(outage)
        message = await bot.send_message(chat_id=os.environ['TELEGRAM_CHAT'], text=text)
    await message.pin(disable_notification=True)
    save_message(outage, message.message_id, message_history)


async def check_outages(bot: Bot, outage: Outage, data: Dict[OutageInfo, int]) -> None:
    soup = await get_html_soup(outage.url)
    for r in soup.find_all('tr', {'class': 'outages-table__row'}):
        if 'outages-table__row_header' in r['class']:
            continue
        outage_info = await parse_table_row(str(r), outage)
        logging.info('Got an outage! Sending the message...')
        await send_message_to_channel(bot, outage_info, data)


def run() -> None:
    logging.info('Bot is running, scheduling tasks...')
    data = load_message_history()
    bot = Bot(token=os.environ['TELEGRAM_TOKEN'])
    schedule.every(20).minutes.do(
        check_outages,
        bot=bot,
        outage=OutageType.unplanned,
        data=data,
    )
    schedule.every(20).minutes.do(
        check_outages, bot=bot, outage=OutageType.planned, data=data
    )
    schedule.every(20).minutes.do(
        check_outages, bot=bot, outage=OutageType.emergency, data=data
    )


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    run()
    while True:
        loop.run_until_complete(schedule.run_pending())
        time.sleep(0.1)
