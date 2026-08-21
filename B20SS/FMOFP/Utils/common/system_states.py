from enum import Enum

class SystemState(Enum):
    BOOT = -1
    INITIALIZING = 0
    INITIALIZED = 1
    STARTING = 2
    RUNNING = 3
    NORMAL = 4 
    ERROR = 5
    SHUTTING_DOWN = 6
    SHUTDOWN = 7

class userCLIStates(Enum):
    NOT_ACCEPTING_COMMANDS = 0
    ACCEPTING_COMMANDS = 1