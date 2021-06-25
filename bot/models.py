from typing import NamedTuple


class Outage(NamedTuple):
    title: str
    url: str


class OutageType(NamedTuple):
    unplanned = Outage(  # type: ignore
        title='Незапланнированное отключение',
        url='https://www.mrsk-cp.ru/local/templates/main/components/bitrix/form.result.new'
        '/inform_about_disconnect/unplan_outages.php'
        '?region=40&district=093778F4-8378-414B-9905-7A145E4F140F'
        '&place=%D0%9A%D0%BE%D1%80%D0%BE%D0%BA%D0%B8%D0%BD%D0%BE&begin_date=today&end_date=today',
    )
    planned = Outage(  # type: ignore
        title='Запланированное отключение',
        url='https://www.mrsk-cp.ru/local/templates/main/components/bitrix/form.result.new/'
        'inform_about_disconnect/plan_outages.php'
        '?region=40&district=093778F4-8378-414B-9905-7A145E4F140F'
        '&place=%D0%A2%D0%BE%D0%B2%D0%B0%D1%80%D0%BA%D0%BE%D0%B2%D0%BE'
        '&begin_date=today&end_date=today',
    )


class OutageInfo(NamedTuple):
    type_: Outage
    start_date: str
    start_time: str
    end_date: str
    end_time: str
