import inspect
from types import ModuleType
from typing import Optional, Any, Dict, get_type_hints, Type
import io

from ghostiss.container import Container, Provider
from ghostiss.core.moss.abc import (
    Moss,
    MossCompiler, MossRuntime, MossPrompter, MOSS_NAME, MOSS_TYPE_NAME,
    MOSS_HIDDEN_MARK, MOSS_HIDDEN_UNMARK,
)
from ghostiss.core.moss.utils import is_name_public
from ghostiss.core.moss.libraries import Modules, ImportWrapper
from ghostiss.core.moss.pycontext import PyContext, SerializableType, Property
from ghostiss.helpers import get_module_spec
from contextlib import contextmanager, redirect_stdout

IMPORT_FUTURE = "from __future__ import annotations"


class MossCompilerImpl(MossCompiler):
    def __init__(self, *, container: Container, pycontext: Optional[PyContext] = None):
        self._container = Container(parent=container)
        self._pycontext = pycontext if pycontext else PyContext()
        self._modules: Modules = self._container.force_fetch(Modules)
        self._predefined_locals: Dict[str, Any] = {
            # 默认代理掉 import.
            '__import__': ImportWrapper(self._modules),
        }
        self._injections: Dict[str, Any] = {}

    def container(self) -> Container:
        return self._container

    def pycontext(self) -> PyContext:
        return self._pycontext

    def join_context(self, context: PyContext) -> "MossCompiler":
        self._pycontext = self._pycontext.join(context)
        return self

    def with_locals(self, **kwargs) -> "MossCompiler":
        self._predefined_locals.update(kwargs)
        return self

    def injects(self, **attrs: Any) -> "MossCompiler":
        self._injections.update(attrs)
        return self

    def _compile(self, modulename: str) -> ModuleType:
        code = self.pycontext_code(model_visible_only=False)
        module = ModuleType(modulename)
        module.__dict__.update(self._predefined_locals)
        compiled = compile(code, modulename, "exec")
        exec(compiled, module.__dict__)
        return module

    def _new_runtime(self, module: ModuleType) -> "MossRuntime":
        return MossRuntimeImpl(
            container=self._container,
            pycontext=self._pycontext.model_copy(deep=True),
            source_code=self.pycontext_code(model_visible_only=False),
            compiled=module,
            injections=self._injections,
        )

    def pycontext_code(self, model_visible_only: bool = True) -> str:
        code = self._pycontext.code
        if code is None and self._pycontext.module:
            module = self._modules.import_module(self._pycontext.module)
            code = inspect.getsource(module)
        if not code.lstrip().startswith(IMPORT_FUTURE):
            code = IMPORT_FUTURE + "\n\n" + code.lstrip("\n")
            return code
        return code if code else ""

    def destroy(self) -> None:
        # container 先不 destroy.
        del self._container
        del self._pycontext
        del self._predefined_locals
        del self._injections


def new_moss_stub(cls: Type[Moss], pycontext: PyContext):
    # cls 必须不包含参数.
    obj = cls()
    obj.__pycontext__ = pycontext
    # 反向注入
    for name, value in cls.__dict__.items():
        if not name.startswith('_') and isinstance(value, Property) and name not in pycontext.properties:
            pycontext.define(value)
    # 初始化 pycontext variable
    for name, var in pycontext.properties.items():
        # 直接用 property 作为值.
        setattr(obj, name, var)
    return obj


class MossRuntimeImpl(MossRuntime, MossPrompter):

    def __init__(
            self, *,
            container: Container,
            pycontext: PyContext,
            source_code: str,
            compiled: ModuleType,
            injections: Dict[str, Any],
    ):
        self._container = container
        self._modules: Modules = container.force_fetch(Modules)
        self._compiled = compiled
        self._source_code = source_code
        self._pycontext = pycontext
        self._injections = injections
        self._runtime_std_output = ""
        # 初始化之后不应该为 None 的值.
        self._built: bool = False
        self._moss: Optional[Moss] = None
        self._moss_prompt: Optional[str] = None
        self._bootstrap_moss()

    def _bootstrap_moss(self):
        if self._built:
            return
        self._built = True
        self._compile_moss()

    def _compile_moss(self):
        moss_type = self.moss_type()
        if not issubclass(moss_type, Moss):
            raise TypeError(f"Moss type {moss_type} is not subclass of Moss")

        # 创建 stub.
        pycontext = self._pycontext
        for prop in pycontext.properties.values():
            # 基于上下文还原变量.
            prop.generate_value(self._compiled)

        moss = new_moss_stub(moss_type, pycontext)

        # 初始化 injection. 强制赋值.
        injections = self._injections.copy()
        # 初始化 pycontext injection. 替代掉系统默认的 injection.
        for name, injection in self._pycontext.injections.items():
            injection_module, injection_spec = injection.get_from_module_attr()
            # 如果要注入的对象就是当前包, 则直接返回当前包的和苏剧.
            if injection_module == self._compiled.__name__:
                module = get_module_spec(self._compiled, injection_spec)
            else:
                module = self._modules.import_module(injection_module)
            # 否则返回查找结果.
            if injection_spec:
                value = get_module_spec(module, injection_spec)
            else:
                value = module
            injections[name] = value

        # 将 Injections 直接注入.
        for name, value in injections.items():
            if name not in pycontext.properties:
                setattr(moss, name, value)

        # 初始化基于容器的依赖注入.
        typehints = get_type_hints(moss_type, localns=self._compiled.__dict__)
        for name, typehint in typehints.items():
            if name.startswith('_'):
                continue

            # 已经有的就不再注入.
            if hasattr(moss, name):
                continue
            value = getattr(moss_type, name, None)
            if value is None:
                # 为 None 才依赖注入.
                value = self._container.get(typehint)
                # 依赖注入.
                setattr(moss, name, value)
        self._moss = moss
        self._compiled.__dict__[MOSS_NAME] = moss
        self._compiled.__dict__[MOSS_TYPE_NAME] = moss_type

    def container(self) -> Container:
        return self._container

    def prompter(self) -> MossPrompter:
        return self

    def module(self) -> ModuleType:
        return self._compiled

    def locals(self) -> Dict[str, Any]:
        return self._compiled.__dict__

    def moss(self) -> object:
        return self._moss

    def dump_context(self) -> PyContext:
        return self._pycontext

    def dump_std_output(self) -> str:
        return self._runtime_std_output

    @contextmanager
    def runtime_ctx(self):
        # 保存原始的stdout
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            yield
        self._runtime_std_output += str(buffer.getvalue())

    def pycontext_code(
            self,
            model_visible: bool = True,
    ) -> str:
        code = self._source_code
        return self._parse_pycontext_code(code, model_visible)

    @staticmethod
    def _parse_pycontext_code(code: str, model_visible: bool = True) -> str:
        lines = code.split("\n")
        results = []
        hide = False
        for line in lines:
            if line.startswith(MOSS_HIDDEN_MARK):
                hide = True
            if hide and model_visible:
                continue
            if not hide or not model_visible:
                results.append(line)
            elif line.startswith(MOSS_HIDDEN_UNMARK):
                hide = False
        return "\n".join(results)

    def destroy(self) -> None:
        self._container.destroy()
        if hasattr(self._moss, "__pycontext__"):
            del self._moss.__pycontext__
        del self._container
        del self._injections
        del self._compiled
        del self._moss


class TestMOSSProvider(Provider[MossCompiler]):
    """
    用于测试的标准 compiler.
    但实际上好像也是这个样子.
    """

    def singleton(self) -> bool:
        return False

    def contract(self) -> Type[MossCompiler]:
        return MossCompiler

    def factory(self, con: Container) -> MossCompiler:
        return MossCompilerImpl(container=con, pycontext=PyContext())