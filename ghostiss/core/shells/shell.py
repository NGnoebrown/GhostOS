from abc import ABC, abstractmethod
from typing import List, Type, Dict
from ghostiss.entity import Entity, EntityFactory
from ghostiss.core.shells.messenger import Messenger


class Driver(ABC):
    """
    可以实现的抽象驱动.
    """

    @classmethod
    @abstractmethod
    def description(cls) -> str:
        pass


class App(ABC):
    """
    自解释的 app.
    """

    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def description(self) -> str:
        pass


class Shell(ABC):

    @abstractmethod
    def id(self) -> str:
        pass

    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def get_drivers(self, drivers: List[Type[Driver]]) -> Dict[str, Driver]:
        pass

    @abstractmethod
    def get_apps(self) -> List[App]:
        pass

    @abstractmethod
    def messenger(self) -> Messenger:
        pass


class ShellFactory(EntityFactory[Shell], ABC):
    pass
