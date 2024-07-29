import sys
import argparse
import os
from typing import Optional, Type, ClassVar

import yaml
from ghostiss.container import Container, Provider, CONTRACT
from ghostiss.core.ghosts import Operator, Mindflow
from ghostiss.contracts.storage import Storage, FileStorageProvider
from ghostiss.contracts.configs import ConfigsByStorageProvider
from ghostiss.core.moss import MOSS, BasicMOSSImpl, BasicModulesProvider
from ghostiss.reflect import Interface, Library
from ghostiss.framework.llms import ConfigBasedLLMsProvider
from ghostiss.framework.runners.mossrunner import MOSSRunnerTestSuite
from ghostiss.core.ghosts.messenger import TestMessengerProvider
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

"""
基于 MOSS Runner 来实现 MOSS 的测试脚本. 
"""


class MOSSTestProvider(Provider):
    moss_doc: ClassVar[str] = """
Model-oriented Operating System Simulation (MOSS).
You can use the api that MOSS provided to implement your plan.
"""

    def singleton(self) -> bool:
        return False

    def contract(self) -> Type[CONTRACT]:
        return MOSS

    def factory(self, con: Container) -> Optional[CONTRACT]:
        return BasicMOSSImpl(container=con, doc=self.moss_doc).with_vars(
            Interface(cls=Operator),
            Library(cls=Mindflow),
        )


def _prepare_container() -> Container:
    container = Container()
    # 注册一个假的 messenger.
    container.register(TestMessengerProvider())
    # 注册 moss 相关.
    container.register(BasicModulesProvider())
    container.register(MOSSTestProvider())
    # 注册 llms 配置.
    ghostiss_dir = os.path.abspath(os.path.dirname(__file__) + "/../../demo/ghostiss")
    container.register(FileStorageProvider(ghostiss_dir))
    container.register(ConfigsByStorageProvider("configs"))
    # 准备 llms
    container.register(ConfigBasedLLMsProvider("llms/llms_conf.yaml"))
    return container


def json_format(data: str) -> Markdown:
    return Markdown(f"""
```json
{data}
```
""")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="run ghostiss runner test cases which located at demo/ghostiss/tests/moss_tests",
    )

    parser.add_argument(
        "--case", "-c",
        help="file name of the case without .yaml suffix",
        type=str,
        default="hello_world"
    )

    container = _prepare_container()
    parsed = parser.parse_args(sys.argv[1:])
    storage = container.force_fetch(Storage)
    prefix = "tests/moss_tests/"
    file_name = os.path.join(prefix, parsed.case + ".yaml")
    content = storage.get(file_name)
    if content is None:
        raise FileNotFoundError(f"file {file_name} not found")

    data = yaml.safe_load(content)
    suite = MOSSRunnerTestSuite(**data)
    # 输出环节.
    console = Console()

    thread = suite.thread
    # 先输出 thread 完整信息
    thread_json = json_format(thread.model_dump_json(indent=2, exclude_defaults=True))
    console.print(Panel(thread_json, title="thread info"))

    results = suite.run_test(container)
    # 输出不同模型生成的 chatinfo.
    for api_name, _result in results.items():
        _thread, _chat, _op = _result
        title = api_name
        # 输出 chat 信息.
        console.print(
            Panel(
                json_format(_chat.model_dump_json(exclude_defaults=True, indent=2)),
                title=f"{title}: chat info"
            ),
        )
        # 用 markdown 输出 chat info.
        lines = []
        for msg in _chat.get_messages():
            content = f"> {msg.role}:\n\n{msg.get_content()}"
            lines.append(content)
        console.print(Panel(
            Markdown("\n\n----\n\n".join(lines)),
            title=f"{title}: chat info in markdown"
        ))

    # 输出 appending 信息.
    for api_name, _result in results.items():
        _thread, _chat, _op = _result
        title = api_name
        # 输出 appending 的消息.
        appending = _thread.appending
        for msg in appending:
            # 输出 appending 消息体.
            console.print(
                Panel(
                    json_format(msg.model_dump_json(exclude_defaults=True, indent=2)),
                    title=f"{title}: appending message json",
                ),
            )
            content = f"{msg.content} \n\n----\n\n {msg.memory}"
            # 用 markdown 输出消息的 content 和 memory.
            panel = Panel(Markdown(content), title=f" {title}: appending message")
            console.print(panel)
            for caller in msg.callers:
                if caller.name == "moss":
                    console.print(
                        Panel(
                            Markdown("```python\n\n" + caller.arguments + "\n```"),
                            title=f"{title}: generated moss code"
                        )
                    )
        console.print(Panel(str(_op), title=f" {title}: operator output"))


if __name__ == "__main__":
    main()
