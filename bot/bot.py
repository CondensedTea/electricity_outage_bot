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
    datefmt='%d/%m/%y %H:%m:%S',
)
logging.getLogger('schedule').propagate = False


def load_message_history() -> Dict[OutageInfo, int]:
    with open('message_list.pickle', 'rb') as file:
        message_history = pickle.load(file)
    return message_history


def save_message(
    outage: OutageInfo, message_id: int, data: Dict[OutageInfo, int]
) -> None:
    data[outage] = message_id
    with open('message_list.pickle', 'wb') as file:
        pickle.dump(data, file)


async def parse_soup(soup: str, outage: Outage) -> OutageInfo:
    [result] = re.findall(
        r'(\d{2}.\d{2}.\d{4})<.+>(\d{2}:\d{2})</td>'
        r'<td.+>(\d{2}.\d{2}.\d{4})<.+>(\d{2}:\d{2})</td>',
        soup,
    )
    return OutageInfo(
        type_=outage,
        start_date=result[0],
        start_time=result[1],
        end_date=result[2],
        end_time=result[3],
    )


async def get_html_soup(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()
    soup_as_text = str(BeautifulSoup(html, 'html.parser'))
    return soup_as_text


async def is_message_new(new_outage: OutageInfo, data: Dict[OutageInfo, int]) -> bool:
    old_outage = list(data)[-1]
    if new_outage in data:
        raise MessageAlreadyPosted
    if (
        new_outage.start_date == old_outage.start_date
        and new_outage.end_time != old_outage.end_time
    ):
        raise MessageUpdateRequired(
            date=new_outage.end_date,
            time=new_outage.end_time,
            message_id=list(data.values())[-1],
        )
    return True


async def generate_message(
    outage: OutageInfo, exception: Optional[MessageUpdateRequired] = None
) -> Tuple[str, OutageInfo]:
    if exception:
        fixed_outage = outage._replace(
            end_date=exception.new_date, end_time=exception.new_time
        )
    else:
        fixed_outage = outage
    return (
        f'⚡{fixed_outage.type_.title}⚡\n'
        f'Началось {fixed_outage.start_date} в {fixed_outage.start_time}\n'
        f'Закончится {fixed_outage.end_date} в {fixed_outage.end_time}'
    ), fixed_outage


async def send_message_to_channel(
    bot: Bot, outage: OutageInfo, message_history: Dict[OutageInfo, int]
) -> None:
    try:
        await is_message_new(outage, message_history)
    except MessageAlreadyPosted:
        logging.debug('Message already posted')
        return
    except MessageUpdateRequired as e:
        logging.debug(
            'Message update is required, new date/time: %s/%s', e.new_date, e.new_time
        )
        text, fixed_outage = await generate_message(outage, e)
        message = await bot.edit_message_text(
            chat_id=os.environ['TELEGRAM_CHAT'], text=text, message_id=e.message_id
        )
        save_message(fixed_outage, message.message_id, message_history)
    else:
        text, _ = await generate_message(outage)
        message = await bot.send_message(chat_id=os.environ['TELEGRAM_CHAT'], text=text)
        await bot.pin_chat_message(
            chat_id=os.environ['TELEGRAM_CHAT'],
            message_id=message.message_id,
            disable_notification=True,
        )
        save_message(outage, message.message_id, message_history)


async def check_outages(bot: Bot, outage: Outage, data: Dict[OutageInfo, int]) -> None:
    soup = await get_html_soup(outage.url)
    outage_info = await parse_soup(soup, outage)
    logging.info('Got an outage!')
    await send_message_to_channel(bot, outage_info, data)


def run() -> None:
    logging.info('Bot is running')
    data = load_message_history()
    bot = Bot(token=os.environ['TELEGRAM_TOKEN'])
    schedule.every(2).seconds.do(
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
    logging.info('Initial tasks was started')


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    run()
    while True:
        loop.run_until_complete(schedule.run_pending())
        time.sleep(0.1)
