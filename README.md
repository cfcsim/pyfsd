# pyfsd
## ⚠️警告⚠️：代码质量低下
首先感谢您阅读README。  
基于Twisted的[FSD](https://github.com/kuroneko/fsd)协议9的实现。  

## 逝用
由于作者没有电脑无法运行Swift/ECHO来测试，并且目前无他人测试过，  
我不能保证项目正常运行且能正常广播/储存消息。  
如果您执意要测试:  
请确保已安装pdm. (`pip install pdm`)
```
pdm install # 安装依赖
twistd -n pyfsd # 运行
```
或如果您只是单纯想试一下，可以用ECHO/Swift(FSD Private/Legacy)连接到`bbs.cfcsim.cn`。

## Todo
### 客户端协议(9)
- METAR解析(`#WX`)
### 多服务器协议
一点还没做啊!谁会需要多服务器啊???
### 其他
- 鉴权 (sqliledb, mysql, etc)
- 插件机制 (1/2)
    - PyFSD plugin

## 开源协议
MIT License  
Copyright (c) 2023 gamecss  
无附加条款。
