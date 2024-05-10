# 配置
## 命令行配置
```shell
$ python -m pyfsd --help
usage: __main__.py [-h] [-c CONFIG_PATH]

options:
  -h, --help            show this help message and exit
  -c CONFIG_PATH, --config-path CONFIG_PATH
                        Path to the config file.
```
`-c`或`--config-path`: 配置文件的路径。默认为`pyfsd.toml`。  
`-h`或`--disable-logger`: 打印帮助信息(见上)并退出。

## 配置文件
!!! note
    
    目录下没有指定的配置文件时会自动生成。  
    配置缺失会导致PyFSD报错退出。(见疑难杂症)
默认配置如下: 
```toml
[pyfsd.database]
url = "sqlite:///pyfsd.db"

[pyfsd.client]
port = 6809
motd = """Modify motd in pyfsd.toml."""
motd_encoding = "ascii"
blacklist = []

[pyfsd.metar]
mode = "cron"
cron_time = 3600
fetchers = ["NOAA"]

[pyfsd.logger.logger]
handlers = ["default"]
level = "DEBUG"
propagate = true

[pyfsd.logger.handlers.default]
level = "INFO"
class = "logging.StreamHandler"
formatter = "colored"
```
接下来分块讲解。

### 数据库
```toml
[pyfsd.database]
url = "sqlite:///pyfsd.db"
```
通过`pyfsd.database`表来配置数据库。  
`url`(字符串): 数据库连接描述URL。具体可在[SQLAlchemy文档](https://docs.sqlalchemy.org/en/20/dialects/index.html#included-dialects)查看。
对于PyFSD来说,这些就够用了:
```toml
PostgreSQL: postgresql+asyncpg://user:password@host:port/dbname[?key=value&key=value...]
MySQL: mysql+asyncmy://user:password@host:port/dbname[?key=value&key=value...]
MariaDB: mariadb+asyncmy://user:password@host:port/dbname[?key=value&key=value...]
OracleDB: oracle+oracledb://user:password@host:port[/dbname][?service_name=<service>[&key=value&key=value...]]
MSSQL: mssql+aioodbc://<username>:<password>@<dsnname>[/dbname][?key=value&key=value...]
SQLite: sqlite+aiosqlite:///file_path
```
其中`user`是用户名,`password`是密码,`host`是域名或ip(服务在本机的话一般是`localhost`),`file_path`是到数据库文件的路径,`dbname`是数据库名,[abc]表示abc是可选字段。

### 客户端
```toml
[pyfsd.client]
port = 6809
motd = """Modify motd in pyfsd.toml."""
motd_encoding = "ascii"
blacklist = []
```
通过`pyfsd.client`表来配置客户端协议。  
`port`(整数): 客户端协议的端口。ECHO Pilot、Swift等连飞软件及原版FSD默认使用6809端口。   
`motd`(字符串): 即Message Of The Day,会在客户端成功登录后发送。如需多行直接在引号内换行即可。  
`motd_encoding`(字符串): MOTD的编码方式。如:`gbk`或`utf-8`。  
`blacklist`(字符串列表): IP黑名单。例: `blacklist = ["114.514.191.81", "143.22.124.13"]`  

### Metar
```toml
[pyfsd.metar]
mode = "cron"
cron_time = 3600
fetchers = ["NOAA"]
fallback_once = false
```
通过`pyfsd.metar`表来配置Metar。  
`mode`(字符串): 下载Metar的模式。可选值:  

- `cron`: 间隔一段时间下载一次所有机场的Metar,通过`cron_time`配置。  

在此模式下时还需配置:  
`cron_time`(数字,单位为秒): 多久下载一次Metar。  

- `once`: 当客户端请求Metar时再下载相关机场的Metar。  

`fetchers`(字符串列表): 设置Metar下载器。可以配置多个,一个无法使用时会使用下一个。  
`fallback_once`(布尔值): 在`cron`模式获取指定机场无结果后是否尝试用`once`模式获取。  

### 日志
以下是默认日志配置:   
```toml
[pyfsd.logger.logger]
handlers = ["default"]
level = "DEBUG"
propagate = true

[pyfsd.logger.handlers.default]
level = "INFO"
class = "logging.StreamHandler"
formatter = "colored"
```
通过`pyfsd.logger`表来配置日志,接下来分块讲解。
!!! note

    此节配置需要一定Python `logging`基础。如果您没有或读不懂,可以直接跳到配置模板一节。

#### 日志处理器
```toml
[pyfsd.logger.handlers.处理器id]
level = "INFO"
class = "logging.StreamHandler"
formatter = "colored"
```
通过`pyfsd.logger.handlers.处理器id`表来配置一个日志处理器,可以配置多个,但处理器id不能重复。  
`level`, `class`等配置详见Python [`logging.config`文档 字典架构细节](https://docs.python.org/zh-cn/3/library/logging.config.html#dictionary-schema-details)的`handlers`小节。  
`formatter`(字符串): 此日志处理器的格式化器。 选项:  

- `plain`: 无颜色文本日志,适用于日志文件
- `colored`: 有颜色文本日志,适用于终端输出
- `json`: JSON格式日志,适用于日志分析

#### 日志记录器
```toml
[pyfsd.logger.logger]
handlers = ["default"]
level = "DEBUG"
propagate = true
```
通过`pyfsd.logger.logger`表配置日志处理器。以下配置详见Python [`logging.config`文档 字典架构细节](https://docs.python.org/zh-cn/3/library/logging.config.html#dictionary-schema-details)的`loggers`小节。简略概括:   
`level`(字符串,可选): 全局日志等级。  
`propagate`(布尔值,可选): 是否把事件传递给更高级的日志记录器。  
`handlers`(字符串列表,可选): 启用的日志处理器的id的列表,必须是在`pyfsd.logger.handlers`表中配置的。  
`filters`(字符串列表,可选): 启用的过滤器id的列表。  

#### 日志时间设置(可选)
```toml
[pyfsd.logger.time]
fmt = "timestamp"
utc = true
key = "timestamp"
```
通过`pyfsd.logger.time`表配置日志的时间设置。  
`fmt`(字符串): 格式化后时间的格式,可以是`strftime`格式字符串,也可以是`iso`(ISO定义的时间格式),`timestamp`(时间戳)。  
`utc`(布尔值): 是否按UTC时区来,否则使用系统时区(`fmt`为`timestamp`时`utc`必须为`true`)。  
`key`(字符串): 日志数组中时间的键名,用`timestamp`就好  

#### 日志杂项(可选)
```toml
[pyfsd.logger]
include_extra = true
extract_record = true
```
通过`pyfsd.logger`配置日志杂项。  
`include_extra`(布尔值,可选): 是否把日志的`extra`部分输出。  
`extract_record`(布尔值,可选): 是否把发出日志的线程、进程名输出。  
