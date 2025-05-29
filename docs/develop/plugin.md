# 插件开发
正在重写....

## 依赖注入
你可以通过依赖注入获得 PyFSD 的子组件、配置信息等。  
所用可用依赖见[依赖容器][pyfsd.dependencies.Container]  
详细用法见[ `dependency_injector` 文档](https://python-dependency-injector.ets-labs.org/wiring.html#wiring)。基本用法如下:
```python3
db_engine = Provide[Container.db_engine]

# 获取数据库操作器为dbengine参数
@inject
def function_that_needs_db(dbengine = Provide[Container.db_engine]): ...
```
插件在被 PyFSD 导入时(即 Python 中的 `import`)，PyFSD 会自动把`Provide[依赖]`替换成真实的组件实例。  
!!! note

    如果有多个装饰器，`@inject`必须是最底下一个(最靠近函数的一个)  
注意！此种写法是**无效**的:  
```python3
@inject
def function_that_do_something(db_engine = Provide[Container.db_engine]): ...
    print(db_engine)

function_that_do_something()  # 在导入插件的过程中就运行
```
```
<dependency_injector.wiring.Provide object at 0xae9b0f50c152>
```
其中原因是 Python 在导入(`import`)一个`.py`文件之前必须先把它执行一遍，而 PyFSD 只能在插件导入之后再进行依赖注入。对于这种需要初始化插件的操作可以在插件的[ `setup` 函数][pyfsd.plugin.Plugin.setup]中完成。
