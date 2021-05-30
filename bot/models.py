from typing import NamedTuple


class OutageType(NamedTuple):
    unplanned = 'Незапланнированное отключение'  # type: ignore
    planned = 'Запланированное отключение'  # type: ignore


class OutageInfo(NamedTuple):
    type_: str
    start_date: str
    start_time: str
    end_date: str
    end_time: str
