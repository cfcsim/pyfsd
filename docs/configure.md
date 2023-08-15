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
fetchers = ["NOAA", "anotherfetcher"]
skip_previous_fetcher = true
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
`motd_encoding`: MOTD的编码方式。如:`gbk`或`utf-8`。
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
此模式下时:  
`cron_time`: (单位为秒)多久下载一次Metar。  
- `once`: 每当客户端请求Metar时立即下载相关机场的Metar。  
`fetchers`: 设置Metar下载器。可以配置多个，一个无法使用时会使用下一个。

`fallback`: 替代计划。  
解释：当是`cron`模式时，获取一个机场的METAR失败，就会尝试用`once`模式获取。反之亦然，当是`once`模式时，获取一个机场的METAR失败，就会尝试用`cron`模式获取。  
例:  
```toml
[pyfsd.metar]
mode = "cron"
cron_time = 3600
fetchers = ["NOAA", "xmairavt7"]
skip_previous_fetcher = false
```
按以上配置，无法在`cron`模式获取到需要的机场的Metar时，就会回退到`once`模式，然后再尝试NOAA源(`once`模式)，如没有获取到再去尝试xmairavt7源。
做这个模式的初衷是某些METAR源可能缺失某些机场，这个时候就要用其他METAR源去替代。但是从上例可以看出，如果缺失机场的METAR源同时也支持`once`模式，就会浪费时间再去缺失那个机场的METAR源查询。所以：  
`skip_previous_fetcher`: (bool, true真false假，仅在`cron`模式时生效)跳过`cron`模式时下载时(即缺失那个机场的METAR源)使用的METAR源。`fallback`配置对存在时并且`mode`为`cron`时此配置对也必须存在。如果你不需要此特性，填false。
例:  
```toml
[pyfsd.metar]
mode = "cron"
cron_time = 3600
fetchers = ["NOAA", "xmairavt7"]
skip_previous_fetcher = true
```
按以上配置，无法在`cron`模式获取到需要的机场的Metar时，就会回退到`once`模式，然后直接尝试xmairavt7源(既跳过NOAA源)。
