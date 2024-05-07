from __future__ import annotations

from typing import List, Dict
from abc import ABC, abstractmethod

from .kernel import Kernel, Operator

INSTRUCTION = """
ghost 应该是系统使用者看到的对象. 
而不是 AI 自己看到的自己. 这两者要有所区别. 

给开发者看到的 Interface 要足够简单, 因为我们开发者都是非常非常的 stupid, 不想动一点脑子. 

要考虑同步异步之类的各种问题. 
"""


class Ghost(ABC):
    """
    机器人的灵魂.
    Ghost 本身只有同步接口.
    全异步的调度放在外层, 要克制.
    可以允许外部将 Ghost 包装成 Prototype.
    Prototype 动态去构建 Ghost 的各种组件.
    """

    # properties

    @property
    @abstractmethod
    def shells(self) -> Dict[str, Shell]:
        """
        可以操作的躯壳. 跟随会话状态可能会变.
        """
        pass

    @property
    @abstractmethod
    def mindset(self) -> Mindset:
        """
        思维状态.
        """
        pass

    @property
    @abstractmethod
    def session(self) -> Session:
        """
        会话状态.
        """
        pass

    # api

    @abstractmethod
    def answer(self, question: str) -> str:
        """
        测试时用的简单接口. 没有什么意义的.
        """
        pass

    @abstractmethod
    def think(self, thought: Thought) -> Messenger:
        """
        直接控制 Ghost 思维状态.
        还没想好这个方法要不要.
        """
        pass

    @abstractmethod
    def on_message(self) -> Messenger:
        """
        假设 Ghost 接受到了一个格式化的消息.
        消息会转化为一个 event, 继续触发.
        """
        pass

    @abstractmethod
    def on_event(self) -> Messenger:
        """
        on_event 是系统的底层.
        """
        pass


class Event(ABC):
    """
    Ghost 的事件体系. 不同层的事件体系处理逻辑不一样.
    """
    pass


class Messenger(ABC):
    """
    消息的传递模块.
    需要支持各种消息的传递方式. 常见的有:
    1. 同步整体返回
    2. 同步流式 (多模态, 可扩展) 返回.
    """


class Session(ABC):
    """
    Ghost 的会话构建.
    """


class Shell(ABC):
    """
    Ghost 所在的 Shell.
    提供 API 操作自己的 Shell.
    一个有状态的 Ghost 可以同时存在于多个 Shell.
    """


# ---- bot 的思维空间.

class Mindset(ABC):
    """
    Ghost 的思维空间.
    合并了 Mindset / Knowledge / Memory
    三者理论上可以互相调用, 只要逻辑上不成环.
    为了让 Ghost 有学习成长的能力.
    """

    @property
    @abstractmethod
    def knowledge(self) -> Knowledge:
        pass

    @property
    @abstractmethod
    def memory(self) -> Memory:
        pass


class Thought(ABC):
    """
    思维能力的定义.
    """

    @abstractmethod
    def on_event(self) -> Operator:
        pass


class Knowledge(ABC):
    """
    Ghost 的知识. 要有一种允许开发者给 Ghost 提供知识的方式.
    """
    pass


class Memory(ABC):
    """
    记忆空间. 与知识空间的区别是什么?
    记忆假设和 Ghost 自身行为是相关的, 而且是 Ghost 主动驱动的.
    要设计足够通用的 interface.
    """
    pass