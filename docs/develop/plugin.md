# 插件开发
基于[Twisted插件机制](https://docs.twisted.org/en/stable/core/howto/plugin.html)。  
现在有三种插件形式:  
[`PyFSDPlugin`][pyfsd.plugin.IPyFSDPlugin]: 接受关于PyFSD本体的一些事件，如新用户连接等。  
[`MetarFetcher`][pyfsd.metar.fetch.IMetarFetcher]: Metar源。  
[`DatabaseMaker`][pyfsd.database.IDatabaseMaker]: 数据库源。
注：所有插件都应该实现(`@zope.interface.implementer`) [twisted.plugin.IPlugin][]并实例化才能被加载。  
## 插件参考
### PyFSD Plugin
#### PreventEvent
::: pyfsd.plugin.PreventEvent
#### PyFSD Plugin
::: pyfsd.plugin.IPyFSDPlugin
### Metar获取器
::: pyfsd.metar.fetch.IMetarFetcher
### 数据库源
::: pyfsd.database.IDatabaseMaker
## 示例
### PyFSDPlugin
（所有事件详见`IPyFSDPlugin`）
```python3
from twisted.plugin import IPlugin
from zope.interface import implementer

from pyfsd.plugin import BasePyFSDPlugin, IPyFSDPlugin, PreventEvent

# 方式一（推荐）
@implementer(IPlugin)
class MyPlugin(BasePyFSDPlugin):
# 方式二
@implementer(IPlugin, IPyFSDPlugin):
class MyPlugin:
    plugin_name = "插件名"
    api = 1  # API等级，目前最高为1
    
    def beforeStart(self, pyfsd: "PyFSDService") -> None:
        self.pyfsd = pyfsd

    def lineReceivedFromClient(
        self, protocol: "FSDClientProtocol", byte_line: bytes
    ) -> None:
        if line.startswith(b"#HI"):
            protocol.sendLine(b"#HI:" + byte_line)
            # 在你确保你已经处理完这个事件后，可以抛出PreventEvent，这会阻止其他插件和PyFSD的处理器接收到这个事件。
            raise PreventEvent
            

# 必须实例化，否则无法加载
plugin = MyPlugin()
```
### Metar获取器
```python3
from typing import Optional

from metar.Metar import Metar
from twisted.plugin import IPlugin
from zope.interface import implementer

from ..metar.fetch import IMetarFetcher, MetarInfoDict


@implementer(IPlugin, IMetarFetcher)
class MetarFetcher:
    metar_source = "example"  # Metar源名

    def fetch(self, icao: str) -> Optional[Metar]:
        metar_text = "ZSFZ 200300Z 17004MPS 9999 FEW020 33/27 Q1008 NOSIG"  # 假设如此
        if metar_text is None:
            return None
        else:
            return Metar(parser.metar_text, strict=False)

    def fetchAll(self) -> MetarInfoDict:
        all_metar: MetarInfoDict = {
            "ZSFZ": Metar("ZSFZ 200300Z 17004MPS 9999 FEW020 33/27 Q1008 NOSIG", strict=False)
            "ZBAA": Metar("ZBAA 200400Z VRB02MPS CAVOK 34/21 Q1006 NOSIG", strict=False)
        }  # 假设如此
        return all_metar


# 必须实例化，否则无法加载
fetcher = MetarFetcher()
```
