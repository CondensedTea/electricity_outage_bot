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
from bot.models import OutageInfo, OutageType

unplanned_url = (
    'https://www.mrsk-cp.ru/local/templates/main/components/bitrix/form.result.new'
    '/inform_about_disconnect/unplan_outages.php'
    '?region=40&district=093778F4-8378-414B-9905-7A145E4F140F'
    '&place=%D0%9A%D0%BE%D1%80%D0%BE%D0%BA%D0%B8%D0%BD%D0%BE&begin_date=today&end_date=today'
)
planned_url = (
    'https://www.mrsk-cp.ru/local/templates/main/components/bitrix/form.result.new/'
    'inform_about_disconnect/plan_outages.php'
    '?region=40&district=093778F4-8378-414B-9905-7A145E4F140F'
    '&place=%D0%A2%D0%BE%D0%B2%D0%B0%D1%80%D0%BA%D0%BE%D0%B2%D0%BE&begin_date=today&end_date=today'
)


logging.basicConfig(level=logging.INFO)


def load_message_list() -> list[int]:
    with open('message_list.pickle', 'rb') as file:
        d = pickle.load(file)
    return d


async def parse_table_row(row: str, type_: str) -> OutageInfo:
    [result] = re.findall(
        r'(\d{2}.\d{2}.\d{4})</td><td.+>(\d{2}:\d{2})</td>'
        r'<td.+>(\d{2}.\d{2}.\d{4})</td><.+>(\d{2}:\d{2})</td>',
        row,
    )
    return OutageInfo(
        type_=type_,
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
    _bot: Bot, outage: OutageInfo, data: list[int]
) -> None:
    text = (
        f'⚡{outage.type_}⚡\nНачалось в {outage.start_date},'
        f' {outage.start_time}\nЗакончится в {outage.end_date}, {outage.end_time}'
    )
    try:
        check_hash(text, data)
    except MessageAlreadyPosted:
        return
    await _bot.send_message(chat_id=os.environ['telegram-chat'], text=text)


async def check_outages(_bot: Bot, url: str, _type: str, data: list[int]) -> None:
    soup = await get_html_soup(url)
    for r in soup.find_all('tr', {'class': 'outages-table__row'}):
        if 'outages-table__row_header' in r['class']:
            continue
        outage = await parse_table_row(str(r), _type)
        logging.info('Got a outage! Sending the message...')
        await send_message_to_channel(_bot, outage, data)


def run(_token: str) -> None:
    logging.info('Bot is running, scheduling tasks...')
    data = load_message_list()
    bot = Bot(token=_token)
    schedule.every().hour.do(
        check_outages,
        _bot=bot,
        url=unplanned_url,
        _type=OutageType.unplanned,
        data=data,
    )
    schedule.every().hour.do(
        check_outages, _bot=bot, url=planned_url, _type=OutageType.planned, data=data
    )


if __name__ == '__main__':
    token = os.environ['telegram-token']
    loop = asyncio.get_event_loop()
    run(token)
    while True:
        loop.run_until_complete(schedule.run_pending())
        time.sleep(0.1)
