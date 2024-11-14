
from agentflow.core import config


config_test = {
    'version': 2, 
    'broker': {
        'broker_type': 'mqtt', 
        'host': 'localhost', 
        'port': 1884, 
        'username': 'eric', 
        'password': 'eric123', 
        'keepalive': 60
    },
    config.CONCURRENCY_TYPE: 'thread',
}

