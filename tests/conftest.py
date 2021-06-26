import pytest

from bot.exceptions import MessageUpdateRequired
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


@pytest.fixture(name='outage_info_similar')
def fixture_outage_info_similar():
    return OutageInfo(
        type_=OutageType.planned,
        start_date='00.00.0000',
        start_time='00:00',
        end_date='01.01.2001',
        end_time='2:00',
    )


@pytest.fixture(name='generated_message')
def fixture_generated_message(outage_info):
    return (
        f'⚡{outage_info.type_.title}⚡'
        f'Началось {outage_info.start_date} в {outage_info.start_time}'
        f'Закончится {outage_info.end_date} в {outage_info.end_time}'
    )


@pytest.fixture(name='generated_message_updated')
def fixture_generated_message_updated(outage_info_similar):
    return (
        f'⚡{outage_info_similar.type_.title}⚡'
        f'Началось {outage_info_similar.start_date} в {outage_info_similar.start_time}'
        f'Закончится {outage_info_similar.end_date} в {outage_info_similar.end_time}'
    )


@pytest.fixture(name='exception_update_required')
def fixture_exception_update_required():
    return MessageUpdateRequired(date='01.01.2001', time='2:00', message_id=0)


@pytest.fixture(name='planned_url')
def fixture_planned_url():
    return (
        'https://www.mrsk-cp.ru/local/templates/main/components/bitrix/'
        'form.result.new/inform_about_disconnect'
        '/plan_outages.php?region=40&district=093778F4-8378-414B-9905-7A145E4F140F'
        '&place=%D0%A2%D0%BE%D0%B2%D0%B0'
        '%D1%80%D0%BA%D0%BE%D0%B2%D0%BE&begin_date=today&end_date=today'
    )
