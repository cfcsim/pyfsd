# 插件开发
注：这篇文档假定你有Python异步经验  
插件是`.py`文件的形式，PyFSD启动时自动加载。
!!! note

    此处的插件是指一个`.py`文件，其中定义的`PyFSDPlugin`等子类的实例被称为子插件，下文如此。

## 基本模板
每个插件文件都必须声明以下信息:
```python3
plugin_info = {
    "name": "plugin_name",
    "api": 4,
    "version": (1, "0.1.0"),
    "expected_config": {"a": int},
    "initializer": function_that_do_something,
}
```
`name`(字符串): 插件名。  
`api`(整数): 与插件搭配的PyFSD的API版本，目前为4。  
`version`(元组): 第一个元素为整数版本号，第二个为字符串版本号。  
`expected_config`(None或字典或TypedDict): 插件预期的配置结构(详见[`check_dict`函数][pyfsd.define.check_dict.check_dict])，不需要配置则置None。
`initializer`(`Callable[[], None]`): 无参数、无返回值函数，会在导入插件文件后，即将加载前运行。不需要则置`None`。

## 依赖注入
PyFSD以前将所有东西保存在`PyFSDService`里，但现在改用依赖注入。
所用可用依赖见[依赖容器][pyfsd.dependencies.Container]  
详细用法见[`dependency_injector`文档](https://python-dependency-injector.ets-labs.org/wiring.html#wiring)。基本用法如下:
```python3
db_engine = Provide[Container.db_engine]

@inject
def function_that_needs_db(dbengine = Provide[Container.db_engine]): ...
```
插件被PyFSD载入时(插件文件导入(`import`)后)PyFSD会自动把`Provide[相关依赖]`替换成相关依赖。  
!!! note

    如果有多个装饰器，`@inject`必须是最底下一个(最靠近函数的一个)  
注意！此种写法是*无效*的:  
```python3
@inject
def function_that_do_something(db_engine = Provide[Container.db_engine]): ...
    print(db_engine)

function_that_do_something()  # 在导入插件的过程中就运行
```
```
<dependency_injector.wiring.Provide object at 0xae9b0f50c152>
```
依赖注入是在*插件文件导入完成后*才进行的。在导入插件的过程中就被运行，但`db_engine`参数仍未被替换成对应的依赖。  
对此问题，就可以使用`plugin_info`的`initializer`属性了:  
```python3
@inject
def after_import(db_engine: AsyncEngine = Provide[Container.db_engine]) -> None:
    print(db_engine)

plugin_info = {
    "name": "plugin_name",
    "api": 4,
    "version": (1, "0.1.0"),
    "expected_config": {"a": int},
    "initializer": after_import,
}
```
于是`after_import`会在插件文件导入、检查`plugin_info`无误之后，在加载子插件之前运行:  
```
<sqlalchemy.ext.asyncio.engine.AsyncEngine object at 0x682669bc19c8>
```

## 子插件
现在三种插件形式:  
[`AwaitableMaker`][pyfsd.plugin.interfaces.AwaitableMaker]: 制作一个可等待对象，并和PyFSD一起运行。  
[`MetarFetcher`][pyfsd.metar.fetch.MetarFetcher]: Metar源。  
[`PyFSDPlugin`][pyfsd.plugin.interfaces.PyFSDPlugin]: 接受关于PyFSD本体的一些事件，如新用户连接等。  
注：子插件*必须实例化*才能被加载:
```python3
class APlugin: ...

a_plugin = APlugin()  # 这很重要!
```

### `PyFSDPlugin`
通过这种子插件，你可以监听一些事件（所有事件见[API][pyfsd.plugin.interfaces.PyFSDPlugin]）。  
```python3
from pyfsd.plugin.interfaces import Plugin, PyFSDPlugin

class MyPlugin(Plugin, PyFSDPlugin):
    # 例如line_received_from_client事件
    def line_received_from_client(self, protocol: ClientProtocol, line: bytes) -> None:
        if line.startswith(b"#HI"):
            protocol.send_line(b"#HI:" + byte_line)
            # 在你确保你已经处理完这个事件后，可以抛出PreventEvent异常
            # 来停止传播此事件。
            raise PreventEvent
            # 注意! 目前你只能在line_received_from_client事件处理函数中抛出此异常


# 必须实例化，否则无法加载
plugin = MyPlugin()
```

### `MetarFetcher`
通过这种子插件，你可以注册一个新的Metar来源。
```python3
from asyncio import get_event_loop
from typing import Optional

from aiohttp import ClientSession
from metar.Metar import Metar
from pyfsd.metar.fetch import MetarFetcher, MetarInfoDict
from pyfsd.plugin.interfaces import Plugin


class MetarFetcher(Plugin, MetarFetcher):
    metar_source = "example"  # Metar源名

    # 此处的config参数是配置文件的[pyfsd.metar]部分，下同
    async def fetch(self, config: dict, icao: str) -> Optional[Metar]:
        # 使用异步的aiohttp来下载Metar，不会使PyFSD整体阻塞
        # 详细用法请见aiohttp文档
        async with ClientSession() as session, session.get(url_of_metar) as resp:
            if resp.status != 200:  # 检查HTTP状态码是否是200
                return None
            metar_text = await resp.text("ascii", "ignore")
        if metar_text is None:
            return None
        else:
            return Metar(parser.metar_text, strict=False)

    async def fetch_all(self, config: dict) -> Optional[MetarInfoDict]:
        metar_text = {
            "ZSFZ": "ZSFZ 200300Z 17004MPS 9999 FEW020 33/27 Q1008 NOSIG",
            "ZBAA": "ZBAA 200400Z VRB02MPS CAVOK 34/21 Q1006 NOSIG",
        }  # 假设如此

        # 把解析部分单拎出来作为函数，方便在另外线程中运行
        def parser() -> MetarInfoDict:
            all_metar: MetarInfoDict = {}
            for icao, metar in metar_text.items():
                all_metar[icao] = Metar(metar, strict=False)
            return all_metar

        # fetch与fetch_all默认在主线程运行，所以fetch或fetch_all阻塞会导致PyFSD整个堵塞住
        # 这里使用asyncio的工具函数让parser函数在另一个线程运行，“异步化”
        return await get_event_loop().run_in_executor(None, parser)


# 必须实例化，否则无法加载
fetcher = MetarFetcher()
```

### `AwaitableMaker`
通过这种子插件，你可以创建一个阻塞的可等待对象并让它和PyFSD一起运行。
```python3
from asyncio import sleep
from time import time
from typing import Awaitable, Iterable

from pyfsd.plugin.interfaces import AwaitableMaker, Plugin


class AMaker(Plugin, AwaitableMaker):
    def __call__(self) -> Iterable[Awaitable]:
        async def func() -> None:  # 假设你那个阻塞的服务是这样的。。
            while True:
                print("Working", time())
                await sleep(1)

        yield func()  # 生成可等待对象
        # 接下来的代码会在PyFSD停止后运行，没需要留空也可以
        print("Clean up!")


# 必须实例化，否则无法加载
maker = AMaker()
```
```
2024-05-11 09:36:32 [info     ] PyFSD 0.0.1.2.dev0+86.gd72d5ce.dirty [pyfsd.main]
Working 1715391392.5279753
Working 1715391393.5289881
Working 1715391394.5294101
Working 1715391395.530576
2024-05-11 09:36:36 [info     ] Stopping                       [pyfsd.main]
Clean up!
```

### 子插件API参考
::: pyfsd.plugin.PreventEvent
::: pyfsd.plugin.interfaces.PyFSDPlugin
::: pyfsd.plugin.interfaces.AwaitableMaker
::: pyfsd.metar.fetch.MetarFetcher
