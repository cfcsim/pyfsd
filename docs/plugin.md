# 插件
一般地，只需要创建pyfsd/plugins目录然后把插件文件丢进去就行。没效果的话需要用`PYTHONPATH=. twistd -n pyfsd`来启动PyFSD。
## 插件结构
### PyFSD Plugin
::: pyfsd.plugin.IPyFSDPlugin
### Metar获取器
::: pyfsd.metar.fetcher.IMetarFetcher
### 数据库源
::: pyfsd.database.IDatabaseMaker
