from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from aioresponses import aioresponses
from bs4 import BeautifulSoup

from bot import bot
from bot.bot import (
    check_hash,
    check_outages,
    get_html_soup,
    load_message_list,
    parse_table_row,
    planned_url,
    run,
    send_message_to_channel,
)
from bot.exceptions import MessageAlreadyPosted
from bot.models import OutageType


@pytest.mark.asyncio
async def test_get_html_soup(load_html_response):
    body = load_html_response.read()
    with aioresponses() as mocked:
        mocked.get(planned_url, status=200, body=body)
        new_soup = await get_html_soup(planned_url)
        assert isinstance(new_soup, BeautifulSoup)
        assert new_soup == BeautifulSoup(body, 'html.parser')


def test_load_message_list():
    m = mock_open()
    with patch('builtins.open', m), patch('pickle.load') as mocked_load:
        load_message_list()
        m.assert_called_once_with('data/message_list.pickle', 'rb')
        mocked_load.assert_called_once()


@pytest.mark.asyncio
async def test_parse_table_row(load_outage_table, outage_info):
    html = load_outage_table.read()
    info = await parse_table_row(html, OutageType.planned)
    assert info == outage_info


def test_check_hash_normal():
    message = 'test_message'
    message_list: list[int] = []
    m = mock_open()
    with patch('builtins.open', m) as mocked_open, patch('pickle.dump') as mocked_dump:
        check_hash(message, message_list)
        m.assert_called_once_with('data/message_list.pickle', 'wb')
        handle = mocked_open()
        mocked_dump.assert_called_once_with(message_list, handle)


@pytest.mark.asyncio
async def test_send_message_to_channel_normal(outage_info):
    channel = 'test_channel'
    b = AsyncMock()
    message_list: list[int] = []
    with patch.object(bot, 'chat', channel):
        await send_message_to_channel(b, outage_info, message_list)
        b.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_message_to_channel_exception(outage_info, telegram_message_hash):
    channel = 'test_channel'
    b = AsyncMock()
    message_list: list[int] = [telegram_message_hash]
    with patch.object(bot, 'chat', channel):
        await send_message_to_channel(b, outage_info, message_list)
        b.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_check_outages(load_html_response, outage_info):
    body = load_html_response.read()
    b = AsyncMock()
    url = 'test'
    message_list: list[int] = []
    with patch(
        'bot.bot.get_html_soup', return_value=BeautifulSoup(body, 'html.parser')
    ), patch('bot.bot.parse_table_row', return_value=outage_info), patch(
        'bot.bot.send_message_to_channel'
    ) as mock_send_message_to_channel:
        await check_outages(b, url, OutageType.planned, message_list)
        mock_send_message_to_channel.assert_called_once_with(
            b, outage_info, message_list
        )


def test_check_hash_exception():
    message = 'test_message'
    message_list = [hash(message)]
    m = mock_open()
    with pytest.raises(MessageAlreadyPosted):
        with patch('builtins.open', m), patch('pickle.dump'):
            check_hash(message, message_list)


def test_run():
    data_value = 'test_data'
    mock_data = MagicMock(return_value=data_value)
    token = 'test'
    _bot_value = 'bot_instance'
    _bot = MagicMock(token=token, return_value=_bot_value)
    schedule = MagicMock()
    with patch('bot.bot.schedule', schedule) as mock_schedule, patch(
        'bot.bot.Bot', _bot
    ) as mock_bot, patch('bot.bot.load_message_list', mock_data):
        run()
        mock_bot.assert_called_once()
        mock_schedule.every().hour.do.assert_called_with(
            check_outages,
            bot=_bot_value,
            url=planned_url,
            _type=OutageType.planned,
            data=data_value,
        )
