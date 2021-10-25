from typing import Optional

from xrpl.clients import WebsocketClient
from xrpl.models import ServerInfo

from slk.config_file import ConfigFile

class RippleClient(WebsocketClient):
    def __init__(self, config, command_log, exe):
        section = config.port_ws_admin_local
        self.websocket_uri = f'{section.protocol}://{section.ip}:{section.port}'
        super().__init__(url=self.websocket_uri)
        self.config = config
        self.exe = exe
        self.command_log = command_log
        self.subscription_websockets = []
        self.tasks = []
        self.pid = None
        if command_log:
            with open(self.command_log, 'w') as f:
                f.write(f'# Start \n')
    
    @property
    def config_file_name(self):
        return self.config.get_file_name()

    def shutdown(self):
        self.close()

    def set_pid(self, pid: int):
        self.pid = pid

    def get_pid(self) -> Optional[int]:
        return self.pid
    
    def get_config(self) -> ConfigFile:
        return self.config

    # Get a dict of the server_state, validated_ledger_seq, and complete_ledgers
    def get_brief_server_info(self) -> dict:
        ret = {
            'server_state': 'NA',
            'ledger_seq': 'NA',
            'complete_ledgers': 'NA'
        }
        if not self.pid or self.pid == -1:
            return ret
        r = self.request(ServerInfo()).result
        if 'info' not in r:
            return ret
        r = r['info']
        for f in ['server_state', 'complete_ledgers']:
            if f in r:
                ret[f] = r[f]
        if 'validated_ledger' in r:
            ret['ledger_seq'] = r['validated_ledger']['seq']
        return ret