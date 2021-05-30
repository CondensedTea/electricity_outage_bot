import pytest

from bot.models import OutageInfo, OutageType


@pytest.fixture(name='load_html_response')
def fixture_load_html_response():
    with open('tests/responses/outage.html') as file:
        yield file


@pytest.fixture(name='load_outage_table')
def fixture_load_outage_table():
    with open('tests/responses/table.html') as file:
        yield file


@pytest.fixture(name='outage_info')
def fixture_outage_info():
    return OutageInfo(
        type_=OutageType.planned,
        start_date='00.00.0000',
        start_time='00:00',
        end_date='00.00.0000',
        end_time='00:00',
    )


@pytest.fixture(name='telegram_message_hash')
def fixture_telegram_message_hash(outage_info):
    return hash(
        f'⚡{outage_info.type_}⚡\nНачалось в {outage_info.start_date},'
        f' {outage_info.start_time}\nЗакончится в {outage_info.end_date}, {outage_info.end_time}'
    )
