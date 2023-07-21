# 配置
## 命令行配置
```shell
$ twistd -n pyfsd --help
Usage: twistd [options] pyfsd [options]
Options:
  -c, --config-path=    Path to the config file. [default: pyfsd.toml]
      --help            Display this help and exit.
  -l, --disable-loguru  Use default logger instead of loguru.
      --version         Display Twisted version and exit.
```
-c或--config-path: 配置文件的路径。默认为`pyfsd.toml`。  
-l或--disable-logger: 禁用loguru，使用Twisted默认日志记录器。
## 配置文件
!!! note
    
    第一次启动会自动生成。无特别声明时，所有配置对都必须存在。
```toml
[pyfsd.database]
source = "sqlite3"
filename = "pyfsd.db"

[pyfsd.client]
port = 6809
motd = """Modify motd in pyfsd.toml."""
motd_encoding = "ascii"
blacklist = []

[pyfsd.metar]
mode = "cron"
cron_time = 3600
fetchers = ["NOAA"]
```
### 数据库
通过pyfsd.database表来配置数据库。  
`source`: 数据库源。PyFSD仅自带`sqlite3`源，可以通过添加插件来使用其他源。  
其他参数取决于你使用的数据库源。对`sqlite3`源来说:  
`filename`: 数据库文件名。
### 客户端
通过pyfsd.client表来配置客户端协议。  
`port`: 客户端协议的端口。ECHO Pilot、Swift等连飞软件及原版FSD默认使用6809端口。  
`motd`: 即Message Of The Day，会在客户端成功登录后发送。  
`motd_encoding`: MOTD的编码方式。如果MOTD是中文建议改为`GBK`。  
`blacklist`: IP黑名单。例：  
```toml
[pyfsd.client]
(省去一大堆)
blacklist = ["114.514.191.81", "143.22.124.13"]
```
### Metar
通过pyfsd.metar表来配置Metar。
`mode`: 下载Metar的模式。可选值:
- `cron`: 间隔一段时间下载一次所有机场的Metar，通过`cron_time`配置。
- `once`: 每当客户端请求Metar时立即下载相关机场的Metar。

`cron_time`: (仅`cron`模式时需要，单位为秒)多久下载一次Metar。
`fetchers`: 设置Metar下载器。可以配置多个，一个无法使用时会使用下一个。

