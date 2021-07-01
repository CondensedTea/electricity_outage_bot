import os
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
    parse_soup,
    run,
    save_message,
    send_message_to_channel,
)
from bot.exceptions import MessageAlreadyPosted, MessageUpdateRequired, OutageNotFound
from bot.models import OutageType


@pytest.mark.asyncio
async def test_get_html_soup(load_html_response, planned_url):
    body = load_html_response.read()
    with aioresponses() as mocked:
        mocked.get(planned_url, status=200, body=body)
        new_soup = await get_html_soup(planned_url)
        assert new_soup == str(BeautifulSoup(body, 'html.parser'))


def test_load_message_history():
    m = mock_open()
    with patch('builtins.open', m), patch('pickle.load') as mocked_load:
        load_message_history()
        m.assert_called_once_with('message_list.pickle', 'rb')
        mocked_load.assert_called_once()


@pytest.mark.asyncio
async def test_parse_soup(load_outage_table, outage_info_empty):
    html = load_outage_table.read()
    soup = str(BeautifulSoup(html, 'html.parser'))
    info = await parse_soup(soup, OutageType.planned)
    assert info == outage_info_empty


@pytest.mark.asyncio
async def test_parse_soup_outage_not_found(load_empty_html_response):
    html = load_empty_html_response.read()
    soup = str(BeautifulSoup(html, 'html.parser'))
    with pytest.raises(OutageNotFound):
        await parse_soup(soup, OutageType.planned)


@pytest.mark.asyncio
async def test_is_message_new(outage_info, message_history_empty):
    result = await is_message_new(outage_info, message_history_empty)
    assert result is True


@pytest.mark.asyncio
async def test_is_message_new_already_posted(outage_info, message_history_default):
    with pytest.raises(MessageAlreadyPosted):
        await is_message_new(outage_info, message_history_default)


@pytest.mark.asyncio
async def test_is_message_new_update_required(
    outage_info_similar, message_history_default
):
    with pytest.raises(MessageUpdateRequired):
        await is_message_new(outage_info_similar, message_history_default)


def test_save_message(outage_info, message_history_empty):
    m = mock_open()
    with patch('builtins.open', m) as mocked_open, patch('pickle.dump') as mocked_dump:
        save_message(outage_info, 0, message_history_empty)
        m.assert_called_once_with('message_list.pickle', 'wb')
        handle = mocked_open()
        mocked_dump.assert_called_once_with(message_history_empty, handle)


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
async def test_send_message_to_channel(outage_info, message_history_empty):
    b = AsyncMock()
    with patch.object(os, 'environ', return_value='test_channel'), patch(
        'bot.bot.save_message'
    ):
        await send_message_to_channel(b, outage_info, message_history_empty)
        b.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_message_to_channel_already_posted(
    outage_info, message_history_default
):
    b = AsyncMock()
    with patch.object(os, 'environ', return_value='test_channel'):
        await send_message_to_channel(b, outage_info, message_history_default)
        b.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_message_to_channel_update_required(
    outage_info_similar, message_history_default
):
    b = AsyncMock()
    with patch.object(os, 'environ', return_value='test_channel'), patch(
        'bot.bot.save_message'
    ):
        await send_message_to_channel(b, outage_info_similar, message_history_default)
        b.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_check_outages(load_html_response, outage_info, message_history_empty):
    body = load_html_response.read()
    b = AsyncMock()
    with patch(
        'bot.bot.get_html_soup', return_value=BeautifulSoup(body, 'html.parser')
    ), patch('bot.bot.parse_soup', return_value=outage_info), patch(
        'bot.bot.send_message_to_channel'
    ) as mock_send_message_to_channel:
        await check_outages(b, OutageType.planned, message_history_empty)
        mock_send_message_to_channel.assert_called_once_with(
            b, outage_info, message_history_empty
        )


@pytest.mark.asyncio
async def test_check_outages_outage_not_found(
    load_empty_html_response, message_history_empty
):
    body = load_empty_html_response.read()
    b = AsyncMock()
    with patch(
        'bot.bot.get_html_soup', return_value=BeautifulSoup(body, 'html.parser')
    ), patch('bot.bot.parse_soup', side_effect=OutageNotFound), patch(
        'bot.bot.send_message_to_channel'
    ) as mock_send_message_to_channel:
        await check_outages(b, OutageType.planned, message_history_empty)
        mock_send_message_to_channel.assert_not_called()


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
