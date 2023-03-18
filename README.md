# pyfsd

首先感谢您阅读README。  
基于Twisted的[FSD](https://github.com/kuroneko/fsd)协议9的实现。  
⚠️警告⚠️：代码质量低下

## 逝用
请确保已安装pdm. (`pip install pdm`)
```
pdm install # 安装依赖
python -m pyfsd # 运行
```

## Todo
### 协议(9)
- METAR(`#WX`,`$AX`)
- CQ (信息广播/查询用户信息/查询机组飞行计划)
### 其他
- 鉴权 (sqliledb, mysql, etc)
- 插件机制

## 开源协议
MIT License
Copyright (c) 2023 gamecss  
无附加条款。
