import os
from typing import Dict
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from aioresponses import aioresponses
from bs4 import BeautifulSoup

from bot.bot import (
    check_outages,
    generate_message,
    get_html_soup,
    is_message_new,
    load_message_history,
    parse_table_row,
    run,
    save_message,
    send_message_to_channel,
)
from bot.exceptions import MessageAlreadyPosted, MessageUpdateRequired
from bot.models import OutageInfo, OutageType


@pytest.mark.asyncio
async def test_get_html_soup(load_html_response, planned_url):
    body = load_html_response.read()
    with aioresponses() as mocked:
        mocked.get(planned_url, status=200, body=body)
        new_soup = await get_html_soup(planned_url)
        assert isinstance(new_soup, BeautifulSoup)
        assert new_soup == BeautifulSoup(body, 'html.parser')


def test_load_message_history():
    m = mock_open()
    with patch('builtins.open', m), patch('pickle.load') as mocked_load:
        load_message_history()
        m.assert_called_once_with('message_list.pickle', 'rb')
        mocked_load.assert_called_once()


@pytest.mark.asyncio
async def test_parse_table_row(load_outage_table, outage_info):
    html = load_outage_table.read()
    info = await parse_table_row(html, OutageType.planned)
    assert info == outage_info


@pytest.mark.asyncio
async def test_is_message_new(outage_info):
    message_history: Dict[OutageInfo, int] = {}
    result = await is_message_new(outage_info, message_history)
    assert result is True


@pytest.mark.asyncio
async def test_is_message_new_already_posted(outage_info):
    message_history: Dict[OutageInfo, int] = {outage_info: 0}
    with pytest.raises(MessageAlreadyPosted):
        await is_message_new(outage_info, message_history)


@pytest.mark.asyncio
async def test_is_message_new_update_required(outage_info, outage_info_similar):
    message_history = {outage_info: 0}
    with pytest.raises(MessageUpdateRequired):
        await is_message_new(outage_info_similar, message_history)


def test_save_message(outage_info):
    m = mock_open()
    message_history: Dict[OutageInfo, int] = {}
    with patch('builtins.open', m) as mocked_open, patch('pickle.dump') as mocked_dump:
        save_message(outage_info, 0, message_history)
        m.assert_called_once_with('message_list.pickle', 'wb')
        handle = mocked_open()
        mocked_dump.assert_called_once_with(message_history, handle)


@pytest.mark.asyncio
async def test_generate_message(outage_info, generated_message):
    result, _ = await generate_message(outage_info)
    assert result == generated_message


@pytest.mark.asyncio
async def test_generate_message_updated(
    outage_info, exception_update_required, generated_message_updated
):
    result, _ = await generate_message(outage_info, exception_update_required)
    assert result == generated_message_updated


@pytest.mark.asyncio
async def test_send_message_to_channel(outage_info):
    channel = 'test_channel'
    b = AsyncMock()
    message_history: Dict[OutageInfo, int] = {}
    with patch.object(os, 'environ', return_value=channel), patch(
        'bot.bot.save_message'
    ):
        await send_message_to_channel(b, outage_info, message_history)
        b.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_message_to_channel_already_posted(outage_info):
    channel = 'test_channel'
    b = AsyncMock()
    message_history = {outage_info: 0}
    with patch.object(os, 'environ', return_value=channel):
        await send_message_to_channel(b, outage_info, message_history)
        b.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_message_to_channel_update_required(
    outage_info, outage_info_similar
):
    channel = 'test_channel'
    b = AsyncMock()
    message_history = {outage_info: 0}
    with patch.object(os, 'environ', return_value=channel), patch(
        'bot.bot.save_message'
    ):
        await send_message_to_channel(b, outage_info_similar, message_history)
        b.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_check_outages(load_html_response, outage_info):
    body = load_html_response.read()
    b = AsyncMock()
    message_history: Dict[OutageInfo, int] = {}
    with patch(
        'bot.bot.get_html_soup', return_value=BeautifulSoup(body, 'html.parser')
    ), patch('bot.bot.parse_table_row', return_value=outage_info), patch(
        'bot.bot.send_message_to_channel'
    ) as mock_send_message_to_channel:
        await check_outages(b, OutageType.planned, message_history)
        mock_send_message_to_channel.assert_called_once_with(
            b, outage_info, message_history
        )


def test_run():
    data_value = 'test_data'
    mock_data = MagicMock(return_value=data_value)
    bot_value = 'bot_instance'
    bot = MagicMock(return_value=bot_value)
    schedule = MagicMock()
    with patch('bot.bot.schedule', schedule) as mock_schedule, patch(
        'bot.bot.Bot', bot
    ) as mock_bot, patch('bot.bot.load_message_history', mock_data), patch.dict(
        'os.environ', {'TELEGRAM_TOKEN': 'fake_token'}
    ):
        run()
        mock_bot.assert_called_once()
        mock_schedule.every(20).minutes.do.assert_called_with(
            check_outages,
            bot=bot_value,
            outage=OutageType.emergency,
            data=data_value,
        )
