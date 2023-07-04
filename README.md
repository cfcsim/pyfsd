# PyFSD
基于Twisted的[FSD](https://github.com/kuroneko/fsd)协议9的实现。  

## 逝用
```
pip install pyfsd
twistd -n pyfsd # 运行,将会自动产生配置文件及数据库
```
或如果您只是单纯想试一下，可以用ECHO/Swift(FSD Private/Legacy)连接到`bbs.cfcsim.cn`(无鉴权，任何账户都可登录)。

### 问题排除:
运行`twistd -n pyfsd`提示`Unknown command: pyfsd`
: 由于twistd没有加载当前目录的插件。把当前路径写入文件保存为pyfsd.pth并放到site-packages目录或使用`PYTHONPATH=. twistd -n pyfsd`来运行即可。

## Todo
### 客户端协议(9)
- METAR解析(`#WX`)
### 多服务器协议
一点还没做啊!谁会需要多服务器啊???

## 开源协议
MIT License  
Copyright (c) 2023 gamecss  
无附加条款。
