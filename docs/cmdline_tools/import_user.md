# import\_user
此工具可以从其他格式的用户数据库读取用户信息保存到PyFSD使用的数据库。  
```shell
$ python -m pyfsd.utils.import_users --help
Usage: python -m pyfsd.utils.import_users [options] [filename]
Options:
  -c, --config-path=  Path to the config file. [default: pyfsd.toml]
  -f, --format=       Format of the original database file.
      --help          Display this help and exit.
      --version       Display Twisted version and exit.

This tool can convert users database in other format into PyFSD format.
Example:
$ python -m pyfsd.utils.import_users -f cfcsim cert.sqlitedb3
$ python -m pyfsd.utils.import_users -f fsd -c env_pyfsd.toml cert.txt
```
命令格式: python -m pyfsd.utils.import\_users -f 格式 -c PyFSD配置文件名(默认为pyfsd.toml,可选) 要倒入的数据库文件的文件名
例:
```shell
$ python -m pyfsd.utils.import_users -f cfcsim cert.sqlitedb3  # 以cfcsim fork fsd格式把cert.sqlitedb3中的数据读出，然后储存到pyfsd.toml配置的PyFSD数据库
$ python -m pyfsd.utils.import_users -f fsd -c env_pyfsd.toml cert.txt  # 以fsd cert.txt格式把cert.txt中的数据读出，然后储存到env_pyfsd.toml里配置的数据库
```
