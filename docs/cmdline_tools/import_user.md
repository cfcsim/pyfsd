# import\_user
此工具可以从其他格式的用户数据库读取用户信息保存到PyFSD使用的数据库。  
```shell
$ python -m pyfsd.utils.import_users --help
usage: __main__.py [-h] [-v] [-c CONFIG_PATH] filename {cfcsim,pyfsd,fsd}

convert users database in other format into PyFSD's format

positional arguments:
  filename              filename of the original file
  {cfcsim,pyfsd,fsd}    format of the original file

options:
  -h, --help            show this help message and exit
  -v, --verbose         increase output verbosity
  -c CONFIG_PATH, --config-path CONFIG_PATH
                        path to the config of PyFSD
```
命令格式: `python -m pyfsd.utils.import_users -c PyFSD配置文件名(默认为pyfsd.toml,可选) 要导入的文件的格式 要导入的文件的文件名`  
例:  
```shell
$ python -m pyfsd.utils.import_users cert.sqlitedb3 cfcsim  # 以cfcsim's fsd fork格式把cert.sqlitedb3中的数据读出，然后储存到pyfsd.toml配置的PyFSD数据库
$ python -m pyfsd.utils.import_users -c env_pyfsd.toml cert.txt fsd  # 以fsd cert.txt格式把cert.txt中的数据读出，然后储存到env_pyfsd.toml里配置的数据库
```
