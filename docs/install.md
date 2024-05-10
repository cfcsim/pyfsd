# 安装

一般地，您可以直接使用pip安装:
```
pip install pyfsd[数据库]
```
其中数据库字段可以是`sqlite3`，`postgresql`，`mysql`，`oracle`，`mssql`中的一种。例如:
```
pip install pyfsd[sqlite3]  # SQLite 3
pip install pyfsd[postgresql]  # PostgreSQL
pip install pyfsd[mysql]  # MySQL / MariaDB
pip install pyfsd[oracle]  # OracleDB
pip install pyfsd[mssql]  # Microsoft SQL Server
```
但PyPI上的PyFSD通常不是最新的开发版。建议从[GitHub Actions](https://github.com/cfcsim/pyfsd/actions/workflows/python.yml)的Artifacts下载dict，解压后使用pip安装wheel文件即可。  
也可以直接安装依赖之后从源代码运行（需要PDM）:
```
pip install pdm # 安装PDM
pdm install -G 数据库 # 安装依赖
eval $(pdm venv activate in-project) # 进入虚拟环境(Linux)
Invoke-Expression (pdm venv activate in-project) # 进入虚拟环境(Windows)
```
现在运行PyFSD:  
```
python -m pyfsd
```
如果程序没有立即退出，那么安装应该成功了。您现在可以按Ctrl-C退出了。
