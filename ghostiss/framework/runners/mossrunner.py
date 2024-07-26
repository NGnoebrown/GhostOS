from typing import Iterable, Optional, Tuple
from ghostiss.container import Container
from ghostiss.core.ghosts import (
    Action, MOSSAction,
    LLMRunner,
    Operator,
)
from ghostiss.core.moss import MOSS, PyContext
from ghostiss.core.messages import Messenger, DefaultTypes
from ghostiss.core.runtime.llms import LLMs, LLMApi, Chat
from ghostiss.core.runtime.threads import Thread, thread_to_chat
from ghostiss.helpers import uuid
from pydantic import BaseModel, Field


class MossRunner(LLMRunner):
    """
    llm runner with moss
    """

    def __init__(
            self, *,
            system_prompt: str,
            instruction: str,
            llm_api_name: str = "",
            pycontext: Optional[PyContext] = None,
            **variables,
    ):
        self._system_prompt = system_prompt
        self._instruction = instruction
        self._llm_api_name = llm_api_name
        self._pycontext = pycontext
        self._variables = variables

    def actions(self, container: Container, thread: Thread) -> Iterable[Action]:
        moss = container.force_fetch(MOSS)
        if self._variables:
            moss = moss.with_vars(**self._variables)
        if self._pycontext:
            moss.update_context(self._pycontext)
        moss = moss.update_context(thread.pycontext)
        yield MOSSAction(moss)

    def prepare(self, container: Container, thread: Thread) -> Tuple[Iterable[Action], Chat]:
        """
        生成默认的 chat.
        :param container:
        :param thread:
        :return:
        """
        system = [
            DefaultTypes.DEFAULT.new_system(content=self._system_prompt),
            DefaultTypes.DEFAULT.new_system(content=self._instruction),
        ]
        chat = thread_to_chat(chat_id=uuid(), thread=thread, system=system)
        actions = self.actions(container, thread)
        result_actions = []
        for action in actions:
            chat = action.update_chat(chat)
            result_actions.append(action)
        return result_actions, chat

    def get_llmapi(self, container: Container) -> LLMApi:
        llms = container.force_fetch(LLMs)
        return llms.get_api(self._llm_api_name)

    def messenger(self, container: Container) -> Messenger:
        return container.force_fetch(Messenger)


class MOSSRunnerTestSuite(BaseModel):
    """
    模拟一个 MOSSRunner 的单元测试.
    """

    system_prompt: str = Field(
        description="定义系统 prompt. "
    )
    instruction: str = Field(
        description="定义当前 Runner 的 prompt",
    )
    llm_api_name: str = Field(
        default="",
        description="定义当前 runner 运行时使用的 llm api 是哪一个. ",
    )
    pycontext: PyContext = Field(
        description="定义 pycontext. "
    )
    thread: Thread = Field(
        description="定义一个上下文. "
    )

    def get_runner(self) -> MossRunner:
        """
        从配置文件里生成 runner 的实例.
        """
        return MossRunner(
            system_prompt=self.system_prompt,
            instruction=self.instruction,
            llm_api_name=self.llm_api_name,
            pycontext=self.pycontext,
        )

    def run_test(self, container: Container) -> Tuple[Thread, Optional[Operator]]:
        """
        基于 runner 实例运行测试. 如何渲染交给外部实现.
        """
        runner = self.get_runner()
        thread = self.thread
        return runner.run(container, thread)
