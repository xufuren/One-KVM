# ========================================================================== #
#                                                                            #
#    KVMD - The main PiKVM daemon.                                           #
#                                                                            #
#    Copyright (C) 2018-2024  Maxim Devaev <mdevaev@gmail.com>               #
#                                                                            #
#    This program is free software: you can redistribute it and/or modify    #
#    it under the terms of the GNU General Public License as published by    #
#    the Free Software Foundation, either version 3 of the License, or       #
#    (at your option) any later version.                                     #
#                                                                            #
#    This program is distributed in the hope that it will be useful,         #
#    but WITHOUT ANY WARRANTY; without even the implied warranty of          #
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the           #
#    GNU General Public License for more details.                            #
#                                                                            #
#    You should have received a copy of the GNU General Public License       #
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.  #
#                                                                            #
# ========================================================================== #


import re
import asyncio
import time


from typing import AsyncGenerator
from xmlrpc.client import ServerProxy

from ...logging import get_logger

try:
    import systemd.journal
except ImportError as e:
    get_logger(0).error("Failed to import module: %s", "systemd.journal")
    us_systemd_journal = False

try:
    import supervisor.xmlrpc
except ImportError as e:
    get_logger(0).info("Failed to import module: %s", "supervisor.xmlrpc")
    us_systemd_journal = True


# =====
class LogReader:
    async def poll_log(self, seek: int, follow: bool) -> AsyncGenerator[dict, None]:
        if us_systemd_journal:
            reader = systemd.journal.Reader() # type: ignore
            reader.this_boot()
            # XXX: Из-за смены ID машины в bootconfig это не работает при первой загрузке.
            # reader.this_machine()
            reader.log_level(systemd.journal.LOG_DEBUG) # type: ignore
            services = set(
                service
                for service in systemd.journal.Reader().query_unique("_SYSTEMD_UNIT") # type: ignore
                if re.match(r"kvmd(-\w+)*\.service", service)
            ).union(["kvmd.service"])

            for service in services:
                reader.add_match(_SYSTEMD_UNIT=service)
            if seek > 0:
                reader.seek_realtime(float(time.time() - seek))

            for entry in reader:
                yield self.__entry_to_record(entry)

            while follow:
                entry = reader.get_next()
                if entry:
                    yield self.__entry_to_record(entry)
                else:
                    await asyncio.sleep(1)
        else:
            server = ServerProxy('http://127.0.0.1',transport=supervisor.xmlrpc.SupervisorTransport(None, None, serverurl='unix:///tmp/supervisor.sock'))
            log_entries = server.supervisor.readLog(0,0)
            yield log_entries
            

    def __entry_to_record(self, entry: dict) -> dict[str, dict]:
        return {
            "dt": entry["__REALTIME_TIMESTAMP"],
            "service": entry["_SYSTEMD_UNIT"],
            "msg": entry["MESSAGE"].rstrip(),
        }
