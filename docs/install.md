# 安装

一般地，您可以直接使用pip安装:
```
pip install pyfsd
```
但PyPI上的PyFSD通常不是最新的开发版。建议从[GitHub Actions](https://github.com/gamecss/pyfsd/actions/workflows/python.yml)的Artifacts下载dict，解压后使用pip安装wheel文件即可。  
也可以直接安装依赖之后从源代码运行（需要PDM）:
```
pip install pdm # 安装PDM
pdm install # 安装依赖
eval $(pdm venv activate in-project) # 进入虚拟环境(Linux)
Invoke-Expression (pdm venv activate in-project) # 进入虚拟环境(Windows)
```

## 使用

```
twistd -n pyfsd
```
如果您不是通过PDM安装启动，您需要使用`PYTHONPATH=. twistd -n pyfsd`来加载插件。  
（如果没有配置文件存在的话）会自动在当前目录创建配置文件与数据库文件。`
